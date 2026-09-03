const EFFECTS = {
  hero: { glow: true, shade: true },
  split: { glow: true, shade: false },
  card: { glow: false, shade: false },
  step: { glow: false, shade: false },
};

export default function VisualFrame({
  src,
  alt = "",
  variant = "hero",
  align = "center",
  children,
}) {
  const fx = EFFECTS[variant] || EFFECTS.split;
  const eager = variant === "hero";

  return (
    <div className={`visual-frame visual-frame--${variant} visual-frame--${align}`}>
      {fx.glow ? <div className="visual-frame__glow" aria-hidden="true" /> : null}
      {fx.shade ? (
        <>
          <div className="visual-frame__shade visual-frame__shade--top" aria-hidden="true" />
          <div className="visual-frame__shade visual-frame__shade--bottom" aria-hidden="true" />
        </>
      ) : null}
      <div className="visual-frame__inner">
        {src ? (
          <img
            src={src}
            alt={alt}
            className="visual-frame__img"
            width={960}
            height={600}
            loading={eager ? "eager" : "lazy"}
            fetchPriority={eager ? "high" : "low"}
          />
        ) : null}
        {children}
      </div>
    </div>
  );
}
