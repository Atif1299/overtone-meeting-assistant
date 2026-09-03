export default function BrandLogo({ brand, size = 28, className = "", compact = false }) {
  if (!brand) return null;

  if (brand.type === "local" || brand.type === "external") {
    const src = compact && brand.iconSrc ? brand.iconSrc : brand.src;
    const isWordmark = brand.variant === "wordmark" && !compact;

    return (
      <img
        src={src}
        alt={brand.title}
        width={isWordmark ? undefined : size}
        height={size}
        className={`brand-logo brand-logo--img${isWordmark ? " brand-logo--wordmark" : ""} ${className}`.trim()}
        loading="lazy"
        decoding="async"
      />
    );
  }

  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      width={size}
      height={size}
      className={`brand-logo brand-logo--svg ${className}`.trim()}
      aria-label={brand.title}
    >
      <title>{brand.title}</title>
      <path d={brand.path} fill={`#${brand.hex}`} />
    </svg>
  );
}
