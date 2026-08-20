import { resolveWsBase } from "./resolveWsBase.js";

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

export { resolveWsBase };

export function wsBase() {
  const locationHostname =
    typeof window !== "undefined" ? window.location.hostname : "";
  const locationProtocol =
    typeof window !== "undefined" ? window.location.protocol : "http:";
  return resolveWsBase({
    wssQuery: queryValue("wss"),
    viteWsBase: import.meta.env.VITE_WS_BASE || "",
    apiQuery: queryValue("api"),
    locationHostname,
    locationProtocol,
    backendPort: import.meta.env.VITE_BACKEND_PORT || "8000",
  });
}

export function presentationWsUrl(sessionId) {
  return `${wsBase()}/ws/presentation/${sessionId}`;
}

export function realtimeRelayWsUrl(sessionId) {
  return `${wsBase()}/ws/realtime/${sessionId}`;
}

function isUsableHttpBase(value) {
  if (!value) return false;
  const normalized = String(value).trim();
  if (!normalized) return false;
  if (normalized.includes("REPLACE-WITH")) return false;
  return true;
}

export function apiBase() {
  const derivedFromRelay = deriveHttpBaseFromWss();
  if (derivedFromRelay) return derivedFromRelay;
  const explicit = import.meta.env.VITE_API_BASE || queryValue("api");
  if (isUsableHttpBase(explicit)) return explicit.replace(/\/$/, "");
  return "http://127.0.0.1:8000";
}

export function slideImageUrl(presentationId, page) {
  return `${apiBase()}/api/v1/presentations/${presentationId}/page/${page}/image`;
}

export function slidePageUrl(presentationId, page) {
  return `${apiBase()}/api/v1/presentations/${presentationId}/page/${page}`;
}
