'use client';
import { useEffect, useState, useCallback } from 'react';
import Board from '../Board';
import Logo from '../Logo';
import { sysById } from '../../lib/data';

export default function Duel() {
  const [d, setD] = useState(null);
  const [res, setRes] = useState(null);
  const [board, setBoard] = useState(null);
  const [busy, setBusy] = useState(false);
  const next = useCallback(async () => {
    setRes(null);
    const j = await (await fetch('/api/duel', { cache: 'no-store' })).json();
    setD(j); setBoard({ total: j.total, rows: j.rows });
  }, []);
  useEffect(() => { next(); }, [next]);
  async function vote(pick) {
    if (res || busy) return; setBusy(true);
    try {
      const j = await (await fetch('/api/vote', { method: 'POST', body: JSON.stringify({ pid: d.pid, pick }) })).json();
      setRes({ pick, ...j }); setBoard({ total: j.total, rows: j.rows });
    } finally { setBusy(false); }
  }
  const who = (id) => id === 'Human' ? <><span className="o" aria-hidden="true" />A real person</> : <><Logo vendor={sysById[id].vendor} />{sysById[id].name}</>;
  const right = res && res.reveal.human && res.pick === res.reveal.human;
  return (<>
    <p className="kick mono in" style={{ '--i': 0 }}>The duel</p>
    <h1 className="in" style={{ '--i': 1 }}>Which one did a real person write?</h1>
    <p className="ask in" style={{ '--i': 2 }}><span className="mono">Prompt</span>{d ? `“${d.prompt}”` : ' '}</p>
    {d && <div className={'pick' + (res ? ' done' : '')} key={d.pid}>
      {['a', 'b'].map((k, i) => (
        <button key={k} style={{ '--i': 3 + i }}
          className={'opt in' + (res && res.reveal.human === k ? ' win' : '') + (res && res.pick === k ? ' mine' : '')}
          disabled={!!res || busy} onClick={() => vote(k)}>
          <span className="mono lbl">{k.toUpperCase()}{res && res.pick === k ? ' · your pick' : ''}</span>
          <span className="txt">{d[k]}</span>
          {res && <span className="mono who">{who(res.reveal[k])}</span>}
        </button>))}
    </div>}
    {!res && d && <p className="mono hint in" style={{ '--i': 5 }}>Tap the one a person wrote.</p>}
    {res && <div className="after">
      <p className="verdict">{res.reveal.human ? (right ? 'You spotted the human.' : 'Fooled. That one was a machine.') : 'Both were machines. Your pick still moved the ratings.'}</p>
      <button className="mono next" onClick={next}>Next duel &rarr;</button>
    </div>}
    <section className="sec">
      <p className="kick mono">Live leaderboard</p>
      <p className="sub">Elo from blind votes. Whoever gets picked as the human climbs.{board ? ` ${board.total} votes so far.` : ''}</p>
      {board && <Board board={board} />}
    </section>
  </>);
}
