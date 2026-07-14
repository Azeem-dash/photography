#!/usr/bin/env python3
"""
Image pipeline for photo-by-azeem.

Reads originals from `library/`, and for each photo:
  - trims baked-in letterbox bars (Instagram-style white/black padding)
  - emits a responsive ladder of WebP + JPEG derivatives (never upscaling)
  - extracts a blurred LQIP placeholder + dominant colour (kills layout shift)
  - writes `data/gallery.json`, which drives the whole gallery

Usage:
    python3 tools/build_images.py            # build only what changed
    python3 tools/build_images.py --force    # rebuild everything

To add new photos: drop them into `library/`, add an entry to CURATION below
(or leave it out to default to the "street" category), then re-run.
"""

import argparse
import base64
import io
import json
import os
import sys
from collections import Counter

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "library")
OUT = os.path.join(ROOT, "assets", "gallery")
MANIFEST = os.path.join(ROOT, "data", "gallery.json")

# Responsive ladder. A derivative is only produced if the original is at least
# this wide -- we never invent pixels that were not in the source file.
WIDTHS = [400, 800, 1200, 1600, 2400]

# WebP carries the whole ladder (~97% browser support). A single JPEG rung is
# emitted at FALLBACK_W purely as the <img> src for the long tail.
FALLBACK_W = 1200
JPEG_Q = 82
LQIP_W = 20


def webp_quality(width):
    """Big rungs are only ever seen fullscreen in the lightbox, where a lower
    quality is visually indistinguishable but roughly 40% lighter."""
    if width >= 1600:
        return 72
    if width >= 1200:
        return 78
    return 80

# ---------------------------------------------------------------------------
# Curation. Photos are keyed by their original filename.
#
# Categories were assigned by eye from contact sheets of the full library.
# Anything not listed here is skipped -- that is how the screenshots, text/quote
# overlays and duplicates stay out of the portfolio.
# ---------------------------------------------------------------------------
MACRO, GOLDEN, ARCH, NATURE, RIDES, MOUNTAINS, STREET = (
    "macro", "golden", "architecture", "nature", "rides", "mountains", "street",
)

CATEGORY_META = [
    ("macro",        "Macro"),
    ("golden",       "Golden Hour"),
    ("architecture", "Architecture"),
    ("nature",       "Nature"),
    ("rides",        "Roads & Rides"),
    ("mountains",    "Mountains"),
    ("street",       "Street"),
]

