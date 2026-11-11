import { data } from '../../../lib/data';
import { addVote, board } from '../../../lib/votes';
export const dynamic = 'force-dynamic';

export async function POST(req) {
  try {
    const { pid, pick } = await req.json();
    const { t, a, b } = JSON.parse(Buffer.from(String(pid), 'base64url').toString());
    const ok = (id) => id === 'Human' || data.systems.some((s) => s.id === id);
    if (!ok(a) || !ok(b) || !data.tasks.some((x) => x.id === t) || !['a', 'b'].includes(pick)) throw 0;
    await addVote({ ts: Date.now(), task: t, a, b, win: pick === 'a' ? a : b });
    return Response.json({ reveal: { a, b, human: a === 'Human' ? 'a' : b === 'Human' ? 'b' : null }, ...(await board()) });
  } catch { return Response.json({ error: 'bad vote' }, { status: 400 }); }
}
