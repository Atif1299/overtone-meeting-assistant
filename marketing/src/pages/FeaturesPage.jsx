export default function FeaturesPage() {
  const items = [
    { title: "Upload PPTX or PDF", body: "Dashboard ingests decks, extracts per-slide metadata, and builds a searchable vector index." },
    { title: "Launch with one link", body: "Paste a meeting URL. Overtone joins, opens the presenter page as output media, and starts presenting." },
    { title: "Slide navigation tools", body: "The agent calls navigate_to_slide, get_slide_details, and search_and_answer — grounded in your deck." },
    { title: "Operator studio", body: "Monitor sessions, tune agent prompts, manage your knowledge base, and track usage from one dashboard." },
    { title: "Multi-tenant SaaS", body: "Each workspace gets isolated presentations, agents, and monthly usage limits by plan." },
    { title: "Stripe subscriptions", body: "Free trial, Starter ($10), and Pro ($20) tiers with bot launch and upload quotas." },
  ];

  return (
    <section className="section">
      <h2>Features</h2>
      <p className="muted" style={{ maxWidth: 640 }}>Overtone is an end-to-end stack: ingestion, realtime voice, meeting bots, and operator controls.</p>
      <div className="grid-3">
        {items.map((item) => (
          <article key={item.title} className="card">
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
