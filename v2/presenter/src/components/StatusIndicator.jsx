const labels = {
  connecting: "Connecting",
  listening: "Listening",
  processing: "Processing",
  speaking: "Speaking",
};

export default function StatusIndicator({ status }) {
  const label = labels[status] || status || "Connecting";
  const tone =
    status === "processing"
      ? "warn"
      : status === "speaking"
        ? "active"
        : status === "connecting"
          ? "neutral"
          : "ok";
  return (
    <div className={`status-indicator ${tone}`}>
      <span className="status-dot" />
      <span>{label}</span>
    </div>
  );
}