CURATION = {
    # --- macro / objects: the bokeh close-ups ---
    "10.jpg":  (MACRO,  "Glass and Chrome"),
    "11.jpg":  (MACRO,  "Lens, Ring, Ledge"),
    "12.jpg":  (MACRO,  "Signet on Stone"),
    "13.jpg":  (MACRO,  "Tangled Sound"),
    "15.jpg":  (MACRO,  "Precision"),
    "20.jpg":  (MACRO,  "Black Stone"),
    "27.jpg":  (MACRO,  "Blue Dial, Green Hills"),
    "3.jpg":   (MACRO,  "Ring and Minaret"),
    "33.jpg":  (MACRO,  "Faith in Focus"),
    "35.jpg":  (MACRO,  "A Rose, Held"),
    "4.jpg":   (MACRO,  "Sapphire and Spire"),

    # --- golden hour ---
    "16.jpg":  (GOLDEN, "Ten Past Sunset"),
    "17.jpg":  (GOLDEN, "Through the Lens"),
    "2.jpg":   (GOLDEN, "Aviators at Dusk"),
    "22.jpg":  (GOLDEN, "Moonrise, Mirrored"),
    "24.jpg":  (GOLDEN, "Last Light in the Grass"),
    "40.jpg":  (GOLDEN, "Rickshaw into the Sun"),
    "41.jpg":  (GOLDEN, "Freight and Fire"),
    "42.jpg":  (GOLDEN, "The Road Ends in Gold"),
    "46.jpg":  (GOLDEN, "Backlit Leaves"),
    "61.webp": (GOLDEN, "Cloudbreak"),
    "62.webp": (GOLDEN, "Fairground Evening"),
    "63.webp": (GOLDEN, "Pastel Ridge"),
    "7.jpg":   (GOLDEN, "Bare Branches, Warm Wall"),

    # --- architecture & heritage ---
    "1.jpg":   (ARCH,   "Old Campus, Long Shadows"),
    "34.jpg":  (ARCH,   "Badshahi"),
    "37.jpg":  (ARCH,   "Fort Walls"),
    "38.jpg":  (ARCH,   "Arches, Reflected"),
    "39.jpg":  (ARCH,   "Dome and Minaret"),
    "45.jpg":  (ARCH,   "Iron Lattice, Violet Sky"),
    "51.jpg":  (ARCH,   "Glass at Golden Hour"),
    "66.jpg":  (ARCH,   "Vertical"),
    "69.jpg":  (ARCH,   "Hill Station Facade"),
    "71.jpg":  (ARCH,   "Stone and Steel"),
    "72.jpg":  (ARCH,   "Corner Block"),
    "75.jpg":  (ARCH,   "Sandstone, Blue Hour"),
    "76.jpg":  (ARCH,   "Cables and Cornices"),
    "79.jpeg": (ARCH,   "The Gate"),
    "80.jpeg": (ARCH,   "White Facade"),
    "82.jpeg": (ARCH,   "Clean Lines"),
    "83.jpg":  (ARCH,   "Domes Above the Bazaar"),
    "95.jpg":  (ARCH,   "Balconies"),
    "99.jpg":  (ARCH,   "Scaffold"),

    # --- nature & flora ---
    "14.jpg":  (NATURE, "Wildflower, Sunlit"),
    "18.jpg":  (NATURE, "Grass Against the Sun"),
    "21.jpg":  (NATURE, "Bougainvillea"),
    "23.jpg":  (NATURE, "Reaching Up"),
    "25.jpg":  (NATURE, "River Stones"),
    "26.jpg":  (NATURE, "Blades at Dusk"),
    "28.jpg":  (NATURE, "Veined Rock"),
    "29.jpg":  (NATURE, "Five Petals"),
    "36.jpg":  (NATURE, "After the Rain"),
    "52.jpg":  (NATURE, "One Rose"),
    "54.jpg":  (NATURE, "Marigold Verge"),
    "55.jpg":  (NATURE, "Open Hand"),
    "60.webp": (NATURE, "Chai in the Garden"),
    "102.jpg": (NATURE, "Roadside Chai"),

    # --- roads & rides ---
    "57.webp": (RIDES,  "Two Up"),
    "58.webp": (RIDES,  "Standing Still"),
    "59.webp": (RIDES,  "Helmet on the Tank"),
    "64.jpg":  (RIDES,  "Parked, Waiting"),
    "70.jpg":  (RIDES,  "Fuel Stop"),
    "73.jpg":  (RIDES,  "Rider and Machine"),
    "77.jpg":  (RIDES,  "Dusk Patrol"),
    "81.jpeg": (RIDES,  "Chrome and Dust"),
    "84.jpg":  (RIDES,  "Loaded Up"),
    "89.jpg":  (RIDES,  "Pines and Pistons"),
    "92.jpg":  (RIDES,  "Handlebars to the Pass"),

    # --- mountains & travel ---
    "50.jpg":  (MOUNTAINS, "Flag at the Hut"),
    "68.jpg":  (MOUNTAINS, "Moon Over the Ridge"),
    "85.jpg":  (MOUNTAINS, "Forest Stalls"),
    "86.jpg":  (MOUNTAINS, "The Long Way Up"),
    "87.jpg":  (MOUNTAINS, "Glacial Rubble"),
    "88.jpg":  (MOUNTAINS, "Through the Deodars"),
    "90.jpg":  (MOUNTAINS, "Pine Cathedral"),
    "91.jpg":  (MOUNTAINS, "Tall Timber"),
    "93.jpg":  (MOUNTAINS, "Where the Road Runs Out"),
    "94.jpg":  (MOUNTAINS, "The Wooden House"),
    "96.jpg":  (MOUNTAINS, "Valley Floor"),
    "97.jpg":  (MOUNTAINS, "Riverbed"),
    "98.jpg":  (MOUNTAINS, "Rest Stop"),

    # --- street & city life ---
    "100.jpg": (STREET, "After the Rain, Mall Road"),
    "101.jpg": (STREET, "Two Lamps"),
    "19.jpg":  (STREET, "Rooftops, Heavy Sky"),
    "43.jpg":  (STREET, "Parked on the Gravel"),
    "47.jpg":  (STREET, "Evening Commute"),
    "48.jpg":  (STREET, "Orange Haze"),
    "53.jpg":  (STREET, "Lot, Late Winter"),
    "56.jpg":  (STREET, "The Campus Bus"),
    "6.jpg":   (STREET, "Match Point"),
    "67.jpg":  (STREET, "Blue Alley"),
    "74.jpg":  (STREET, "Rickshaw Row"),
    "8.jpg":   (STREET, "Open Ground"),
}

# Portraits used in the About section -- processed, but kept out of the grid.
PORTRAITS = ["me3.jpeg", "me5.jpeg", "me.jpeg"]


