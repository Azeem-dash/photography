/* Photo by Azeem — all site behaviour. No dependencies. */
(() => {
  'use strict';

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* --- theme ------------------------------------------------------------ */
  const root = document.documentElement;
  const setTheme = (t) => {
    root.dataset.theme = t;
    try { localStorage.setItem('pba-theme', t); } catch {}
  };
  $('.theme-toggle')?.addEventListener('click', () =>
    setTheme(root.dataset.theme === 'light' ? 'dark' : 'light')
  );

  /* --- header + mobile nav ---------------------------------------------- */
  const header = $('.header');
  const nav = $('.nav');
  const navToggle = $('.nav-toggle');

  navToggle?.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    navToggle.setAttribute('aria-expanded', String(open));
  });
  $$('.nav__link').forEach((a) =>
    a.addEventListener('click', () => {
      nav.classList.remove('is-open');
      navToggle?.setAttribute('aria-expanded', 'false');
    })
  );

  const onScroll = () => header?.classList.toggle('is-stuck', scrollY > 24);
  addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  /* --- active section in nav -------------------------------------------- */
  const sections = $$('main section[id]');
  if (sections.length) {
    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          $$('.nav__link').forEach((l) =>
            l.classList.toggle('is-active', l.getAttribute('href') === `#${e.target.id}`)
          );
        });
      },
      { rootMargin: '-45% 0px -50% 0px' }
    );
    sections.forEach((s) => spy.observe(s));
  }

  /* --- blur-up image loading -------------------------------------------- */
  // Each .card__img carries its LQIP as a background. Once the real file
  // decodes we fade it in on top, so there is never a blank box.
  const reveal = (img) => {
    img.classList.add('is-loaded');
    // drop the placeholder once the real pixels are painted
    setTimeout(() => { img.style.backgroundImage = ''; }, 700);
  };
  $$('.card__img').forEach((img) => {
    if (img.complete && img.naturalWidth) reveal(img);
    else img.addEventListener('load', () => reveal(img), { once: true });
  });

  /* --- scroll reveal ----------------------------------------------------- */
  const revealer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        e.target.classList.add('is-in');
        obs.unobserve(e.target);
      });
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.02 }
  );
  const watchReveal = (el, i = 0) => {
    if (reduced) return el.classList.add('is-in');
    el.style.transitionDelay = `${Math.min(i % 4, 3) * 70}ms`;
    revealer.observe(el);
  };
  $$('.card').forEach(watchReveal);

  /* --- skill bars -------------------------------------------------------- */
  const skills = $$('.skill__fill');
  if (skills.length) {
    const so = new IntersectionObserver(
      (entries, obs) => {
        entries.forEach((e) => {
          if (!e.isIntersecting) return;
          e.target.style.width = e.target.dataset.level + '%';
          obs.unobserve(e.target);
        });
      },
      { threshold: 0.4 }
    );
    skills.forEach((s) => so.observe(s));
  }

  /* --- hero slideshow ---------------------------------------------------- */
  const slides = $$('.hero__slide');

  // Slides 2..n ship without a src so they cannot compete with the first paint.
  // Pull them in once the page is idle -- long before the 6.5s rotation needs them.
  const hydrateHero = () => {
    $$('.hero__slide img[data-src]').forEach((img) => {
      img.srcset = img.dataset.srcset;
      img.src = img.dataset.src;
      delete img.dataset.src;
      delete img.dataset.srcset;
    });
  };
  if (document.readyState === 'complete') hydrateHero();
  else addEventListener('load', hydrateHero, { once: true });

  if (slides.length > 1 && !reduced) {
    let i = 0;
    setInterval(() => {
      slides[i].classList.remove('is-active');
      i = (i + 1) % slides.length;
      slides[i].classList.add('is-active');
      // restart the ken-burns drift on the newly shown frame
      const img = slides[i].querySelector('img');
      img.style.animation = 'none';
      void img.offsetWidth;
      img.style.animation = '';
    }, 6500);
  }

  /* ======================================================================
     Gallery: filtering + lightbox
     ====================================================================== */
  const grid = $('.grid');
  if (!grid) return;

  const cards = $$('.card', grid);
  const empty = $('.grid__empty');

  /* --- filters ----------------------------------------------------------- */
  // `visible` is the list the lightbox pages through, so prev/next always
  // respects the active filter rather than jumping to a hidden photo.
  let visible = cards.slice();

  const applyFilter = (cat) => {
    visible = [];
    cards.forEach((c) => {
      const show = cat === 'all' || c.dataset.cat === cat;
      c.classList.toggle('is-hidden', !show);
      if (show) visible.push(c);
    });
    if (empty) empty.hidden = visible.length > 0;

    // re-run the reveal animation so filtered-in cards animate rather than pop
    if (!reduced) {
      visible.forEach((c, i) => {
        c.classList.remove('is-in');
        c.style.transitionDelay = `${Math.min(i, 8) * 45}ms`;
      });
      requestAnimationFrame(() =>
        requestAnimationFrame(() => visible.forEach((c) => c.classList.add('is-in')))
      );
    }
  };

  $$('.chip').forEach((chip) =>
    chip.addEventListener('click', () => {
      $$('.chip').forEach((c) => c.setAttribute('aria-pressed', String(c === chip)));
      applyFilter(chip.dataset.filter);
    })
  );

  /* --- lightbox ---------------------------------------------------------- */
  const lb = $('.lb');
  const lbImg = $('.lb__img');
  const lbTitle = $('.lb__title');
  const lbCat = $('.lb__cat');
  const lbDim = $('.lb__dim');
  const lbCount = $('.lb__count');

  let idx = 0;
  let lastFocus = null;

  const load = (card) => {
    const full = card.dataset.full;
    lbImg.classList.remove('is-ready');
    lb.classList.add('is-loading');

    const pre = new Image();
    pre.src = full;
    pre.decode()
      .catch(() => {})
      .then(() => {
        lbImg.src = full;
        lbImg.alt = card.dataset.title || '';
        lbImg.classList.add('is-ready');
        lb.classList.remove('is-loading');
      });

    lbTitle.textContent = card.dataset.title || '';
    lbCat.textContent = card.dataset.catLabel || '';
    lbDim.textContent = `${card.dataset.w} × ${card.dataset.h}`;
    lbCount.textContent = `${visible.indexOf(card) + 1} / ${visible.length}`;
  };

  // Warm the neighbours so arrowing through the gallery feels instant.
  const prefetch = (i) => {
    [i - 1, i + 1].forEach((n) => {
      const c = visible[(n + visible.length) % visible.length];
      if (c) new Image().src = c.dataset.full;
    });
  };

  const open = (card) => {
    idx = visible.indexOf(card);
    if (idx < 0) return;
    lastFocus = document.activeElement;
    load(card);
    lb.classList.add('is-open');
    lb.setAttribute('aria-hidden', 'false');
    document.body.classList.add('is-locked');
    $('.lb__close').focus();
    prefetch(idx);
  };

  const close = () => {
    lb.classList.remove('is-open');
    lb.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('is-locked');
    lastFocus?.focus();
  };

  const go = (step) => {
    idx = (idx + step + visible.length) % visible.length;
    load(visible[idx]);
    prefetch(idx);
  };

  cards.forEach((card) => {
    const trigger = $('.card__media', card);
    trigger.addEventListener('click', (e) => {
      e.preventDefault();
      open(card);
    });
  });

  $('.lb__close').addEventListener('click', close);
  $('.lb__nav--prev').addEventListener('click', () => go(-1));
  $('.lb__nav--next').addEventListener('click', () => go(1));

  // click the backdrop (but not the photo or the controls) to dismiss
  lb.addEventListener('click', (e) => {
    if (e.target === lb || e.target.classList.contains('lb__stage')) close();
  });

  addEventListener('keydown', (e) => {
    if (!lb.classList.contains('is-open')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') go(-1);
    else if (e.key === 'ArrowRight') go(1);
    else if (e.key === 'Tab') {
      // keep focus inside the dialog while it is open
      const f = $$('button', lb);
      const first = f[0];
      const last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });

  // swipe to page on touch
  let x0 = null;
  lb.addEventListener('touchstart', (e) => { x0 = e.changedTouches[0].clientX; }, { passive: true });
  lb.addEventListener('touchend', (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0;
    if (Math.abs(dx) > 55) go(dx < 0 ? 1 : -1);
    x0 = null;
  }, { passive: true });
})();
