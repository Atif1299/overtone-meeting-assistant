import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function MetricsBand({ metrics }) {
  const ref = useScrollReveal();

  return (
    <section className="metrics-band section-dark scroll-fade" ref={ref}>
      <div className="metrics-grid">
        {metrics.map((m) => (
          <div key={m.label} className="metric">
            <p className="metric-value">{m.value}</p>
            <p className="metric-label">{m.label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
