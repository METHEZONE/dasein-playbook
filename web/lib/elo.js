// votes: [{ts,a,b,win}] win = id picked as "the human". Elo over all contestants, K=24.
export function elo(votes, ids) {
  const r = Object.fromEntries(ids.map((i) => [i, 1000]));
  const n = Object.fromEntries(ids.map((i) => [i, 0]));
  const fooled = Object.fromEntries(ids.map((i) => [i, 0]));
  for (const v of [...votes].sort((x, y) => x.ts - y.ts)) {
    if (!(v.a in r) || !(v.b in r)) continue;
    const lose = v.win === v.a ? v.b : v.a;
    const e = 1 / (1 + 10 ** ((r[lose] - r[v.win]) / 400));
    r[v.win] += 24 * (1 - e); r[lose] -= 24 * (1 - e);
    n[v.a]++; n[v.b]++; fooled[v.win]++;
  }
  return ids.map((id) => ({ id, elo: Math.round(r[id]), n: n[id], picked: n[id] ? fooled[id] / n[id] : null }))
    .sort((a, b) => b.elo - a.elo);
}
if (process.argv[1]?.endsWith('elo.js')) {
  const t = elo([{ ts: 1, a: 'Human', b: 'S1', win: 'Human' }, { ts: 2, a: 'S6', b: 'S1', win: 'S6' }], ['Human', 'S1', 'S6']);
  console.assert(t[0].elo > 1000 && t[2].id === 'S1', 'elo broken'); console.log(t);
}
