import { put, list } from '@vercel/blob';
import { data } from './data';
import { elo } from './elo';

const ids = ['Human', ...data.systems.map((s) => s.id)];
const hasBlob = !!process.env.BLOB_READ_WRITE_TOKEN;
const mem = globalThis.__votes || (globalThis.__votes = []); // dev fallback only

export async function addVote(v) {
  if (!hasBlob) { mem.push(v); return; }
  await put(`votes/${v.ts}-${Math.random().toString(36).slice(2, 7)}__${v.task}__${v.a}__${v.b}__${v.win}.txt`, '1',
    { access: 'public', addRandomSuffix: false, contentType: 'text/plain' });
}

export async function readVotes() {
  if (!hasBlob) return mem;
  const out = []; let cursor;
  do {
    const r = await list({ prefix: 'votes/', limit: 1000, cursor });
    for (const b of r.blobs) {
      const [head, task, a, bb, win] = b.pathname.replace(/^votes\//, '').replace(/\.txt$/, '').split('__');
      out.push({ ts: Number(head.split('-')[0]), task, a, b: bb, win });
    }
    cursor = r.hasMore ? r.cursor : undefined;
  } while (cursor);
  return out;
}

export async function board() {
  const votes = await readVotes();
  return { total: votes.length, rows: elo(votes, ids) };
}
