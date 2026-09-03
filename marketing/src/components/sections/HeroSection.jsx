import { useEffect } from "react";
import { Radio, Rocket, Upload } from "lucide-react";
import { useScrollReveal } from "../../hooks/useScrollReveal.js";
import VisualFrame from "../visuals/VisualFrame.jsx";

const STEP_CHIPS = [
  { icon: Upload, label: "Upload" },
  { icon: Rocket, label: "Launch" },
  { icon: Radio, label: "Present" },
];

function useHeroPreload(href) {
  useEffect(() => {
    if (!href) return undefined;
    const selector = `link[rel="preload"][as="image"][href="${href}"]`;
    if (document.querySelector(selector)) return undefined;
    const link = document.createElement("link");
    link.rel = "preload";
    link.as = "image";
    link.href = href;
    document.head.appendChild(link);
    return () => {
      link.remove();
    };
  }, [href]);
}

function HeroAtoms({ sources, alt }) {
  const stack = sources.length >= 2 ? sources.slice(0, 3) : [sources[0], sources[0], sources[0]];
  const positions = ["top left", "center right", "bottom center"];

  return (
    <div className="hero-atoms">
      {stack.map((src, i) => (
        <div key={`${src}-${i}`} className={`hero-atoms__frag hero-atoms__frag--${i}`}>
          <img
            src={src}
            alt={i === 0 ? alt : ""}
            width={720}
            height={480}
            loading={i === 0 ? "eager" : "lazy"}
            fetchPriority={i === 0 ? "high" : "low"}
            style={{ objectPosition: sources.length < 2 ? positions[i] : "center" }}
          />
        </div>
      ))}
    </div>
  );
}

function HeroComposition({ kind, images, alt }) {
  const srcs = images.filter(Boolean);
  if (!srcs.length) return null;

  if (kind === "orbit") {
    const main = srcs[0];
    const chipA = srcs[1] || srcs[0];
    const chipB = srcs[2] || srcs[1] || srcs[0];
    return (
      <div className="hero-orbit">
        <div className="hero-orbit__main">
          <img src={main} alt={alt} width={720} height={480} loading="eager" fetchPriority="high" />
        </div>
        <div className="hero-orbit__chip hero-orbit__chip--a">
          <img src={chipA} alt="" width={280} height={180} loading="lazy" />
        </div>
        <div className="hero-orbit__chip hero-orbit__chip--b">
          <img src={chipB} alt="" width={240} height={160} loading="lazy" />
        </div>
      </div>
    );
  }

  if (kind === "steps") {
    return (
      <div className="hero-steps">
        <div className="hero-steps__main">
          <img src={srcs[0]} alt={alt} width={720} height={480} loading="eager" fetchPriority="high" />
        </div>
        <div className="hero-steps__chips">
          {STEP_CHIPS.map(({ icon: Icon, label }) => (
            <div key={label} className="hero-steps__chip">
              <span className="hero-steps__icon" aria-hidden="true">
                <Icon size={16} strokeWidth={2} />
              </span>
              <span>{label}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (kind === "stage") {
    const front = srcs[0];
    const back = srcs[1] || srcs[0];
    return (
      <div className="hero-stage">
        <div className="hero-stage__a">
          <img src={front} alt={alt} width={640} height={400} loading="eager" fetchPriority="high" />
        </div>
        <div className="hero-stage__b">
          <img src={back} alt="" width={400} height={280} loading="lazy" />
        </div>
      </div>
    );
  }

  if (kind === "ledger") {
    return (
      <div className="hero-ledger">
        <img src={srcs[0]} alt={alt} width={720} height={360} loading="eager" fetchPriority="high" />
      </div>
    );
  }

  return null;
}

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
  overlay = false,
  overlayImages,
  composition,
  compositionImages,
}) {
  const ref = useScrollReveal();
  const fragments = overlayImages?.filter(Boolean) ?? [];
  const composed = compositionImages?.filter(Boolean) ?? [];
  const isOverlay = Boolean(overlay);
  const overlaySources = fragments.length ? fragments : imageSrc ? [imageSrc] : [];
  const preloadHref = isOverlay
    ? overlaySources[0] || imageSrc
    : composed[0] || imageSrc;

  useHeroPreload(preloadHref);

  const compositionClass = composition ? ` hero--${composition}` : "";
  const overlayClass = isOverlay ? " hero--overlay" : "";

  return (
    <section className={`hero section-dark scroll-fade${overlayClass}${compositionClass}`} ref={ref}>
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
        {isOverlay && overlaySources.length ? (
          <HeroAtoms sources={overlaySources} alt={imageAlt} />
        ) : composition && composed.length ? (
          <HeroComposition kind={composition} images={composed} alt={imageAlt} />
        ) : (imageSrc || visual) ? (
          <VisualFrame src={imageSrc} alt={imageAlt} variant="hero">
            {visual}
          </VisualFrame>
        ) : null}
      </div>
    </section>
  );
}
