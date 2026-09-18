const TONES = {
  light: { fill: "#111111", hole: "#FFFFFF" },
  dark: { fill: "#F1F5F9", hole: "#080C14" },
};

export default function DeckVoiceMark({ tone = "light", size = 28, className = "", decorative = false }) {
  const { fill, hole } = TONES[tone] || TONES.light;

  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role={decorative ? "presentation" : "img"}
      aria-hidden={decorative ? true : undefined}
      aria-label={decorative ? undefined : "DeckVoice"}
    >
      {decorative ? null : <title>DeckVoice</title>}
      <circle cx="16" cy="16" r="13" fill={fill} />
      <circle cx="13" cy="12.4" r="6.15" fill={hole} />
      <circle cx="13" cy="12.4" r="3.05" fill="none" stroke={fill} strokeWidth="1.65" />
    </svg>
  );
}
