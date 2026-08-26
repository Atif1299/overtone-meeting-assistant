import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import VisualFrame from "../visuals/VisualFrame.jsx";

export default function HeroSection({
  badge,
  title,
  subtitle,
  primaryCta,
  primaryHref,
  secondaryCta,
  secondaryHref,
  imageSrc,
  imageAlt = "Overtone product preview",
  visual,
}) {
  const ref = useScrollReveal();

  return (
    <section className="hero section-dark reveal" ref={ref}>
      <div className="section-mesh section-mesh--hero" aria-hidden="true" />
      <div className="hero-glow hero-glow-a" aria-hidden="true" />
      <div className="hero-glow hero-glow-b" aria-hidden="true" />
      <div className="hero-inner">
        <div className="hero-copy">
          {badge ? <span className="hero-badge">{badge}</span> : null}
          <h1>{title}</h1>
          {subtitle ? <p className="lede">{subtitle}</p> : null}
          <div className="hero-actions">
            {primaryHref ? (
              <a href={primaryHref} className="btn btn-primary btn-shimmer">{primaryCta}</a>
            ) : null}
            {secondaryHref ? (
              <a href={secondaryHref} className="btn btn-secondary">{secondaryCta}</a>
            ) : null}
          </div>
        </div>
        {(imageSrc || visual) ? (
          <VisualFrame src={imageSrc} alt={imageAlt} variant="hero">
            {visual}
          </VisualFrame>
        ) : null}
      </div>
    </section>
  );
}
