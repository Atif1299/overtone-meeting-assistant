const dashboardUrl = import.meta.env.VITE_DASHBOARD_URL || "http://127.0.0.1:5176";

const steps = [
  { n: "01", title: "Upload your deck", body: "Add a PPTX or PDF in the dashboard. Vision extracts slide content and builds a pgvector index." },
  { n: "02", title: "Launch the bot", body: "Paste a Google Meet, Zoom, or Teams URL. Recall joins and opens the presenter as the bot camera." },
  { n: "03", title: "Present live", body: "Overtone speaks through Gemini Live, navigates slides on demand, and stays on-script." },
  { n: "04", title: "Answer from slides", body: "Audience questions trigger search_and_answer — responses come from your deck, not the open web." },
];

export default function HowItWorksPage() {
  return (
    <section className="section">
      <h2>How it works</h2>
      <p className="muted" style={{ maxWidth: 560 }}>Four steps from deck upload to live meeting presentation.</p>
      <div className="steps">
        {steps.map((s) => (
          <article key={s.n} className="step">
            <p className="step-num">STEP {s.n}</p>
            <h3>{s.title}</h3>
            <p style={{ color: "var(--muted)", marginTop: "0.5rem", fontSize: "0.95rem" }}>{s.body}</p>
          </article>
        ))}
      </div>
      <div style={{ marginTop: "2.5rem", textAlign: "center" }}>
        <a href={`${dashboardUrl}/signup`} className="btn btn-primary">Try it free</a>
      </div>
    </section>
  );
}
