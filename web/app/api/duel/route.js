import { data } from '../../../lib/data';
import { board } from '../../../lib/votes';
export const dynamic = 'force-dynamic';

const pick = (a) => a[Math.floor(Math.random() * a.length)];
const textOf = (task, id) => id === 'Human' ? data.tasks.find((t) => t.id === task).human
  : data.outputs.find((o) => o.task === task && o.system === id).text;

export async function GET() {
  const task = pick(data.tasks);
  const sys = data.systems.map((s) => s.id);
  let a = Math.random() < 0.6 ? 'Human' : pick(sys);
  let b = pick(sys.filter((s) => s !== a));
  if (Math.random() < 0.5) [a, b] = [b, a];
  const pid = Buffer.from(JSON.stringify({ t: task.id, a, b })).toString('base64url');
  return Response.json({ pid, prompt: task.prompt, a: textOf(task.id, a), b: textOf(task.id, b), ...(await board()) });
}
