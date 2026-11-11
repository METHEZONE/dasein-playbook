'use client';
import { useEffect, useRef } from 'react';
import { makeRing } from '../lib/ring';

// Drives the scroll story: every [data-scene] gets a smoothed --p in 0..1.
// sticky scenes: progress through the pinned stretch. flow scenes: progress as they enter.
export function Scroller() {
  useEffect(() => {
    const els = [...document.querySelectorAll('[data-scene]')];
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const cur = new Map(els.map((e) => [e, 0]));
    const clamp = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);
    const target = (e) => {
      const r = e.getBoundingClientRect(), vh = innerHeight;
      if (e.dataset.scene === 'sticky') return clamp(-r.top / Math.max(1, r.height - vh));
      return clamp((vh - r.top) / (vh * 0.5 + r.height * 0.6));
    };
    let raf = 0;
    const tick = () => {
      raf = 0; let moving = false;
      for (const e of els) {
        const t = reduced ? 1 : target(e);
        let p = cur.get(e);
        p += (t - p) * 0.14; // soft follow, like ring's spring
        if (Math.abs(t - p) < 0.0005) p = t; else moving = true;
        cur.set(e, p);
        e.style.setProperty('--p', p.toFixed(4));
      }
      if (moving) raf = requestAnimationFrame(tick);
    };
    const kick = () => { if (!raf) raf = requestAnimationFrame(tick); };
    addEventListener('scroll', kick, { passive: true });
    addEventListener('resize', kick);
    document.documentElement.classList.add('js');
    kick();
    return () => { removeEventListener('scroll', kick); removeEventListener('resize', kick); cancelAnimationFrame(raf); };
  }, []);
  return null;
}

// The Arca ring, in ink glyphs, the same renderer as ring.heyarca.app. Tilts and recedes with the hero's --p.
export function Ring() {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current, ctx = cv.getContext('2d'), draw = makeRing();
    const scene = cv.closest('[data-scene]');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    let W = 0, H = 0, dpr = 1, raf = 0, spin = 0, last = performance.now(), visible = true;
    const fit = () => {
      dpr = Math.min(devicePixelRatio || 1, 2); W = cv.clientWidth; H = cv.clientHeight;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    };
    const frame = (ms) => {
      const dt = Math.min(0.05, (ms - last) / 1000); last = ms;
      const p = parseFloat(getComputedStyle(scene).getPropertyValue('--p')) || 0;
      spin += dt * 0.32;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      const rad = Math.min(W, H) * 0.42 * (1 - p * 0.35);
      const cw = Math.max(2.4, Math.min(6, rad / 16)), ch = cw * 1.55;
      draw(ctx, W / 2, H / 2, rad, 1.1 + p * 0.5, 0.35, cw, ch, dpr, 1 - p * 0.9, spin);
      if (!reduced && visible) raf = requestAnimationFrame(frame);
    };
    fit();
    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      if (visible && !raf && !reduced) { last = performance.now(); raf = requestAnimationFrame(frame); }
      if (!visible) { cancelAnimationFrame(raf); raf = 0; }
    });
    io.observe(cv);
    const onR = () => { fit(); if (reduced) frame(performance.now()); };
    addEventListener('resize', onR);
    raf = requestAnimationFrame(frame);
    return () => { io.disconnect(); removeEventListener('resize', onR); cancelAnimationFrame(raf); };
  }, []);
  return <canvas ref={ref} className="ring" aria-hidden="true" />;
}
