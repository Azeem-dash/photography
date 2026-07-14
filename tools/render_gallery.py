#!/usr/bin/env python3
"""
Renders data/gallery.json into index.html.

The gallery is baked into the HTML rather than assembled by JavaScript at
runtime: the photos are in the source for crawlers, and the grid paints on the
first frame instead of waiting for a fetch + render pass.

Everything is written between <!-- name:start --> / <!-- name:end --> markers, so
re-running is idempotent and the rest of index.html stays hand-editable.

Usage:
    python3 tools/render_gallery.py
"""

import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(ROOT, "data", "gallery.json")
PAGE = os.path.join(ROOT, "index.html")
GAL = "assets/gallery"

# Frames good enough to carry a full-bleed hero, chosen by eye.
HERO = ["67", "img_0772", "97", "100"]

# The grid sits entirely below the full-height hero, so no gallery image is ever
# above the fold. Every one of them is lazy; the hero alone owns the critical path.
EAGER = 0


def esc(s):
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def srcset(p, ext):
    return ", ".join(f"{GAL}/{p['id']}-{w}.{ext} {w}w" for w in p["widths"])


def card(p, labels, i):
    full = f"{GAL}/{p['id']}-{max(p['widths'])}.webp"
    fb = f"{GAL}/{p['id']}-{p['fallback']}.jpg"
    lazy = "eager" if i < EAGER else "lazy"
    prio = "high" if i < EAGER else "auto"
    is_hd = max(p["widths"]) >= 1600

    # width/height are the real pixel dimensions -- the browser reserves the
    # correct box before the file arrives, so nothing shifts as images land.
    return f"""            <figure
              class="card"
              data-cat="{p['category']}"
              data-cat-label="{esc(labels[p['category']])}"
              data-title="{esc(p['title'])}"
              data-full="{full}"
              data-w="{p['w']}"
              data-h="{p['h']}"
            >
              <button class="card__media" type="button" aria-label="Open &quot;{esc(p['title'])}&quot; full size">
                <picture>
                  <source type="image/webp" srcset="{srcset(p, 'webp')}" sizes="(min-width:1500px) 22vw, (min-width:1100px) 30vw, (min-width:720px) 45vw, 92vw" />
                  <img
                    class="card__img"
                    src="{fb}"
                    width="{p['w']}"
                    height="{p['h']}"
                    alt="{esc(p['title'])} — {esc(labels[p['category']].lower())} photograph by Muhammad Azeem"
                    loading="{lazy}"
                    decoding="async"
                    fetchpriority="{prio}"
                    style="background-image:url({p['lqip']});background-color:{p['color']}"
                  />
                </picture>
                <span class="card__veil">
                  <span class="card__cat">{esc(labels[p['category']])}</span>
                  <span class="card__title">{esc(p['title'])}</span>
                </span>
                {'<span class="card__hd">HD</span>' if is_hd else ''}
              </button>
            </figure>"""


def build(m):
    labels = {c["id"]: c["label"] for c in m["categories"]}
    photos = m["photos"]
    by_id = {p["id"]: p for p in photos}

    # --- hero slides ---
    # All four slides sit inside the viewport, so loading="lazy" would not hold
    # any of them back -- they would all download up front for ~3MB of images the
    # visitor cannot see yet. Only the first slide gets a real src; the rest carry
    # data-srcset and are hydrated by main.js once the page has finished loading.
    hero = []
    for n, hid in enumerate(HERO):
        p = by_id.get(hid)
        if not p:
            continue
        ss = ", ".join(
            f"{GAL}/{p['id']}-{w}.webp {w}w" for w in p["widths"] if w >= 800
        ) or f"{GAL}/{p['id']}-{max(p['widths'])}.webp {max(p['widths'])}w"
        fb = f"{GAL}/{p['id']}-{p['fallback']}.jpg"

        if n == 0:
            src = f'src="{fb}" srcset="{ss}" sizes="100vw" fetchpriority="high"'
        else:
            src = f'data-src="{fb}" data-srcset="{ss}" sizes="100vw"'

        hero.append(
            f"""          <div class="hero__slide{' is-active' if n == 0 else ''}">
            <img
              {src}
              width="{p['w']}"
              height="{p['h']}"
              alt=""
              decoding="async"
              style="background-color:{p['color']}"
            />
          </div>"""
        )

    # --- stats ---
    hd = sum(1 for p in photos if max(p["widths"]) >= 1600)
    stats = []
    for n, label in [
        (len(photos), "Photographs"),
        (len(m["categories"]), "Collections"),
        (hd, "Full resolution"),
    ]:
        stats.append(
            f"""              <div class="stat">
                <b class="stat__n">{n}</b>
                <span class="stat__l">{label}</span>
              </div>"""
        )

    # --- marquee (duplicated once: the CSS scrolls by -50%) ---
    words = [c["label"] for c in m["categories"]]
    run = "".join(f'<span class="marquee__item">{esc(w)}</span>' for w in words)
    marquee = f"          {run}{run}"

    # --- chips ---
    counts = {}
    for p in photos:
        counts[p["category"]] = counts.get(p["category"], 0) + 1
    chips = [
        f"""            <button class="chip" type="button" data-filter="all" aria-pressed="true">
              All<span class="chip__n">{len(photos)}</span>
            </button>"""
    ]
    for c in m["categories"]:
        chips.append(
            f"""            <button class="chip" type="button" data-filter="{c['id']}" aria-pressed="false">
              {esc(c['label'])}<span class="chip__n">{counts[c['id']]}</span>
            </button>"""
        )

    # --- grid ---
    cards = [card(p, labels, i) for i, p in enumerate(photos)]

    # --- about portrait ---
    portrait = ""
    if m["portraits"]:
        p = m["portraits"][0]
        portrait = f"""              <picture>
                <source type="image/webp" srcset="{srcset(p, 'webp')}" sizes="(min-width:900px) 40vw, 92vw" />
                <img
                  src="{GAL}/{p['id']}-{p['fallback']}.jpg"
                  width="{p['w']}"
                  height="{p['h']}"
                  alt="Muhammad Azeem, photographer and software engineer, in Lahore"
                  loading="lazy"
                  decoding="async"
                  style="background-color:{p['color']}"
                />
              </picture>"""

    return {
        "hero": "\n".join(hero),
        "stats": "\n".join(stats),
        "marquee": marquee,
        "chips": "\n".join(chips),
        "gallery": "\n".join(cards),
        "portrait": portrait,
    }


def inject(html, name, body):
    pat = re.compile(
        rf"(<!-- {name}:start -->).*?(<!-- {name}:end -->)", re.DOTALL
    )
    if not pat.search(html):
        raise SystemExit(f"marker <!-- {name}:start --> not found in index.html")
    return pat.sub(lambda mm: f"{mm.group(1)}\n{body}\n{' ' * 10}{mm.group(2)}", html, count=1)


def main():
    with open(MANIFEST) as f:
        m = json.load(f)

    parts = build(m)
    with open(PAGE) as f:
        html = f.read()

    for name, body in parts.items():
        html = inject(html, name, body)

    with open(PAGE, "w") as f:
        f.write(html)

    print(f"rendered {len(m['photos'])} photos into index.html")
    print(f"  categories : {', '.join(c['label'] for c in m['categories'])}")
    print(f"  hero slides: {len([h for h in HERO if h in {p['id'] for p in m['photos']}])}")
    print(f"  page size  : {os.path.getsize(PAGE) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
