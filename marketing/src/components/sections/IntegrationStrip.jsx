import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function IntegrationStrip({ title, items }) {
  const ref = useScrollReveal();

  return (
    <section className="integration-strip section-dark reveal" ref={ref}>
      <p className="integration-title">{title}</p>
      <div className="integration-row">
        {items.map((item) => (
          <div key={item.label} className="integration-item card-hover">
            {item.image ? <img src={item.image} alt="" loading="lazy" /> : null}
            <span>{item.label}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
