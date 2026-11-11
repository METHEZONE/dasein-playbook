import Logo from './Logo';
import { sysById } from '../lib/data';
export default function Board({ board }) {
  const max = Math.max(...board.rows.map((r) => r.elo)), min = Math.min(...board.rows.map((r) => r.elo)), span = Math.max(1, max - min);
  return (<div className="scroll"><table className="rows"><thead><tr><th>#</th><th>Writer</th><th className="num">Elo</th><th className="num">Human %</th><th className="num">Duels</th></tr></thead><tbody>
    {board.rows.map((r, i) => { const s = sysById[r.id]; return (
      <tr key={r.id} className={r.id === 'Human' || s?.vendor === 'tell' ? 'me' : ''}>
        <td>{i + 1}</td>
        <td><span className="nm">{s ? <Logo vendor={s.vendor} /> : <span className="o" aria-hidden="true" />}{r.id === 'Human' ? 'A real person' : s.name}</span></td>
        <td className="num"><span className="bar" style={{ width: 8 + ((r.elo - min) / span) * 40 }} />{r.elo}</td>
        <td className="num">{r.picked == null ? '-' : Math.round(r.picked * 100) + '%'}</td>
        <td className="num">{r.n}</td></tr>); })}
  </tbody></table></div>);
}
