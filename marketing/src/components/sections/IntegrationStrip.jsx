import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import { platforms } from "../visuals/platforms.js";
import PlatformLogo from "../visuals/PlatformLogo.jsx";

export default function IntegrationStrip({ title }) {
  const ref = useScrollReveal({ stagger: true });

  return (
    <section className="integration-strip section-dark scroll-reveal scroll-reveal--stagger" ref={ref}>
      <div className="section-mesh section-mesh--dark" aria-hidden="true" />
      <p className="integration-title reveal-item">{title}</p>
      <div className="integration-row">
        {platforms.map((p) => (
          <div key={p.id} className="integration-item reveal-item">
            <PlatformLogo platform={p} size="sm" />
            <span>{p.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
