'use client';
import { useEffect, useRef } from 'react';
import { INK } from '../lib/ring';

// Hero: a human bust in ink glyphs, turning once per loop. It dissolves into the internet's words,
// collapses into a featureless average, then re-forms. Same language as lib/ring.js (z-buffered ASCII, ink on paper).
// The bust is procedural (smooth-unioned SDF primitives), so there is no mesh and no likeness to license.

const RAMP = ' .,:;-=+*#%@', CHARS = RAMP + 'abcdefghijklmnopqrstuvwxyz';
const WORDS = ('the of and to in is that for it as was with be by on not he this are or his from at which but have an had they you were their one all we can her has there been if more when will would who so no ' +
  'truly inspiring meaningful journey delve tapestry landscape vibrant testament seamless unlock elevate leverage robust thrilled excited humbled grateful honored passionate innovative ' +
  'like share subscribe comment reply thread post link click here read more follow update lol omg tbh imo edit source login home page search news video today world people time life love work').split(' ');
const T = 14, SEG = [4.2, 1.6, 2.6, 1.5, 1.9, 2.2]; // bust, ->words, words, ->blob, blob, ->bust

const smin = (a, b, k) => { const h = Math.max(k - Math.abs(a - b), 0) / k; return Math.min(a, b) - h * h * k * 0.25; };
const ell = (x, y, z, cx, cy, cz, rx, ry, rz) => (Math.hypot((x - cx) / rx, (y - cy) / ry, (z - cz) / rz) - 1) * Math.min(rx, ry, rz);
const cap = (x, y, z, ax, ay, az, bx, by, bz, r) => {
  const px = x - ax, py = y - ay, pz = z - az, dx = bx - ax, dy = by - ay, dz = bz - az;
  const h = Math.max(0, Math.min(1, (px * dx + py * dy + pz * dz) / (dx * dx + dy * dy + dz * dz)));
  return Math.hypot(px - dx * h, py - dy * h, pz - dz * h) - r;
};
// y up, face toward +z, about 2.1 units tall
function bust(x, y, z) {
  const ax = Math.abs(x);
  let d = ell(x, y, z, 0, 0.68, -0.04, 0.35, 0.4, 0.43);                  // cranium
  d = smin(d, ell(x, y, z, 0, 0.42, 0.07, 0.27, 0.4, 0.33), 0.12);        // face
  d = smin(d, ell(x, y, z, 0, 0.13, 0.17, 0.12, 0.1, 0.12), 0.12);        // chin
  d = smin(d, ell(ax, y, z, 0.13, 0.64, 0.35, 0.14, 0.04, 0.06), 0.06);   // brow
  d = -smin(-d, ell(ax, y, z, 0.14, 0.56, 0.4, 0.075, 0.045, 0.07), 0.05); // eye sockets
  d = smin(d, ell(x, y, z, 0, 0.44, 0.42, 0.05, 0.14, 0.11), 0.05);       // nose
  d = smin(d, ell(x, y, z, 0, 0.27, 0.36, 0.09, 0.03, 0.05), 0.04);       // lips
  d = smin(d, ell(ax, y, z, 0.35, 0.5, -0.03, 0.035, 0.11, 0.07), 0.04);  // ears
  d = smin(d, cap(x, y, z, 0, 0.3, -0.06, 0, -0.35, -0.1, 0.165), 0.1);   // neck
  d = smin(d, cap(ax, y, z, 0, -0.2, -0.1, 0.55, -0.5, -0.08, 0.13), 0.2); // trapezius
  d = smin(d, ell(ax, y, z, 0.62, -0.66, -0.06, 0.24, 0.22, 0.24), 0.18); // shoulders
  d = smin(d, ell(x, y, z, 0, -0.85, -0.02, 0.6, 0.45, 0.3), 0.2);        // chest
  return d;
}

