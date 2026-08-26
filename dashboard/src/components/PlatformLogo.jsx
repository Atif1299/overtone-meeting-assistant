export default function PlatformLogo({ platform, size = "md" }) {
  const sizeClass = size === "sm" ? "platform-logo--sm" : "platform-logo--md";

  return (
    <div className={`platform-logo ${sizeClass}`} title={platform.label}>
      <img src={platform.logo} alt={platform.label} loading="lazy" />
    </div>
  );
}
