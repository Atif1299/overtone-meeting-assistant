import { Link } from "react-router-dom";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function StepsTimeline({ eyebrow, title, steps, ctaLabel, ctaTo }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-dark reveal" ref={ref}>
      <div className="section-head centered">
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2>{title}</h2>
      </div>
      <div className="steps">
        {steps.map((step, i) => (
          <article key={step.title} className="step card-hover">
            <p className="step-num">STEP {String(i + 1).padStart(2, "0")}</p>
            {step.image ? <img src={step.image} alt="" className="step-image" loading="lazy" /> : null}
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </article>
        ))}
      </div>
      {ctaLabel && ctaTo ? (
        <div className="section-cta centered">
          <Link to={ctaTo} className="btn btn-secondary">{ctaLabel}</Link>
        </div>
      ) : null}
    </section>
  );
}
