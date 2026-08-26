import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function FeatureGrid({ eyebrow, title, subtitle, items }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-light reveal" ref={ref}>
      <div className="section-head centered">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
        {subtitle ? <p className="muted section-sub">{subtitle}</p> : null}
      </div>
      <div className="grid-3">
        {items.map((item) => (
          <article key={item.title} className="card card-hover">
            {item.icon ? <span className="card-icon">{item.icon}</span> : null}
            {item.image ? <img src={item.image} alt="" className="card-thumb" loading="lazy" /> : null}
            <h3>{item.title}</h3>
            <p>{item.body}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
