import { useEffect, useRef } from "react";

const EFFECTS = {
  hero: { border: false, glow: true, shade: true, float: true, parallax: true, tilt: false },
  split: { border: false, glow: true, shade: false, float: false, parallax: false, tilt: false },
  card: { border: false, glow: false, shade: false, float: false, parallax: false, tilt: false },
  step: { border: false, glow: false, shade: false, float: false, parallax: false, tilt: false },
};

export default function VisualFrame({
  src,
  alt = "",
  variant = "hero",
  align = "center",
  children,
}) {
  const ref = useRef(null);
  const fx = EFFECTS[variant] || EFFECTS.split;

  useEffect(() => {
    if (!fx.parallax) return undefined;
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;

    const onMove = (e) => {
      const rect = el.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      el.style.setProperty("--parallax-x", `${x * 4}px`);
      el.style.setProperty("--parallax-y", `${y * 3}px`);
    };

    el.addEventListener("mousemove", onMove);
    return () => el.removeEventListener("mousemove", onMove);
  }, [fx.parallax]);

  return (
    <div
      className={`visual-frame visual-frame--${variant} visual-frame--${align}${fx.float ? " visual-frame--animate" : ""}`}
      ref={ref}
    >
      {fx.glow ? <div className="visual-frame__glow" aria-hidden="true" /> : null}
      {fx.shade ? (
        <>
          <div className="visual-frame__shade visual-frame__shade--top" aria-hidden="true" />
          <div className="visual-frame__shade visual-frame__shade--bottom" aria-hidden="true" />
        </>
      ) : null}
      <div className="visual-frame__inner">
        {src ? (
          <img src={src} alt={alt} className="visual-frame__img" loading="lazy" />
        ) : null}
        {children}
      </div>
    </div>
  );
}
