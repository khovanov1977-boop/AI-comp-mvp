import Link from "next/link";

export default function HomePage() {
  return (
    <main className="shell">
      <div className="topbar">
        <div>
          <div className="brand">AI Companion MVP</div>
          <p className="muted">Sprint 0 skeleton with mock AI responses.</p>
        </div>
        <nav className="nav">
          <Link href="/characters">Characters</Link>
        </nav>
      </div>

      <section className="panel stack">
        <h1>Create a companion and start chatting</h1>
        <p className="muted">
          This build stores characters and messages in PostgreSQL and uses mock providers for all AI features.
        </p>
        <div>
          <Link className="button" href="/characters">
            Open characters
          </Link>
        </div>
      </section>
    </main>
  );
}