def trim_bars(im, tol=12, max_frac=0.28):
    """Remove baked-in uniform letterbox bars (the white Instagram padding).

    Only trims a side if the bar is near-uniform AND smaller than `max_frac` of
    the dimension, so we never eat into an actual bright sky or a dark frame.
    """
    rgb = im.convert("RGB")
    w, h = rgb.size
    px = rgb.load()

    def line_uniform(coords):
        step = max(1, len(coords) // 40)
        sample = [px[x, y] for x, y in coords[::step]]
        base = sample[0]
        # bar colours are the flat extremes -- white or black
        if not (all(c > 238 for c in base) or all(c < 18 for c in base)):
            return False
        return all(
            abs(c[0] - base[0]) <= tol
            and abs(c[1] - base[1]) <= tol
            and abs(c[2] - base[2]) <= tol
            for c in sample
        )

    left = 0
    while left < int(w * max_frac) and line_uniform([(left, y) for y in range(h)]):
        left += 1
    right = w - 1
    while right > w - int(w * max_frac) and line_uniform([(right, y) for y in range(h)]):
        right -= 1
    top = 0
    while top < int(h * max_frac) and line_uniform([(x, top) for x in range(w)]):
        top += 1
    bottom = h - 1
    while bottom > h - int(h * max_frac) and line_uniform([(x, bottom) for x in range(w)]):
        bottom -= 1

    # require a meaningful trim, and a sane resulting box
    if right - left < w * 0.4 or bottom - top < h * 0.4:
        return im, False
    if left == 0 and top == 0 and right == w - 1 and bottom == h - 1:
        return im, False
    return im.crop((left, top, right + 1, bottom + 1)), True


def lqip_data_uri(im):
    """Tiny blurred WebP, inlined as a data URI -- the blur-up placeholder."""
    w, h = im.size
    small = im.resize((LQIP_W, max(1, round(LQIP_W * h / w))), Image.LANCZOS)
    small = small.filter(ImageFilter.GaussianBlur(1.1))
    buf = io.BytesIO()
    small.save(buf, "WEBP", quality=45, method=6)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def dominant_color(im):
    small = im.resize((32, 32), Image.LANCZOS).convert("RGB")
    common = Counter(small.getdata()).most_common(6)
    # skip near-white/near-black so the tint stays useful behind the blur
    for (r, g, b), _ in common:
        if 18 < (r + g + b) / 3 < 238:
            return f"#{r:02x}{g:02x}{b:02x}"
    r, g, b = common[0][0]
    return f"#{r:02x}{g:02x}{b:02x}"


def slug(name):
    return os.path.splitext(name)[0].replace(" ", "-").lower()


def process(fname, force=False):
    path = os.path.join(SRC, fname)
    with Image.open(path) as im:
        im = im.convert("RGB")
        im, trimmed = trim_bars(im)
        w, h = im.size

        sid = slug(fname)
        widths = [x for x in WIDTHS if x <= w] or [w]
        if widths[-1] < w and w <= WIDTHS[-1]:
            widths.append(w)  # keep the native size as the top rung

        # the JPEG fallback sits on the widest rung at or below FALLBACK_W
        fallback_w = max([x for x in widths if x <= FALLBACK_W] or [widths[0]])

        for tw in widths:
            th = round(h * tw / w)
            resized = None

            dst = os.path.join(OUT, f"{sid}-{tw}.webp")
            if force or not os.path.exists(dst):
                resized = im.resize((tw, th), Image.LANCZOS)
                resized.save(dst, "WEBP", quality=webp_quality(tw), method=6)

            if tw == fallback_w:
                dst = os.path.join(OUT, f"{sid}-{tw}.jpg")
                if force or not os.path.exists(dst):
                    if resized is None:
                        resized = im.resize((tw, th), Image.LANCZOS)
                    resized.save(dst, "JPEG", quality=JPEG_Q,
                                 optimize=True, progressive=True)

        return {
            "id": sid,
            "w": w,
            "h": h,
            "widths": widths,
            "fallback": fallback_w,
            "lqip": lqip_data_uri(im),
            "color": dominant_color(im),
            "trimmed": trimmed,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="rebuild every derivative")
    args = ap.parse_args()

    if not os.path.isdir(SRC):
        sys.exit(f"missing source directory: {SRC}")
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)

    available = {f for f in os.listdir(SRC) if not f.startswith(".")}
    missing = [f for f in CURATION if f not in available]
    if missing:
        print(f"!! curated but not found in library/: {', '.join(sorted(missing))}")

    photos, trimmed_count = [], 0
    for fname, (cat, title) in CURATION.items():
        if fname not in available:
            continue
        rec = process(fname, args.force)
        rec["category"] = cat
        rec["title"] = title
        trimmed_count += rec.pop("trimmed")
        photos.append(rec)
        print(f"  {fname:<12} {rec['w']}x{rec['h']:<5} -> {len(rec['widths'])} sizes  [{cat}]")

    portraits = []
    for fname in PORTRAITS:
        if fname not in available:
            continue
        rec = process(fname, args.force)
        rec.pop("trimmed", None)
        portraits.append(rec)

    # Biggest, most striking frames lead the grid; the rest keep a stable order.
    photos.sort(key=lambda p: (-(p["w"] * p["h"]), p["id"]))

    manifest = {
        "categories": [
            {"id": cid, "label": label}
            for cid, label in CATEGORY_META
            if any(p["category"] == cid for p in photos)
        ],
        "photos": photos,
        "portraits": portraits,
    }
    with open(MANIFEST, "w") as f:
        json.dump(manifest, f, indent=1)

    total = sum(
        os.path.getsize(os.path.join(OUT, f)) for f in os.listdir(OUT)
    ) / 1e6
    print(f"\n{len(photos)} photos, {len(portraits)} portraits")
    print(f"letterbox bars trimmed from {trimmed_count} photos")
    print(f"derivatives: {len(os.listdir(OUT))} files, {total:.1f} MB")
    print(f"manifest: {os.path.relpath(MANIFEST, ROOT)}")


if __name__ == "__main__":
    main()
