import Link from 'next/link';
import vs from '../data/vs.json';
import Logo from './Logo';
import { Scroller } from './Story';
import HeroBust from './HeroBust';

// One page, one idea. Scenes: hero, the problem, where it comes from, the fix, the VS, a small way out.
const VOICES = ['a founder in Taipei', 'a nurse in Busan', 'a retired teacher in Ohio', 'a student in Lagos', 'a chef in Lyon', 'you'];
const SAME = 'Today was a truly inspiring day, full of meaningful connections.';

// deterministic "voices of the internet": wide spread, some in the tails
function dots(n) {
  let s = 7; const r = () => ((s = (s * 16807) % 2147483647) / 2147483647);
  return Array.from({ length: n }, () => {
    const g = (r() + r() + r() + r() - 2) * 1.35; // ~normal
    const x = Math.round(g * 210), y = Math.round((r() - 0.5) * 120);
    return { x, y, tail: Math.abs(x) > 190 ? 1 : 0 };
  });
}
const DOTS = dots(90);
// bell curve, sigma ~ 160 user units, centred at 500
const CURVE = 'M 40 220 ' + Array.from({ length: 93 }, (_, i) => {
  const x = 40 + i * 10, z = (x - 500) / 160;
  return `L ${x} ${(220 - 170 * Math.exp(-z * z / 2)).toFixed(1)}`;
}).join(' ');

const rv = (a, d, cls = '') => ({ className: ('rv ' + cls).trim(), style: { '--a': a, ...(d ? { '--d': d } : {}) } });

