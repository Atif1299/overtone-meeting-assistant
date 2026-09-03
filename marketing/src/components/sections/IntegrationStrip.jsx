import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import BrandLogo from "../visuals/BrandLogo.jsx";
import { integrations } from "../visuals/integrations.js";

export default function IntegrationStrip({ title }) {
  const ref = useScrollReveal({ variant: "fade" });

  return (
    <section className="integration-strip section-dark scroll-fade" ref={ref}>
      <div className="section-mesh section-mesh--dark" aria-hidden="true" />
      <p className="integration-title">{title}</p>
      <div className="integration-grid">
        {integrations.map((item) => (
          <div key={item.id} className="integration-tile">
            <BrandLogo brand={item} size={32} compact />
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
