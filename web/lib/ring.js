// ASCII ring renderer, copied from ring.heyarca.app /p/common.js so the two sites share one object.
export const INK = '#141414';
// ---- ASCII ring: a flat band torus, donut.c style, ink glyphs on paper ----
const RAMP = ' .,:;-=+*#%@';
const atlasCache = new Map();
function glyphAtlas(cw, chh, dpr) {
  const key = `${cw}x${chh}@${dpr}`;
  if (atlasCache.has(key)) return atlasCache.get(key);
  const c = document.createElement('canvas');
  c.width = Math.ceil(cw * dpr) * RAMP.length; c.height = Math.ceil(chh * dpr);
  const g = c.getContext('2d');
  g.fillStyle = INK; g.textBaseline = 'middle'; g.textAlign = 'center';
  g.font = `${Math.round(chh * 0.92 * dpr)}px ui-monospace, "SF Mono", Menlo, Consolas, monospace`;
  const W = Math.ceil(cw * dpr);
  for (let i = 1; i < RAMP.length; i++) g.fillText(RAMP[i], i * W + W / 2, c.height / 2 + dpr * 0.5);
  const a = { c, W, H: c.height };
  atlasCache.set(key, a);
  return a;
}

export function makeRing() {
  let zb = new Float32Array(0), lum = new Float32Array(0);
  // draws a ring of outer radius `rad` centred at (cx,cy) on ctx (which has dpr transform)
  return function draw(ctx, cx, cy, rad, rotA, rotB, cw, chh, dpr, alpha = 1, yaw = 0) {
    const cols = Math.ceil((rad * 2.3) / cw) | 1, rows = Math.ceil((rad * 2.3) / chh) | 1;
    const n = cols * rows;
    if (zb.length < n) { zb = new Float32Array(n); lum = new Float32Array(n); }
    zb.fill(0, 0, n);
    const R = 1, a = 0.13, b = 0.42, K2 = 5, K1 = (rad * K2) / (R + a + 0.05);
    const cA = Math.cos(rotA), sA = Math.sin(rotA), cB = Math.cos(rotB), sB = Math.sin(rotB), cC = Math.cos(yaw), sC = Math.sin(yaw);
    const lx = -0.45, ly = 0.75, lz = -0.48; // light from upper-left-front
    const dT = 0.11, dP = Math.min(0.04, cw / rad / 1.4);
    for (let t = 0; t < 6.2832; t += dT) {
      const ct = Math.cos(t), st = Math.sin(t);
      const x0 = R + a * ct, y0 = b * st;
      let nx0 = b * ct, ny0 = a * st; const nl = Math.hypot(nx0, ny0); nx0 /= nl; ny0 /= nl;
      for (let p = 0; p < 6.2832; p += dP) {
        const cp = Math.cos(p), sp = Math.sin(p);
        // ring axis = y. rotate about x by A (tilt), about y by yaw (tumble), about z by B (roll)
        let X = x0 * cp, Y = y0, Z = x0 * sp;
        let Nx = nx0 * cp, Ny = ny0, Nz = nx0 * sp;
        let y1 = Y * cA - Z * sA, z1 = Y * sA + Z * cA; Y = y1; Z = z1;
        y1 = Ny * cA - Nz * sA; z1 = Ny * sA + Nz * cA; Ny = y1; Nz = z1;
        let x1 = X * cC + Z * sC; z1 = -X * sC + Z * cC; X = x1; Z = z1;
        x1 = Nx * cC + Nz * sC; z1 = -Nx * sC + Nz * cC; Nx = x1; Nz = z1;
        x1 = X * cB - Y * sB; y1 = X * sB + Y * cB; X = x1; Y = y1;
        x1 = Nx * cB - Ny * sB; y1 = Nx * sB + Ny * cB; Nx = x1; Ny = y1;
        const ooz = 1 / (Z + K2);
        const col = Math.floor(cols / 2 + (K1 * ooz * X) / cw), row = Math.floor(rows / 2 - (K1 * ooz * Y) / chh);
        if (col < 0 || col >= cols || row < 0 || row >= rows) continue;
        const i = row * cols + col;
        if (ooz > zb[i]) { zb[i] = ooz; lum[i] = Nx * lx + Ny * ly + Nz * lz; }
      }
    }
    const A = glyphAtlas(cw, chh, dpr);
    const x0 = cx - (cols * cw) / 2, y0 = cy - (rows * chh) / 2;
    ctx.globalAlpha = alpha;
    for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) {
      const i = r * cols + c;
      if (!zb[i]) continue;
      // engraving logic: lit = sparse, shadow = dense ink
      const ink = 0.12 + 0.88 * (1 - Math.max(0, lum[i])) ** 1.4;
      const g = Math.max(1, Math.min(RAMP.length - 1, Math.round(ink * (RAMP.length - 1))));
      ctx.drawImage(A.c, g * A.W, 0, A.W, A.H, x0 + c * cw, y0 + r * chh, cw, chh);
    }
    ctx.globalAlpha = 1;
  };
}
