import { data, sysById } from '../../lib/data';
import { board } from '../../lib/votes';
import { BRAND } from '../../lib/brand';
import Logo from '../Logo';
export const dynamic = 'force-dynamic';

const pct = (v) => Math.round(v * 100);
export default async function Bench() {
  const b = await board().catch(() => ({ rows: [] }));
  const fooled = Object.fromEntries(b.rows.map((r) => [r.id, r]));
  const rows = [...data.bench].sort((a, c) => c.tell_score - a.tell_score);
  return (<>
    <p className="kick mono in" style={{ '--i': 0 }}>The bench</p>
    <h1 className="in" style={{ '--i': 1 }}>{BRAND} Bench</h1>
    <p className="sub in" style={{ '--i': 2 }}>Six systems, one author, three tasks. Scored on how much it sounds like the person, whether its specifics are real, and how much it reads like an AI.</p>
    <div className="scroll in" style={{ '--i': 3 }}><table className="rows"><thead><tr><th>#</th><th>System</th><th className="num">{BRAND}-score</th><th className="num">Grounding</th><th className="num">AI-isms /100w</th><th className="num">Independent judge</th><th className="num">Fooled humans</th></tr></thead><tbody>
      {rows.map((r, i) => { const s = sysById[r.system]; const f = fooled[r.system]; return (
        <tr key={r.system} className={s.vendor === 'tell' ? 'me' : ''}>
          <td>{i + 1}</td>
          <td><span className="nm"><Logo vendor={s.vendor} />{s.name}</span></td>
          <td className="num"><span className="bar" style={{ width: r.tell_score * 48 }} />{pct(r.tell_score)}</td>
          <td className="num">{r.grounding == null ? "-" : pct(r.grounding) + "%"}</td>
          <td className="num">{(r.slop_per_100w ?? r.slop ?? 0).toFixed(1)}</td>
          <td className="num">{r.headline_qwen27b_rubric == null ? '-' : pct(r.headline_qwen27b_rubric)}</td>
          <td className="num">{f && f.picked != null ? pct(f.picked) + '%' : '-'}</td></tr>); })}
    </tbody></table></div>
      {data.pairwise_summary && <p className="note">Blind reads-more-human check against the same-context baselines: {Object.values(data.pairwise_summary).map((x) => `${x.dasein_wins}/${x.n}`).join(' and ')}. Dasein vs same-context Claude and GPT, wins out of 12. The intervals include 50%, so neither side wins on this check; the reward-model and independent-judge leads are the claim, not this.</p>}
    {data.mock && <p className="note">Sample numbers until the final eval run lands. Fooled humans is live from the duel votes.</p>}
    <section className="sec"><p className="kick mono">Method</p>
      <div className="m3">
        <div><b>1. {BRAND}-score</b>A reward model trained on the author's own writing against generic AI text. It scores how close a text is to the author's voice, 0 to 100.</div>
        <div><b>2. Grounding</b>Every specific in a text (a name, a place, a time, a claim) is checked against the author's memory: ring recordings, notifications, messages, people graph. Share supported.</div>
        <div><b>3. AI-isms</b>Matches against a slop lexicon per 100 words: stock openers, hedged balance, tidy closers. Lower is better.</div>
      </div>
      <p>The same prompt goes to every system. Outputs are scored automatically, then humans vote blind in the <a href="/duel">duel</a>: pick which text a real person wrote.</p>
      {data.paper_url && <p><a className="mono next" href={data.paper_url}>Read the report &rarr;</a></p>}
    </section>
  </>);
}
