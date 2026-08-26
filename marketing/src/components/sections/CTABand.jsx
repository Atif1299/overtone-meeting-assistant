import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function CTABand({ title, subtitle, primaryLabel, primaryHref, secondaryLabel, secondaryHref }) {
  const ref = useScrollReveal();

  return (
    <section className="cta-band reveal" ref={ref}>
      <div className="cta-band-inner">
        <h2>{title}</h2>
        {subtitle ? <p>{subtitle}</p> : null}
        <div className="hero-actions">
          <a href={primaryHref} className="btn btn-primary btn-shimmer">{primaryLabel}</a>
          {secondaryHref ? (
            <a href={secondaryHref} className="btn btn-ghost-light">{secondaryLabel}</a>
          ) : null}
        </div>
      </div>
    </section>
  );
}
