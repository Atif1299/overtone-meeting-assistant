import { useScrollReveal } from "../../hooks/useScrollReveal.js";

export default function SplitFeature({ eyebrow, title, body, bullets = [], imageSrc, imageAlt, reverse = false, tone = "light" }) {
  const ref = useScrollReveal();

  return (
    <section className={`split-feature section-${tone} reveal`} ref={ref}>
      <div className={`split-inner${reverse ? " reverse" : ""}`}>
        <div className="split-copy">
          {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
          {body ? <p className="split-body">{body}</p> : null}
          {bullets.length ? (
            <ul className="split-bullets">
              {bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          ) : null}
        </div>
        {imageSrc ? (
          <div className="split-visual">
            <div className="split-visual-glow" aria-hidden="true" />
            <img src={imageSrc} alt={imageAlt || title} className="split-image" loading="lazy" />
          </div>
        ) : null}
      </div>
    </section>
  );
}
