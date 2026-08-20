/**
 * Resolve presentation / realtime WS host.
 * Priority: ?wss= → VITE_WS_BASE → ?api= → localhost.
 */
export function resolveWsBase({
  wssQuery = "",
  viteWsBase = "",
  apiQuery = "",
  locationHostname = "",
  locationProtocol = "http:",
  backendPort = "8000",
} = {}) {
  if (wssQuery) {
    try {
      const url = new URL(wssQuery);
      const proto =
        url.protocol === "https:" ? "wss:" : url.protocol === "http:" ? "ws:" : url.protocol;
      return `${proto}//${url.host}`;
    } catch {
      // Fall through.
    }
  }
  if (viteWsBase && !String(viteWsBase).includes("REPLACE-WITH")) {
    return String(viteWsBase).replace(/\/$/, "");
  }
  if (apiQuery) {
    try {
      const url = new URL(apiQuery);
      const proto = url.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${url.host}`;
    } catch {
      // Fall through.
    }
  }
  const wsProto = locationProtocol === "https:" ? "wss:" : "ws:";
  if (locationHostname && locationHostname !== "localhost" && locationHostname !== "127.0.0.1") {
    return `${wsProto}//${locationHostname}`;
  }
  return `${wsProto}//127.0.0.1:${backendPort || "8000"}`;
}
