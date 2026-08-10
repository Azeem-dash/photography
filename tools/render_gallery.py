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
SITEMAP = os.path.join(ROOT, "sitemap.xml")
GAL = "assets/gallery"
SITE = "https://photo-by-azeem.netlify.app"

# Editorial intros for the collection pages, keyed by category id and shown
# under the numbered title. Two or three sentences, in the site's own voice.
COLLECTIONS = {
    "macro": (
        "Stop walking and look closer: a watch dial becomes terrain, a ring "
        "borrows a minaret for its bokeh. Small things, photographed as if "
        "they mattered — because up close, they do."
    ),
    "golden": (
        "The hour when Lahore's dust turns the light to honey. Rickshaws, "
        "freight trucks and bare branches, all briefly gilded — most of these "
        "were taken on the way to somewhere else."
    ),
    "architecture": (
        "Domes, facades, iron lattice and the odd violet sky — the city "
        "holding still. These buildings carry centuries in one skyline, and I "
        "keep trying to fit them into a phone frame."
    ),
    "pilgrimage": (
        "Makkah and Madinah, 2026. Photographs made between prayers — the "
        "Kaaba at night, the courtyards at noon, a Qur'an held open beneath "
        "the striped arches of Al-Masjid an-Nabawi."
    ),
    "nature": (
        "Wildflowers on road verges, rain on petals, grass against the sun. "
        "Nothing exotic — just proof that the green world keeps going about "
        "its business a metre from the traffic."
    ),
    "rides": (
        "Motorcycles, mostly mine, photographed wherever the road stopped "
        "being a road. Fuel stops, pine forests, riverbeds — the machine is "
        "the excuse; the places are the point."
    ),
    "mountains": (
        "The long road north out of the plains — deodar forests, glacial "
        "rubble, wooden houses, valleys that make the bike feel very small. "
        "Northern Pakistan, in the frames I managed to stop for."
    ),
    "street": (
        "Lahore at street level: rickshaws, wet asphalt, heavy skies, the "
        "walled city waking up early. The kind of pictures you only get by "
        "being out in it."
    ),
}

# Frames good enough to carry a full-bleed hero, chosen by eye. The order
# matters: the first slide is the site's first impression, so it must be a
# bright frame that shows the photography instantly -- never a night shot.
HERO = ["100", "97", "img_0772", "67"]

# The hero is object-fit: cover and never shown at full resolution, so anything
# past 1600w is invisible weight (the 2400w rung alone is ~1MB per frame).
HERO_MAX_W = 1600

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


def srcset(p, ext, base=""):
    return ", ".join(f"{base}{GAL}/{p['id']}-{w}.{ext} {w}w" for w in p["widths"])


def card(p, labels, i, eager=EAGER, sizes=None, base="", note=None):
    """One gallery card. `base` prefixes asset URLs ("" on the homepage, "/"
    on nested collection pages). `note` is a visible figcaption index -- the
    collection pages show title/caption in the flow instead of on hover."""
    sizes = sizes or "(min-width:1500px) 22vw, (min-width:1100px) 30vw, (min-width:720px) 45vw, 92vw"
    full = f"{base}{GAL}/{p['id']}-{max(p['widths'])}.webp"
    fb = f"{base}{GAL}/{p['id']}-{p['fallback']}.jpg"
    lazy = "eager" if i < eager else "lazy"
    prio = "high" if i < eager else "auto"
    is_hd = max(p["widths"]) >= 1600

    figcaption = ""
    if note is not None:
        cap = f'<span class="card__note-cap">{esc(p["caption"])}</span>' if p.get("caption") else ""
        figcaption = f"""
              <figcaption class="card__note">
                <span class="card__note-n">{note:02d}</span>
                <span class="card__note-t">{esc(p['title'])}</span>
                {cap}
              </figcaption>"""

    # width/height are the real pixel dimensions -- the browser reserves the
    # correct box before the file arrives, so nothing shifts as images land.
    caption = f'\n              data-caption="{esc(p["caption"])}"' if p.get("caption") else ""
    return f"""            <figure
              class="card"
              data-id="{p['id']}"
              data-cat="{p['category']}"
              data-cat-label="{esc(labels[p['category']])}"
              data-title="{esc(p['title'])}"{caption}
              data-full="{full}"
              data-w="{p['w']}"
              data-h="{p['h']}"
            >
              <button class="card__media" type="button" aria-label="Open &quot;{esc(p['title'])}&quot; full size">
                <picture>
                  <source type="image/avif" srcset="{srcset(p, 'avif', base)}" sizes="{sizes}" />
                  <source type="image/webp" srcset="{srcset(p, 'webp', base)}" sizes="{sizes}" />
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
              </button>{figcaption}
            </figure>"""


