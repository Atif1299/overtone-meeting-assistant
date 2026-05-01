import { useCallback, useEffect } from "react";
import { usePresentationWebSocket } from "./useWebSocket.js";
import { presentationWsUrl } from "../utils/config.js";

export function usePresentationTransport({
  sessionId,
  onStatus,
  onTranscript,
  onNavigate,
  onAnswer,
  onError,
  onPlayFiller,
  onToolStart,
  onToolDone,
  onMuteChange,
}) {
  const onWsMessage = useCallback(
    (msg) => {
      switch (msg.type) {
        case "status":
          onStatus?.(msg.status || "listening");
          break;
        case "transcript":
          onTranscript?.({
            text: msg.text || "",
            speaker: msg.speaker || null,
            isPartial: Boolean(msg.is_partial),
          });
          break;
        case "navigate":
          if (msg.target_page) onNavigate?.(msg.target_page);
          break;
        case "navigate_and_answer":
          if (msg.target_page) onNavigate?.(msg.target_page);
          onAnswer?.({
            text: msg.answer_text || "",
            audioUrl: msg.audio_url || "",
            sourcePages: msg.source_pages || [],
          });
          break;
        case "answer":
          onAnswer?.({
            text: msg.answer_text || "",
            audioUrl: msg.audio_url || "",
            sourcePages: msg.source_pages || [],
          });
          break;
        case "play_filler":
          onPlayFiller?.(msg.audio_b64);
          break;
        case "tool_start":
          onToolStart?.({ callId: msg.call_id, toolName: msg.tool_name });
          break;
        case "tool_done":
          onToolDone?.({ callId: msg.call_id, toolName: msg.tool_name });
          break;
        case "bot_muted":
          onMuteChange?.(true);
          break;
        case "bot_unmuted":
          onMuteChange?.(false);
          break;
        case "error":
          onError?.(msg.message || "Presentation transport error");
          break;
        default:
          break;
      }
    },
    [onAnswer, onError, onNavigate, onPlayFiller, onStatus, onTranscript, onToolStart, onToolDone, onMuteChange]
  );

  const wsUrl = sessionId ? presentationWsUrl(sessionId) : "";
  const { connected, send } = usePresentationWebSocket(wsUrl, onWsMessage);

  useEffect(() => {
    if (connected && sessionId) {
      send({ type: "ready", session_id: sessionId });
    }
  }, [connected, send, sessionId]);

  return { connected };
}
