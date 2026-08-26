export default function PlatformLogo({ platform, size = "md", showLabel = false }) {
  const sizeClass = size === "sm" ? "platform-logo--sm" : size === "lg" ? "platform-logo--lg" : "platform-logo--md";

  return (
    <div className={`platform-logo ${sizeClass}`} title={platform.label}>
      <img src={platform.logo} alt={platform.label} loading="lazy" />
      {showLabel ? <span>{platform.label}</span> : null}
    </div>
  );
}