export default function Home() {
  return (
    <main className="ds">
      <Scroller />
      <div className="grain" aria-hidden="true" />
      <header className="top">
        <Link href="/" className="mark"><span className="o" aria-hidden="true" />Dasein</Link>
        <nav><Link href="/duel">Duel &#8599;</Link><a href="/dasein-bench.pdf">Report &#8599;</a></nav>
      </header>

      {/* 00 hero */}
      <section className="scene hero" data-scene="sticky">
        <div className="stage">
          <HeroBust />
          <div className="hero-t">
            <h1>AI has words.<br />It doesn&rsquo;t have a world.</h1>
            <p className="mono">Dasein &mdash; being-in-the-world</p>
          </div>
          <div className="cue mono" aria-hidden="true"><span />scroll</div>
        </div>
      </section>

      {/* 01 the problem */}
      <section className="scene s1" data-scene="sticky">
        <div className="stage">
          <p className="kick mono">01 &nbsp;The problem</p>
          <h2>AI writing sounds like nobody.</h2>
          <div className="rows">
            {VOICES.map((v, i) => (
              <div key={v} className="row" style={{ '--i': i }}>
                <span {...rv(0.12 + i * 0.07, 0, 'who mono')}>{v}</span>
                <span {...rv(0.14 + i * 0.07, 0, 'said')}>{SAME}</span>
              </div>
            ))}
          </div>
          <p {...rv(0.84, 0, 'cap')}>Six people. One sentence.</p>
        </div>
      </section>

      {/* 02 where it comes from */}
      <section className="scene s2" data-scene="sticky">
        <div className="stage">
          <p className="kick mono">02 &nbsp;Where it comes from</p>
          <h2>It learned the average<br />of the internet.</h2>
          <svg className="dist" viewBox="0 0 1000 260" aria-hidden="true">
            <line x1="40" y1="220.5" x2="960" y2="220.5" className="axis" />
            <line x1="500" y1="30" x2="500" y2="236" className="mean" />
            <g className="curve"><path d={CURVE} vectorEffect="non-scaling-stroke" /></g>
            {DOTS.map((d, i) => <circle key={i} cx="500" cy={130} r="2.4" style={{ '--x': d.x, '--y': d.y, '--tail': d.tail }} />)}
          </svg>
          <ol className="why">
            <li {...rv(0.14)}><b className="mono">Pretraining</b> learns what most people write.</li>
            <li {...rv(0.34)}><b className="mono">Sampling</b> cuts the tails, where individuality lives.</li>
            <li {...rv(0.52)}><b className="mono">Post-training</b> rewards the polished assistant. RL for code ignores voice.</li>
          </ol>
          <div {...rv(0.74, 0.14, 'noworld')}>
            <p className="big">And it has no world.</p>
            <p className="sub">No memories, no people, no stakes, no days of its own.</p>
          </div>
        </div>
      </section>

      {/* 03 the fix */}
      <section className="scene s3" data-scene="sticky">
        <div className="stage">
          <p className="kick mono">03 &nbsp;The fix</p>
          <h2>Give it yours.</h2>
          <div className="chain">
            <i className="wire" aria-hidden="true" />
            <div {...rv(0.16, 0, 'node')}>
              <svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="21" /><circle cx="24" cy="24" r="14" /><circle cx="24" cy="24" r="7" /></svg>
              <p className="mono">Your world</p>
              <p>An Arca ring and your phone capture real conversations, notifications and the people you meet.</p>
            </div>
            <div {...rv(0.4, 0, 'node')}>
              <svg viewBox="0 0 48 48" aria-hidden="true"><path d="M4 34 H44 M8 34 V28 M16 34 V24 M24 34 V14 M32 34 V24 M40 34 V28" /><path d="M24 6 l-4 -4 h8 z" className="fill" /></svg>
              <p className="mono">dasein-score</p>
              <p>A reward model that pays only for writing that is human and grounded in your real life.</p>
            </div>
            <div {...rv(0.64, 0, 'node')}>
              <svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="24" cy="24" r="12" /><path d="M24 4 V10 M24 38 V44 M4 24 H10 M38 24 H44" /><circle cx="24" cy="24" r="2.5" className="fill" /></svg>
              <p className="mono">An open model</p>
              <p>Post-trained against that reward, so it writes from your days instead of everyone&rsquo;s.</p>
            </div>
          </div>
        </div>
      </section>

      {/* 04 the VS */}
      <section className="vs" data-scene="flow">
        {vs.draft && <div hidden dangerouslySetInnerHTML={{ __html: '<!-- draft sample: hand-written VS, swap data/vs.json with real W2 outputs -->' }} />}
        <p className="kick mono">04 &nbsp;Same prompt</p>
        <p {...rv(0.02, 0, 'ask')}>&ldquo;{vs.prompt}&rdquo;</p>
        {vs.note && <p {...rv(0.06, 0, 'mono fair')}>{vs.note}</p>}
        <div className="duo">
          <article {...rv(0.08, 0.2, 'side ai')}>
            <header className="mono">{vs.ai.vendors.map((v) => <Logo key={v} vendor={v} />)}{vs.ai.label}</header>
            <p className="txt">{vs.ai.text}</p>
            {typeof vs.ai.score === 'number' && <footer className="mono">{vs.metric} <b>{vs.ai.score.toFixed(2)}</b></footer>}
          </article>
          <div className="versus mono" aria-hidden="true"><span>vs</span></div>
          <article {...rv(0.3, 0.2, 'side me')}>
            <header className="mono"><span className="o" aria-hidden="true" />{vs.dasein.label}</header>
            <p className="txt">{vs.dasein.text}</p>
            {typeof vs.dasein.score === 'number' && <footer className="mono">{vs.metric} <b>{vs.dasein.score.toFixed(2)}</b></footer>}
          </article>
        </div>
        <p {...rv(0.72, 0.16, 'cap end')}>Only one of them was there.</p>
      </section>

      {/* 05 out */}
      <section className="out">
        <nav className="mono"><Link href="/duel">Try the duel &rarr;</Link><a href="/dasein-bench.pdf">Read the report &rarr;</a></nav>
        <p className="mono foot">Dasein, Heidegger&rsquo;s word for being-in-the-world.<br />Built at c0mpiled-18, Taipei. Part of <a href="https://ring.heyarca.app">Arca</a>.</p>
      </section>
    </main>
  );
}
