import { useCallback, useState } from "react";

export default function FileUploader({ onUploaded, busy = false }) {
  const [drag, setDrag] = useState(false);
  const [selectedName, setSelectedName] = useState("");
  const onDrop = useCallback(
    async (e) => {
      e.preventDefault();
      if (busy) return;
      setDrag(false);
      const f = e.dataTransfer?.files?.[0];
      if (f) {
        setSelectedName(f.name);
        onUploaded?.(f);
      }
    },
    [busy, onUploaded]
  );
  return (
    <div
      onDragOver={(e) => {
        e.preventDefault();
        if (busy) return;
        setDrag(true);
      }}
      onDragLeave={() => setDrag(false)}
      onDrop={onDrop}
      className={`uploader ${drag ? "dragging" : ""} ${busy ? "busy" : ""}`}
    >
      <p className="uploader-title">Drop .pptx or .pdf files</p>
      <p className="helper-text">
        Each slide is rendered as an image and analyzed by Claude Vision for rich semantic search.
      </p>
      <input
        className="input"
        type="file"
        accept=".pdf,.pptx"
        disabled={busy}
        onChange={(e) => {
          if (busy) return;
          if (e.target.files?.[0]) {
            const file = e.target.files[0];
            setSelectedName(file.name);
            onUploaded?.(file);
          }
        }}
      />
      {selectedName ? <p className="helper-text">Selected: {selectedName}</p> : null}
      {busy ? <p className="helper-text shimmer-text">Uploading — Claude Vision is processing each slide...</p> : null}
    </div>
  );
}
