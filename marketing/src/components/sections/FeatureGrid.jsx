import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import VisualFrame from "../visuals/VisualFrame.jsx";

export default function FeatureGrid({ eyebrow, title, subtitle, items }) {
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
        <div className="grid-3">
          {items.map((item) => (
            <article key={item.title} className="card card-glass card-hover">
              {item.icon ? <span className="card-icon">{item.icon}</span> : null}
              {item.image ? (
                <VisualFrame src={item.image} alt="" variant="card" />
              ) : item.visual ? (
                <div className="card-visual">{item.visual}</div>
              ) : null}
              <h3>{item.title}</h3>
              <p>{item.body}</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
