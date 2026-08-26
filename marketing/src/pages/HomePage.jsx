const dashboardUrl = import.meta.env.VITE_DASHBOARD_URL || "http://127.0.0.1:5176";

export default function HomePage() {
  return (
    <>
      <section className="hero">
        <span className="hero-badge">AI presentation agent for live meetings</span>
        <h1>Your deck. Your meeting. Overtone presents and answers live.</h1>
        <p className="lede">
          Upload slides, paste a Meet / Zoom / Teams link, and let Overtone join as a presenter —
          navigating your deck and answering questions grounded in your content.
        </p>
        <div className="hero-actions">
          <a href={`${dashboardUrl}/signup`} className="btn btn-primary">Start free trial</a>
          <a href="/how-it-works" className="btn btn-secondary">See how it works</a>
        </div>
        <div className="hero-visual">
          <div className="mock-window">
            <div className="mock-bar"><span /><span /><span /></div>
            <p style={{ color: "#94a3b8", fontSize: "0.85rem" }}>Live session · Google Meet</p>
            <p style={{ marginTop: "0.5rem", fontWeight: 600 }}>“What’s on slide 7 about pricing?”</p>
            <p style={{ marginTop: "0.75rem", color: "#38bdf8" }}>
              Overtone navigates to slide 7 and answers from your indexed deck — not generic chat.
            </p>
          </div>
        </div>
      </section>

      <section className="section section-light">
        <h2>Built for demos, sales calls, and investor updates</h2>
        <p className="muted">Everything you need to run a credible live presentation — without a human presenter in the loop.</p>
        <div className="grid-3">
          <article className="card">
            <h3>Deck-grounded answers</h3>
            <p>Vision indexes every slide. Q&amp;A stays tied to your actual content.</p>
          </article>
          <article className="card">
            <h3>Joins real meetings</h3>
            <p>Recall.ai carries your presenter view as the bot camera in Meet, Zoom, or Teams.</p>
          </article>
          <article className="card">
            <h3>Live voice</h3>
            <p>Gemini Live speech-to-speech — natural pacing, interruptions handled.</p>
          </article>
        </div>
      </section>
    </>
  );
}
