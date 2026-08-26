import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import { integrations } from "../visuals/media.js";

export default function IntegrationStrip({ title }) {
  const ref = useScrollReveal();

  return (
    <section className="integration-strip section-dark reveal" ref={ref}>
      <div className="section-mesh section-mesh--dark" aria-hidden="true" />
      <p className="integration-title">{title}</p>
      <div className="integration-row">
        {integrations.map((item) => (
          <div key={item.label} className="integration-item card-glass card-hover">
            <span className="integration-glyph" style={{ "--brand-color": item.color }}>
              {item.glyph}
            </span>
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
