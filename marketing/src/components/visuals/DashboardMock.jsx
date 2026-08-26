export default function DashboardMock({ variant = "overview" }) {
  if (variant === "launch") {
    return (
      <div className="dash-mock dash-mock--launch" aria-hidden="true">
        <div className="dash-mock__chrome">
          <span /><span /><span />
        </div>
        <div className="dash-mock__body">
          <aside className="dash-mock__sidebar">
            {["Overview", "Agents", "Presentations", "Launch", "Session"].map((l, i) => (
              <div key={l} className={`dash-mock__nav${i === 3 ? " active" : ""}`}>{l}</div>
            ))}
          </aside>
          <main className="dash-mock__main">
            <p className="dash-mock__eyebrow">Bot controls</p>
            <h3 className="dash-mock__title">Launch meeting bot</h3>
            <div className="dash-mock__field">https://meet.google.com/abc-defg-hij</div>
            <div className="dash-mock__field dash-mock__field--select">Q3 Sales Deck · Ready</div>
            <div className="dash-mock__btn">Launch bot</div>
          </main>
        </div>
      </div>
    );
  }

  return (
    <div className="dash-mock" aria-hidden="true">
      <div className="dash-mock__chrome">
        <span /><span /><span />
      </div>
      <div className="dash-mock__body">
        <aside className="dash-mock__sidebar">
          {["Overview", "Agents", "Presentations", "Launch", "Session", "Billing"].map((l, i) => (
            <div key={l} className={`dash-mock__nav${i === 0 ? " active" : ""}`}>{l}</div>
          ))}
        </aside>
        <main className="dash-mock__main">
          <p className="dash-mock__eyebrow">Command Deck</p>
          <h3 className="dash-mock__title">Operations overview</h3>
          <div className="dash-mock__metrics">
            <div><strong>Online</strong><small>Backend</small></div>
            <div><strong>3</strong><small>Decks</small></div>
            <div><strong>Live</strong><small>Session</small></div>
          </div>
          <div className="dash-mock__panel">
            <span>Launch meeting bot</span>
            <small>Paste Meet / Zoom / Teams URL</small>
          </div>
        </main>
      </div>
    </div>
  );
}
