import { useEffect, useRef } from "react";

export default function VisualFrame({
  src,
  alt = "",
  variant = "hero",
  align = "center",
  children,
}) {
  const ref = useRef(null);

  useEffect(() => {
    const el = ref.current;
    if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return undefined;

    const onMove = (e) => {
      const rect = el.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      el.style.setProperty("--parallax-x", `${x * 8}px`);
      el.style.setProperty("--parallax-y", `${y * 6}px`);
    };

    el.addEventListener("mousemove", onMove);
    return () => el.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <div className={`visual-frame visual-frame--${variant} visual-frame--${align}`} ref={ref}>
      <div className="visual-frame__glow" aria-hidden="true" />
      <div className="visual-frame__shade visual-frame__shade--top" aria-hidden="true" />
      <div className="visual-frame__shade visual-frame__shade--bottom" aria-hidden="true" />
      <div className="visual-frame__inner">
        {src ? (
          <img src={src} alt={alt} className="visual-frame__img" loading="lazy" />
        ) : null}
        {children}
      </div>
      <div className="visual-frame__border" aria-hidden="true" />
    </div>
  );
}
