import { useEffect, useRef, useState, useCallback } from "react";

const BASE_RETRY_MS = 1000;
const MAX_RETRY_MS = 16000;

export function usePresentationWebSocket(url, onMessage) {
  const [connected, setConnected] = useState(false);
  const wsRef = useRef(null);
  const onMessageRef = useRef(onMessage);
  const retryDelayRef = useRef(BASE_RETRY_MS);
  const retryTimerRef = useRef(null);
  const destroyedRef = useRef(false);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!url) return;
    destroyedRef.current = false;

    function connect() {
      if (destroyedRef.current) return;
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        retryDelayRef.current = BASE_RETRY_MS;
      };

      ws.onclose = () => {
        setConnected(false);
        if (!destroyedRef.current) {
          retryTimerRef.current = window.setTimeout(() => {
            retryDelayRef.current = Math.min(retryDelayRef.current * 2, MAX_RETRY_MS);
            connect();
          }, retryDelayRef.current);
        }
      };

      ws.onerror = () => {
        // onclose fires after onerror — reconnect handled there
        setConnected(false);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data);
          onMessageRef.current?.(data);
        } catch {
          /* ignore */
        }
      };
    }

    connect();

    return () => {
      destroyedRef.current = true;
      if (retryTimerRef.current) window.clearTimeout(retryTimerRef.current);
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [url]);

  const send = useCallback((obj) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(obj));
    }
  }, []);

  return { connected, send };
}
