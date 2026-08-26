import { dashboardUrl } from "../../config.js";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function PricingCards({ plans }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-pricing scroll-fade" ref={ref}>
      <div className="section-mesh section-mesh--pricing" aria-hidden="true" />
      <div className="section-inner">
        <div className="pricing-grid">
          {plans.map((p) => (
            <article key={p.name} className={`price-card card-glass card-hover${p.featured ? " featured" : ""}`}>
              <h3>{p.name}</h3>
              <div className="price">
                {p.price}
                {p.period ? <small>{p.period}</small> : null}
              </div>
              <ul>
                {p.features.map((f) => (
                  <li key={f}>✓ {f}</li>
                ))}
              </ul>
              <a
                href={p.plan ? `${dashboardUrl}/signup?plan=${p.plan}` : `${dashboardUrl}/signup`}
                className={`btn ${p.featured ? "btn-primary btn-shimmer" : "btn-secondary"}`}
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
