import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import PresentationStage from "./components/PresentationStage.jsx";
import ToolToasts from "./components/ToolToasts.jsx";
import { usePresentationTransport } from "./hooks/usePresentationTransport.js";
import { useRealtimeAgent } from "./hooks/useRealtimeAgent.js";
import { useSlideNavigation } from "./hooks/useSlideNavigation.js";
import { apiBase, realtimeRelayWsUrl } from "./utils/config.js";

function parseQuery() {
  const q = new URLSearchParams(window.location.search);
  return {
    session: q.get("session") || "",
    presentation: q.get("presentation") || "demo",
    wss: q.get("wss") || "",
    mode: q.get("mode") || "realtime",
  };
}

export default function App() {
  const { session, presentation, wss, mode } = parseQuery();
  const isRealtimeMode = mode !== "webhook";
  const { currentPage, totalPages, setTotalPages, goTo } = useSlideNavigation(1, 20);
  const [status, setStatus] = useState("listening");
  const [transitioning, setTransitioning] = useState(false);
  const [activeTools, setActiveTools] = useState({});
  const [isMuted, setIsMuted] = useState(false);
  const audioRef = useRef(null);

  const playAudio = useCallback((url) => {
    if (!url || !audioRef.current) return;
    const el = audioRef.current;
    el.src = url;
    el.currentTime = 0;
    el.muted = false;
    el.volume = 1;
    el.play().catch((err) => {
      console.warn("Overtone audio playback failed", err);
    });
  }, []);

  useEffect(() => {
    setTransitioning(true);
    const timer = window.setTimeout(() => setTransitioning(false), 280);
    return () => window.clearTimeout(timer);
  }, [currentPage]);

  useEffect(() => {
    const base = apiBase();
    fetch(`${base}/api/v1/presentations/${presentation}`, {
      headers: {
        "ngrok-skip-browser-warning": "69420",
      },
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.total_pages) setTotalPages(data.total_pages);
      })
      .catch(() => {});
  }, [presentation, setTotalPages]);

  const fillerRef = useRef(null);
  const playFillerAudio = useCallback((b64) => {
    if (!b64) return;
    // Stop any currently playing filler to prevent overlap
    if (fillerRef.current) {
      fillerRef.current.pause();
      fillerRef.current = null;
    }
    try {
      const binary = atob(b64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const blob = new Blob([bytes], { type: "audio/mpeg" });
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      audio.volume = 1;
      fillerRef.current = audio;
      audio.play().catch(() => {});
      audio.onended = () => {
        URL.revokeObjectURL(url);
        if (fillerRef.current === audio) fillerRef.current = null;
      };
    } catch (err) {
      console.warn("Filler audio playback failed", err);
    }
  }, []);

  const { connected } = usePresentationTransport({
    sessionId: session,
    onStatus: useCallback((next) => setStatus(next), []),
    onTranscript: useCallback(() => {}, []),
    onNavigate: useCallback((page) => { goTo(page); }, [goTo]),
    onAnswer: useCallback(({ audioUrl }) => {
      if (audioUrl) playAudio(audioUrl);
    }, [playAudio]),
    onPlayFiller: playFillerAudio,
    onToolStart: useCallback(({ callId, toolName }) => {
      console.log("🛠 [FRONTEND] tool_start:", toolName, callId);
      setActiveTools((prev) => ({ ...prev, [callId]: { name: toolName, status: "loading" } }));
    }, []),
    onToolDone: useCallback(({ callId, toolName }) => {
      console.log("✅ [FRONTEND] tool_done:", toolName, callId);
      // Mark as done first
      setActiveTools((prev) => ({ ...prev, [callId]: { name: toolName, status: "done" } }));
      
      // Then remove after 2 seconds
      setTimeout(() => {
        setActiveTools((prev) => {
          const next = { ...prev };
          delete next[callId];
          return next;
        });
      }, 2000);
    }, []),
    onMuteChange: useCallback((muted) => { setIsMuted(muted); }, []),
    onError: useCallback(() => {}, []),
  });

  const relayUrl = session ? wss || realtimeRelayWsUrl(session) : "";
  const { realtimeStatus } = useRealtimeAgent({
    enabled: isRealtimeMode,
    sessionId: session,
    relayUrl,
    onAssistantText: useCallback(() => {}, []),
    onStatusChange: useCallback((nextStatus) => { setStatus(nextStatus); }, []),
    onError: useCallback(() => {}, []),
  });

  const indicatorStatus = useMemo(() => {
    if (!isRealtimeMode) return connected ? status : "connecting";
    if (realtimeStatus === "mic_denied") return "connecting";
    if (realtimeStatus === "connecting") return "connecting";
    if (status === "speaking") return "speaking";
    if (realtimeStatus === "connected") return status || "listening";
    return connected ? status : "connecting";
  }, [connected, isRealtimeMode, realtimeStatus, status]);

  if (!session) {
    return (
      <div className="stage stage-empty">
        <div className="empty-panel">
          <p className="empty-eyebrow">Overtone Output Media</p>
          <h1>Session parameter missing</h1>
          <p>Open this page from the Launch flow so session and presentation params are set.</p>
        </div>
      </div>
    );
  }

  return (
    <>
      <PresentationStage
        presentationId={presentation}
        currentPage={currentPage}
        totalPages={totalPages}
        indicatorStatus={indicatorStatus}
        transition={transitioning}
        audioRef={audioRef}
        isMuted={isMuted}
      />
      <ToolToasts activeTools={activeTools} />
    </>
  );
}
