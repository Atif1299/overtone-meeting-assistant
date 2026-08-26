const dashboardUrl = import.meta.env.VITE_DASHBOARD_URL || "http://127.0.0.1:5176";

const plans = [
  {
    name: "Free trial",
    price: "$0",
    features: ["1 bot launch / month", "1 deck upload / month", "Full presenter experience"],
    cta: "Start free",
    featured: false,
  },
  {
    name: "Starter",
    price: "$10",
    period: "/mo",
    features: ["5 bot launches / month", "3 deck uploads / month", "Email support"],
    cta: "Get Starter",
    featured: false,
    plan: "starter",
  },
  {
    name: "Pro",
    price: "$20",
    period: "/mo",
    features: ["20 bot launches / month", "10 deck uploads / month", "Priority support"],
    cta: "Get Pro",
    featured: true,
    plan: "pro",
  },
];

export default function PricingPage() {
  return (
    <section className="section section-light" style={{ maxWidth: "100%" }}>
      <div style={{ maxWidth: 1100, margin: "0 auto" }}>
        <h2>Simple pricing</h2>
        <p className="muted">Start free. Upgrade when your demo volume grows.</p>
        <div className="pricing-grid">
          {plans.map((p) => (
            <article key={p.name} className={`price-card${p.featured ? " featured" : ""}`}>
              <h3>{p.name}</h3>
              <div className="price">
                {p.price}
                {p.period ? <small style={{ fontSize: "1rem", fontWeight: 400 }}>{p.period}</small> : null}
              </div>
              <ul>
                {p.features.map((f) => (
                  <li key={f}>✓ {f}</li>
                ))}
              </ul>
              <a
                href={p.plan ? `${dashboardUrl}/signup?plan=${p.plan}` : `${dashboardUrl}/signup`}
                className={`btn ${p.featured ? "btn-primary" : "btn-secondary"}`}
                style={{ width: "100%" }}
              >
                {p.cta}
              </a>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
