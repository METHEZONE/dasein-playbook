import Link from 'next/link';
// Same paper, ink and top bar as the home page, for /duel and /bench.
export default function Shell({ children }) {
  return (<main className="ds tool">
    <div className="grain" aria-hidden="true" />
    <header className="top">
      <Link href="/" className="mark"><span className="o" aria-hidden="true" />Dasein</Link>
      <nav><Link href="/duel">Duel &#8599;</Link><Link href="/bench">Bench &#8599;</Link><a href="/dasein-bench.pdf">Report &#8599;</a></nav>
    </header>
    <div className="page">{children}</div>
    <p className="mono foot">Dasein, Heidegger&rsquo;s word for being-in-the-world.<br />Built at c0mpiled-18, Taipei. Part of <a href="https://ring.heyarca.app">Arca</a>.</p>
  </main>);
}