function build(N, wide) {
  let s = 7; // mulberry32, so every visit gets the same figure
  const rnd = () => { s = (s + 0x6D2B79F5) | 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
  const A = new Float32Array(N * 3), nA = new Float32Array(N * 3), B = new Float32Array(N * 3), C = new Float32Array(N * 3), R = new Float32Array(N * 3);
  const dl = new Float32Array(N * 3), glyph = new Uint8Array(N), koff = new Float32Array(N);
  const e = 0.003;
  for (let i = 0; i < N;) {
    let x = rnd() * 2.1 - 1.05, y = rnd() * 2.2 - 1.0, z = rnd() * 1.3 - 0.62, gx = 0, gy = 0, gz = 0;
    const d0 = bust(x, y, z);
    if (Math.abs(d0) > 0.25) continue;
    // the ellipsoid distances are only approximate, so measure the shell in true units or the seams come out sparse
    if (Math.abs(d0) * 2 * e > 0.06 * Math.hypot(bust(x + e, y, z) - bust(x - e, y, z), bust(x, y + e, z) - bust(x, y - e, z), bust(x, y, z + e) - bust(x, y, z - e))) continue;
    for (let k = 0; k < 4; k++) { // walk onto the surface along the gradient
      const d = bust(x, y, z);
      gx = bust(x + e, y, z) - bust(x - e, y, z); gy = bust(x, y + e, z) - bust(x, y - e, z); gz = bust(x, y, z + e) - bust(x, y, z - e);
      const l = Math.hypot(gx, gy, gz) || 1; gx /= l; gy /= l; gz /= l;
      const st = d * 2 * e / l; x -= gx * st; y -= gy * st; z -= gz * st;
    }
    if (y < -1) continue; // the bust is cut at the chest
    A.set([x, y - 0.08, z], i * 3); nA.set([gx, gy, gz], i * 3);
    R.set([rnd() - 0.5, rnd() - 0.5, rnd() - 0.5], i * 3);
    const yn = (y + 1) / 2.15, r = rnd();
    dl.set([0.65 * (1 - yn) + 0.35 * r, rnd(), 0.6 * yn + 0.4 * r], i * 3); // head goes first, body returns first
    i++;
  }
  // blob: an even sphere, paired to bust points band by band so the collapse stays spatially coherent
  const fib = [...Array(N)].map((_, i) => { const y = 1 - (2 * i + 1) / N, r = Math.sqrt(1 - y * y), a = i * 2.39996323; return [r * Math.cos(a), y, r * Math.sin(a)]; });
  const band = Math.round(Math.sqrt(N) * 1.2);
  const order = (get) => {
    const ix = [...Array(N).keys()].sort((p, q) => get(p)[1] - get(q)[1]), out = [];
    for (let b = 0; b < N; b += band) out.push(...ix.slice(b, b + band).sort((p, q) => Math.atan2(get(p)[2], get(p)[0]) - Math.atan2(get(q)[2], get(q)[0])));
    return out;
  };
  const oa = order((i) => A.subarray(i * 3, i * 3 + 3)), of = order((i) => fib[i]);
  for (let k = 0; k < N; k++) { const f = fib[of[k]]; C.set([f[0] * 0.74, f[1] * 0.74 + 0.04, f[2] * 0.74], oa[k] * 3); }
  // words: a fifth of the points become letters; the rest thin out into a ghost of the figure
  for (let i = 0; i < N; i++) for (let j = 0; j < 3; j++) B[i * 3 + j] = A[i * 3 + j] * 1.25 + R[i * 3 + j] * 0.7;
  const pick = [...Array(N).keys()].sort(() => rnd() - 0.5);
  for (let p = 0, L = Math.floor(N * 0.075); p < L;) {
    const w = WORDS[Math.floor(rnd() * WORDS.length)], u = rnd() * 2 - 1, a = rnd() * 6.2832, rr = Math.cbrt(rnd()) * 1.25, q = Math.sqrt(1 - u * u);
    for (let k = 0; k < w.length && p < L; k++, p++) {
      const i = pick[p];
      B.set([rr * q * Math.cos(a) * wide, rr * u * 0.9, rr * q * Math.sin(a) * 1.15], i * 3);
      glyph[i] = CHARS.indexOf(w[k]); koff[i] = k - (w.length - 1) / 2;
    }
  }
  return { A, nA, B, C, R, dl, glyph, koff };
}

const ease = (u) => (u <= 0 ? 0 : u >= 1 ? 1 : u < 0.5 ? 4 * u * u * u : 1 - (-2 * u + 2) ** 3 / 2);

export default function HeroBust() {
  const ref = useRef(null);
  useEffect(() => {
    const cv = ref.current, ctx = cv.getContext('2d');
    const scene = cv.closest('[data-scene]');
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
    const small = innerWidth < 700, N = small ? 12000 : 15000;
    const { A, nA, B, C, R, dl, glyph, koff } = build(N, small ? 0.95 : 1.5);
    let W = 0, H = 0, dpr = 1, raf = 0, visible = true, atlas = null, cw = 5, ch = 8, cols = 0, rows = 0, S = 1;
    let zk = new Float32Array(0), lm = new Float32Array(0), al = new Float32Array(0), gl = new Uint8Array(0);
    const t0 = performance.now();
    const fit = () => {
      dpr = Math.min(devicePixelRatio || 1, 2); W = cv.clientWidth; H = cv.clientHeight;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      S = Math.min(H / 2.5, W / 2.2); cw = Math.max(3, Math.min(6, S / 42)); ch = cw * 1.55;
      cols = Math.ceil(W / cw); rows = Math.ceil(H / ch);
      const n = cols * rows; zk = new Float32Array(n); lm = new Float32Array(n); al = new Float32Array(n); gl = new Uint8Array(n);
      const gw = Math.ceil(cw * dpr), c = document.createElement('canvas'); c.width = gw * CHARS.length; c.height = Math.ceil(ch * dpr);
      const g = c.getContext('2d'); g.fillStyle = INK; g.textBaseline = 'middle'; g.textAlign = 'center';
      g.font = `${Math.round(ch * 0.92 * dpr)}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
      for (let i = 1; i < CHARS.length; i++) g.fillText(CHARS[i], i * gw + gw / 2, c.height / 2 + dpr * 0.5);
      atlas = { c, gw, gh: c.height };
    };
    const draw = (t, p) => {
      // which transition is live, and how far along
      let seg = 0, u = t; while (seg < 5 && u >= SEG[seg]) u -= SEG[seg++];
      u /= SEG[seg];
      const yaw = -0.9 + (6.2832 * t) / T, cy = Math.cos(yaw), sy = Math.sin(yaw), tilt = 0.1, ct = Math.cos(tilt), st = Math.sin(tilt);
      const K = 5, sc = S * (1 - p * 0.3), ox = W / 2, oy = H * 0.47, fade = 1 - p * 0.9;
      zk.fill(0);
      for (let i = 0, j = 0; i < N; i++, j += 3) {
        let a = 0, b = 0, c = 0, m = 0; // weights of bust, words, blob; m = mid-flight
        if (seg === 0) a = 1; else if (seg === 2) b = 1; else if (seg === 4) c = 1;
        else {
          const k = (seg - 1) / 2, v = ease(u * 1.7 - dl[j + k] * 0.7); m = Math.sin(v * 3.1416);
          if (seg === 1) { a = 1 - v; b = v; } else if (seg === 3) { b = 1 - v; c = v; } else { c = 1 - v; a = v; }
        }
        const sw = m * 0.16;
        const x = a * A[j] + b * B[j] + c * C[j] + sw * R[j], y = a * A[j + 1] + b * B[j + 1] + c * C[j + 1] + sw * R[j + 1], z = a * A[j + 2] + b * B[j + 2] + c * C[j + 2] + sw * R[j + 2];
        let X = x * cy + z * sy, Z = x * sy - z * cy, Y = y * ct - Z * st; Z = y * st + Z * ct; // view: +Z away from the eye
        const ooz = K / (Z + K);
        let col = Math.floor((ox + sc * ooz * X) / cw), row = Math.floor((oy - sc * ooz * Y) / ch);
        const letter = glyph[i] && b > 0.5;
        // solid shapes shade by their normal; blob normal is its own position
        let nx = a * nA[j] + c * C[j], ny = a * nA[j + 1] + c * (C[j + 1] - 0.04), nz = a * nA[j + 2] + c * C[j + 2];
        const nl = Math.hypot(nx, ny, nz) || 1; nx /= nl; ny /= nl; nz /= nl;
        const NX = nx * cy + nz * sy, NZ0 = nx * sy - nz * cy, NY = ny * ct - NZ0 * st, NZ = ny * st + NZ0 * ct;
        if (b < 0.4 && NZ > 0.12) continue; // back faces of a solid
        let key = ooz, alpha = 1, ink = 0.1 + 0.82 * (1 - Math.max(0, -0.5 * NX + 0.5 * NY - 0.7 * NZ)) ** 1.5;
        if (letter) { col += Math.round(koff[i] * (b - 0.5) * 2); key += 10; alpha = Math.min(1, 0.28 + 0.72 * (1.3 - Z) / 2.6) * (b - 0.5) * 2; }
        else if (b > 0) { ink *= 1 - 0.86 * b; alpha = 1 - (glyph[i] || i % 3 ? 1 : 0.8) * b; }
        if (a > 0) alpha *= 1 - a * (1 - Math.max(0, Math.min(1, (A[j + 1] + 1.06) / 0.4))); // the chest fades out, like a vignette
        if (alpha < 0.02) continue;
        if (col < 0 || col >= cols || row < 0 || row >= rows) continue;
        const q = row * cols + col;
        if (key > zk[q]) { zk[q] = key; lm[q] = ink; al[q] = alpha; gl[q] = letter ? glyph[i] : 0; }
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0); ctx.clearRect(0, 0, W, H);
      const { c: img, gw, gh } = atlas, x0 = (W - cols * cw) / 2;
      for (let r = 0, q = 0; r < rows; r++) for (let c = 0; c < cols; c++, q++) {
        if (!zk[q]) { // close pinholes in solid surfaces
          if (c && c < cols - 1 && zk[q - 1] && zk[q + 1] && !gl[q - 1] && !gl[q + 1] && al[q - 1] > 0.5 && al[q + 1] > 0.5) { lm[q] = lm[q - 1]; al[q] = al[q - 1]; gl[q] = 0; } else continue;
        }
        const g = gl[q] || Math.max(1, Math.min(RAMP.length - 1, Math.round(lm[q] * (RAMP.length - 1))));
        ctx.globalAlpha = al[q] * fade;
        ctx.drawImage(img, g * gw, 0, gw, gh, x0 + c * cw, r * ch, cw, ch);
      }
      ctx.globalAlpha = 1;
    };
    const frame = (ms) => {
      const p = parseFloat(getComputedStyle(scene).getPropertyValue('--p')) || 0;
      draw(reduced ? 1.6 : ((ms - t0) / 1000) % T, p);
      raf = !reduced && visible ? requestAnimationFrame(frame) : 0;
    };
    fit();
    const io = new IntersectionObserver(([e]) => {
      visible = e.isIntersecting;
      if (visible && !raf && !reduced) raf = requestAnimationFrame(frame);
      if (!visible) { cancelAnimationFrame(raf); raf = 0; }
    });
    io.observe(cv);
    const onR = () => { fit(); if (reduced) frame(0); };
    addEventListener('resize', onR);
    raf = requestAnimationFrame(frame);
    return () => { io.disconnect(); removeEventListener('resize', onR); cancelAnimationFrame(raf); };
  }, []);
  return <canvas ref={ref} className="ring" aria-hidden="true" />;
}
