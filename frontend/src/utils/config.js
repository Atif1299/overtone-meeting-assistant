function queryValue(name) {
  if (typeof window === "undefined") return "";
  try {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || "";
  } catch {
    return "";
  }
}

function deriveHttpBaseFromWss() {
  const relay = queryValue("wss");
  if (!relay) return "";
  try {
    const url = new URL(relay);
    const proto = url.protocol === "wss:" ? "https:" : "http:";
    return `${proto}//${url.host}`;
  } catch {
    return "";
  }
}

function wsBase() {
  const u = import.meta.env.VITE_WS_BASE || "";
  if (u) return u.replace(/\/$/, "");
  // If a ?wss= param is provided, use it directly.
  const relay = queryValue("wss");
  if (relay) {
    try {
      const url = new URL(relay);
      const proto = url.protocol === "https:" ? "wss:" : url.protocol;
      return `${proto}//${url.host}`;
    } catch {
      // Fall through.
    }
  }
  // If a ?api= param is provided, convert https→wss and use that host.
  // This ensures the WebSocket connects to the backend tunnel, not the frontend tunnel.
  const apiParam = queryValue("api");
  if (apiParam) {
    try {
      const url = new URL(apiParam);
      const proto = url.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${url.host}`;
    } catch {
      // Fall through.
    }
  }
  if (typeof window !== "undefined") {
    const { protocol, hostname } = window.location;
    const wsProto = protocol === "https:" ? "wss:" : "ws:";
    const port = import.meta.env.VITE_BACKEND_PORT || "8000";
    // On localhost, append the port. On tunnels (ngrok/cloudflare), use standard port (no suffix).
    if (hostname && hostname !== "localhost" && hostname !== "127.0.0.1") {
      return `${wsProto}//${hostname}`;
    }
    return `${wsProto}//127.0.0.1:${port}`;
  }
  return "ws://127.0.0.1:8000";
}

export function presentationWsUrl(sessionId) {
  return `${wsBase()}/ws/presentation/${sessionId}`;
}

export function realtimeRelayWsUrl(sessionId) {
  return `${wsBase()}/ws/realtime/${sessionId}`;
}

export function apiBase() {
  const explicit = import.meta.env.VITE_API_BASE || queryValue("api");
  if (explicit) return explicit.replace(/\/$/, "");
  const derivedFromRelay = deriveHttpBaseFromWss();
  if (derivedFromRelay) return derivedFromRelay;
  return "http://127.0.0.1:8000";
}

export function slideImageUrl(presentationId, page) {
  return `${apiBase()}/api/v1/presentations/${presentationId}/page/${page}/image`;
}

export function slidePageUrl(presentationId, page) {
  return `${apiBase()}/api/v1/presentations/${presentationId}/page/${page}`;
}
