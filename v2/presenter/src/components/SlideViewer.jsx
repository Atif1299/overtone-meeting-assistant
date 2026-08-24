import { useState, useEffect } from "react";
import { slideImageUrl } from "../utils/config";

export default function SlideViewer({ presentationId, page, transition }) {
  const [hasImageError, setHasImageError] = useState(false);
  const [blobUrl, setBlobUrl] = useState("");

  useEffect(() => {
    let active = true;
    let currentUrl = "";

    setHasImageError(false);
    fetch(slideImageUrl(presentationId, page), {
      headers: { "ngrok-skip-browser-warning": "69420" },
    })
      .then((r) => (r.ok ? r.blob() : Promise.reject("bad status")))
      .then((blob) => {
        if (!active) return;
        currentUrl = URL.createObjectURL(blob);
        setBlobUrl(currentUrl);
      })
      .catch(() => {
        if (active) setHasImageError(true);
      });

    return () => {
      active = false;
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [presentationId, page]);

  return (
    <div className="slide-shell">
      {!hasImageError && blobUrl ? (
        <img
          key={page}
          src={blobUrl}
          alt={`Slide ${page}`}
          className={`slide-image ${transition ? "transitioning" : ""}`}
          onError={() => setHasImageError(true)}
        />
      ) : (
        <div className="slide-blank" />
      )}
    </div>
  );
}
