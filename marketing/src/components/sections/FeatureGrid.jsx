import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function FeatureGrid({ eyebrow, title, subtitle, items, columns = 3 }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-light section-elevated reveal" ref={ref}>
      <div className="section-mesh section-mesh--light" aria-hidden="true" />
      <div className="section-inner">
        <div className="section-head centered">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          {subtitle ? <p className="muted section-sub">{subtitle}</p> : null}
        </div>
        <div className={`feature-grid feature-grid--${columns}`}>
          {items.map((item) => (
            <article key={item.title} className="feature-card card-hover">
              {item.image ? (
                <div className="feature-card__media">
                  <img src={item.image} alt="" loading="lazy" />
                </div>
              ) : null}
              <div className="feature-card__body">
                {item.icon ? <span className="feature-card__icon">{item.icon}</span> : null}
                <h3>{item.title}</h3>
                <p>{item.body}</p>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
