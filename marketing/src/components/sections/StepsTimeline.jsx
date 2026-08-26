import { Link } from "react-router-dom";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function StepsTimeline({ eyebrow, title, steps, ctaLabel, ctaTo }) {
  const ref = useScrollReveal();

  return (
    <section className="section section-dark section-elevated reveal" ref={ref}>
      <div className="section-mesh section-mesh--dark" aria-hidden="true" />
      <div className="section-inner">
        <div className="section-head centered">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        <div className="steps">
          {steps.map((step, i) => (
            <article key={step.title} className="step card-glass card-hover">
              <p className="step-num">STEP {String(i + 1).padStart(2, "0")}</p>
              {step.image ? (
                <div className="step-media">
                  <img src={step.image} alt="" loading="lazy" />
                </div>
              ) : null}
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
      </div>
    </section>
  );
}