def build(m):
    labels = {c["id"]: c["label"] for c in m["categories"]}
    photos = m["photos"]
    by_id = {p["id"]: p for p in photos}

    # --- hero slides ---
    # All four slides sit inside the viewport, so loading="lazy" would not hold
    # any of them back -- they would all download up front for ~3MB of images the
    # visitor cannot see yet. Only the first slide gets a real srcset; the rest
    # carry data-srcset and are hydrated by main.js one rotation ahead of when
    # each is shown. Hydration sets srcset only (never src), so the browser
    # resolves exactly one candidate per slide.
    hero = []
    preload = ""
    for n, hid in enumerate(HERO):
        p = by_id.get(hid)
        if not p:
            continue
        hw = [w for w in p["widths"] if 800 <= w <= HERO_MAX_W] or [
            min(p["widths"], key=lambda w: abs(w - HERO_MAX_W))
        ]

        def hero_ss(ext):
            return ", ".join(f"{GAL}/{p['id']}-{w}.{ext} {w}w" for w in hw)

        fb = f"{GAL}/{p['id']}-{p['fallback']}.jpg"

        if n == 0:
            avif = f'srcset="{hero_ss("avif")}" sizes="100vw"'
            img = f'src="{fb}" srcset="{hero_ss("webp")}" sizes="100vw" fetchpriority="high"'
            preload = (
                f'<link rel="preload" as="image" type="image/avif" '
                f'imagesrcset="{hero_ss("avif")}" imagesizes="100vw" fetchpriority="high" />'
            )
        else:
            avif = f'data-srcset="{hero_ss("avif")}" sizes="100vw"'
            img = f'data-srcset="{hero_ss("webp")}" sizes="100vw"'

        hero.append(
            f"""          <div class="hero__slide{' is-active' if n == 0 else ''}">
            <picture>
              <source type="image/avif" {avif} />
              <img
                {img}
                width="{p['w']}"
                height="{p['h']}"
                alt=""
                decoding="async"
                style="background-color:{p['color']}"
              />
            </picture>
          </div>"""
        )

    # --- stats ---
    hd = sum(1 for p in photos if max(p["widths"]) >= 1600)
    stats = []
    for n, label in [
        (len(photos), "Photographs"),
        (len(m["categories"]), "Collections"),
        (hd, "Full-res frames"),
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
                <source type="image/avif" srcset="{srcset(p, 'avif')}" sizes="(min-width:900px) 40vw, 92vw" />
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

    # --- collections index (homepage) ---
    cindex = []
    for n, c in enumerate(m["categories"], 1):
        cindex.append(
            f"""            <li>
              <a class="cindex__link" href="/collections/{c['id']}/">
                <span class="cindex__n">{n:02d}</span>
                <span class="cindex__t">{esc(c['label'])}</span>
                <span class="cindex__count">{counts[c['id']]} photographs</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="15" height="15" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </a>
            </li>"""
        )

    return {
        "hero": "\n".join(hero),
        "heropreload": f"    {preload}",
        "stats": "\n".join(stats),
        "marquee": marquee,
        "chips": "\n".join(chips),
        "gallery": "\n".join(cards),
        "portrait": portrait,
        "collectionsindex": "\n".join(cindex),
    }


def collection_page(m, cid, num, labels):
    """A full standalone page for one collection, sharing the site's CSS/JS."""
    label = labels[cid]
    photos = [p for p in m["photos"] if p["category"] == cid]
    intro = COLLECTIONS.get(cid, "")
    cover = photos[0]
    og = f"{SITE}/{GAL}/{cover['id']}-{cover['fallback']}.jpg"
    url = f"{SITE}/collections/{cid}/"

    ids = [c["id"] for c in m["categories"]]
    nxt = ids[(ids.index(cid) + 1) % len(ids)]
    nxt_num = ids.index(nxt) + 1

    cards = "\n".join(
        card(p, labels, i, eager=2,
             sizes="(min-width:1100px) 44vw, 92vw", base="/", note=i + 1)
        for i, p in enumerate(photos)
    )

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />

    <title>{esc(label)} — Photo by Azeem</title>
    <meta name="description" content="{esc(intro)}" />
    <meta name="author" content="Muhammad Azeem" />
    <meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0b0b0c" />
    <meta name="theme-color" media="(prefers-color-scheme: light)" content="#faf9f7" />
    <link rel="canonical" href="{url}" />

    <meta property="og:type" content="website" />
    <meta property="og:url" content="{url}" />
    <meta property="og:title" content="{esc(label)} — Photo by Azeem" />
    <meta property="og:description" content="{esc(intro)}" />
    <meta property="og:image" content="{og}" />
    <meta name="twitter:card" content="summary_large_image" />

    <link rel="icon" href="/brand/logo.png" />
    <link rel="apple-touch-icon" href="/brand/logo.png" />

    <link rel="preload" href="/assets/fonts/instrument-serif.woff2" as="font" type="font/woff2" crossorigin />
    <link rel="preload" href="/assets/fonts/inter-var.woff2" as="font" type="font/woff2" crossorigin />
    <link rel="stylesheet" href="/assets/css/main.css" />

    <script>
      document.documentElement.classList.add('js');
      try {{
        const s = localStorage.getItem('pba-theme');
        const t = s || (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark');
        document.documentElement.dataset.theme = t;
        if (s) {{
          const c = t === 'light' ? '#faf9f7' : '#0b0b0c';
          document.querySelectorAll('meta[name="theme-color"]').forEach((m) => {{ m.content = c; }});
        }}
      }} catch (e) {{}}
    </script>
  </head>

  <body>
    <a class="skip" href="#photos">Skip to photographs</a>

    <header class="header">
      <div class="header__inner">
        <a class="wordmark" href="/" aria-label="Photo by Azeem, home">
          Photo by Azeem
          <span>Lahore, Pakistan</span>
        </a>

        <nav class="nav" aria-label="Primary">
          <a class="nav__link" href="/#work">Gallery</a>
          <a class="nav__link is-active" href="/#collections">Collections</a>
          <a class="nav__link" href="/#about">About</a>
          <a class="nav__link" href="/#contact">Contact</a>
        </nav>

        <div class="header__actions">
          <button class="icon-btn theme-toggle" type="button" aria-label="Toggle colour theme">
            <svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />
            </svg>
            <svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
              <circle cx="12" cy="12" r="4.2" />
              <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" stroke-linecap="round" />
            </svg>
          </button>

          <button class="icon-btn nav-toggle" type="button" aria-label="Toggle menu" aria-expanded="false">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
              <path d="M4 7h16M4 12h16M4 17h16" stroke-linecap="round" />
            </svg>
          </button>
        </div>
      </div>
    </header>

    <main id="top">
      <section class="section chead" id="photos">
        <div class="shell">
          <p class="eyebrow">Collection {num:02d} &middot; {len(photos)} photographs</p>
          <h1 class="display section__title chead__title">{esc(label)}</h1>
          <p class="lede">{esc(intro)}</p>
        </div>
      </section>

      <section class="section section--tight">
        <div class="shell">
          <div class="grid grid--flow">
{cards}
          </div>

          <div class="cnext">
            <a class="contact__cta" href="/collections/{nxt}/">
              Next &mdash; {nxt_num:02d} {esc(labels[nxt])}
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" width="15" height="15" aria-hidden="true">
                <path d="M5 12h14M13 6l6 6-6 6" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </a>
          </div>
        </div>
      </section>
    </main>

    <footer class="footer">
      <div class="shell footer__inner">
        <span>&copy; <span id="year">2026</span> Muhammad Azeem &mdash; all photographs are my own.</span>
        <span>
          <a href="/">Home</a> &middot;
          <a href="https://github.com/Azeem-dash/photography" target="_blank" rel="noopener noreferrer">Source on GitHub</a>
        </span>
      </div>
    </footer>

    <div class="lb" role="dialog" aria-modal="true" aria-label="Photograph viewer" aria-hidden="true">
      <div class="lb__bar">
        <span class="lb__count">1 / 1</span>
        <button class="lb__share" type="button" aria-label="Copy link to this photograph">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" aria-hidden="true">
            <path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5" stroke-linecap="round" stroke-linejoin="round" />
            <path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="lb__share-hint" aria-hidden="true">Link copied</span>
        </button>
        <button class="lb__close" type="button" aria-label="Close viewer">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M6 6l12 12M18 6L6 18" stroke-linecap="round" />
          </svg>
        </button>
      </div>

      <div class="lb__stage">
        <div class="lb__spin" aria-hidden="true"></div>
        <img class="lb__img" alt="" />

        <button class="lb__nav lb__nav--prev" type="button" aria-label="Previous photograph">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M15 5l-7 7 7 7" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
        <button class="lb__nav lb__nav--next" type="button" aria-label="Next photograph">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">
            <path d="M9 5l7 7-7 7" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </button>
      </div>

      <div class="lb__foot">
        <span class="lb__title"></span>
        <span class="lb__cat"></span>
        <span class="lb__caption"></span>
        <span class="lb__dim"></span>
      </div>
    </div>

    <script src="/assets/js/main.js" defer></script>
  </body>
</html>
"""


def write_sitemap(m):
    urls = [f"""  <url>
    <loc>{SITE}/</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>"""]
    for c in m["categories"]:
        urls.append(f"""  <url>
    <loc>{SITE}/collections/{c['id']}/</loc>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")
    with open(SITEMAP, "w") as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(urls)
            + "\n</urlset>\n"
        )


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

    # --- collection pages + sitemap ---
    labels = {c["id"]: c["label"] for c in m["categories"]}
    for n, c in enumerate(m["categories"], 1):
        out = os.path.join(ROOT, "collections", c["id"])
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "index.html"), "w") as f:
            f.write(collection_page(m, c["id"], n, labels))
    write_sitemap(m)

    print(f"rendered {len(m['photos'])} photos into index.html")
    print(f"  categories : {', '.join(c['label'] for c in m['categories'])}")
    print(f"  hero slides: {len([h for h in HERO if h in {p['id'] for p in m['photos']}])}")
    print(f"  page size  : {os.path.getsize(PAGE) / 1024:.0f} KB")
    print(f"  collections: {len(m['categories'])} pages + sitemap")


if __name__ == "__main__":
    main()
