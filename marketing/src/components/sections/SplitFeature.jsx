import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import VisualFrame from "../visuals/VisualFrame.jsx";

export default function SplitFeature({ eyebrow, title, body, bullets = [], imageSrc, imageAlt, visual, reverse = false, tone = "light" }) {
  const ref = useScrollReveal();

  return (
    <section className={`split-feature section-${tone} scroll-fade`} ref={ref}>
      <div className={`section-mesh section-mesh--${tone}`} aria-hidden="true" />
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
        {(imageSrc || visual) ? (
          <VisualFrame
            src={imageSrc}
            alt={imageAlt || title}
            variant="split"
            align={reverse ? "left" : "right"}
          >
            {visual}
          </VisualFrame>
        ) : null}
      </div>
    </section>
  );
}
