export default function BrandLogo({ brand, size = 28, className = "" }) {
  if (!brand) return null;

  if (brand.type === "external") {
    return (
      <img
        src={brand.src}
        alt={brand.title}
        width={size}
        height={size}
        className={`brand-logo brand-logo--img ${className}`.trim()}
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
