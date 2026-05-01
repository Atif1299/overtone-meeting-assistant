import { useCallback, useEffect, useRef, useState } from "react";
import { RealtimeClient } from "@openai/realtime-api-beta";
import { WavRecorder, WavStreamPlayer } from "wavtools";

export function useRealtimeAgent({
  enabled,
  sessionId,
  relayUrl,
  onAssistantText,
  onStatusChange,
  onError,
}) {
  const [realtimeStatus, setRealtimeStatus] = useState("disconnected");
  const clientRef = useRef(null);
  const recorderRef = useRef(null);
  const playerRef = useRef(null);
  const activeRef = useRef(false);
  const onAssistantTextRef = useRef(onAssistantText);
  const onStatusChangeRef = useRef(onStatusChange);
  const onErrorRef = useRef(onError);
  const isSpeakingRef = useRef(false);

  onAssistantTextRef.current = onAssistantText;
  onStatusChangeRef.current = onStatusChange;
  onErrorRef.current = onError;

  const teardown = useCallback(() => {
    const client = clientRef.current;
    const recorder = recorderRef.current;
    const player = playerRef.current;

    // Clear refs immediately so setup() guards see null, but keep activeRef = true
    // until async cleanup fully completes — prevents a second mount's setup() from
    // racing in and creating a second player while the old one is still playing.
    clientRef.current = null;
    recorderRef.current = null;
    playerRef.current = null;

    const cleanup = async () => {
      isSpeakingRef.current = false;
      try {
        if (recorder?.recording) await recorder.pause();
      } catch {
        /* ignore */
      }
      try {
        await recorder?.end?.();
      } catch {
        /* ignore */
      }
      try {
        await player?.interrupt?.();
      } catch {
        /* ignore */
      }
      try {
        await player?.disconnect?.();
      } catch {
        /* ignore */
      }
      try {
        client?.disconnect?.();
        client?.reset?.();
      } catch {
        /* ignore */
      }
      // Release the slot only after the old player is fully silenced.
      activeRef.current = false;
      setRealtimeStatus("disconnected");
    };
    void cleanup();
  }, []);

  const setup = useCallback(async () => {
    if (!enabled || !sessionId || !relayUrl || activeRef.current) return;
    // Claim the slot synchronously before any await so a concurrent call
    // (e.g. StrictMode's second mount) sees it and bails out immediately.
    activeRef.current = true;

    const client = new RealtimeClient({ url: relayUrl });
    const recorder = new WavRecorder({ sampleRate: 24000 });
    const player = new WavStreamPlayer({ sampleRate: 24000 });
    clientRef.current = client;
    recorderRef.current = recorder;
    playerRef.current = player;
    setRealtimeStatus("connecting");
    onStatusChangeRef.current?.("connecting");

    try {
      await recorder.begin();
      await player.connect();

      client.on("error", (event) => {
        console.error("Realtime client error", event);
        isSpeakingRef.current = false;
        setRealtimeStatus("disconnected");
        onErrorRef.current?.("Realtime relay error");
      });

      client.on("disconnected", () => {
        isSpeakingRef.current = false;
        setRealtimeStatus("disconnected");
      });

      // Matches reference voice-agent-demo: interrupt player, cancel response.
      // Do NOT gate the mic — pausing it breaks the interrupt loop because
      // speech_started never fires and cancelled items never reach "completed".
      client.on("conversation.interrupted", async () => {
        const trackSampleOffset = await player.interrupt();
        if (trackSampleOffset?.trackId) {
          const { trackId, offset } = trackSampleOffset;
          await client.cancelResponse(trackId, offset);
        }
        isSpeakingRef.current = false;
        onStatusChangeRef.current?.("listening");
      });

      client.on("conversation.updated", async ({ item, delta }) => {
        if (delta?.audio) {
          isSpeakingRef.current = true;
          onStatusChangeRef.current?.("speaking");
          player.add16BitPCM(delta.audio, item.id);
        }
        if (item?.role === "assistant") {
          const assistantText =
            item?.formatted?.transcript ||
            item?.formatted?.text ||
            item?.formatted?.output_text ||
            "";
          if (assistantText) {
            onAssistantTextRef.current?.(assistantText);
          }
        }
        if (item?.status === "completed") {
          isSpeakingRef.current = false;
          onStatusChangeRef.current?.("listening");
        }
      });

      await client.connect();
      await recorder.record((data) => client.appendInputAudio(data.mono));

      setRealtimeStatus("connected");
      onStatusChangeRef.current?.("listening");
    } catch (error) {
      console.error("Failed to initialize realtime agent", error);
      const isMicIssue =
        String(error?.message || "").toLowerCase().includes("permission") ||
        String(error?.name || "").toLowerCase().includes("notallowed");
      setRealtimeStatus(isMicIssue ? "mic_denied" : "disconnected");
      onStatusChangeRef.current?.("connecting");
      onErrorRef.current?.(
        isMicIssue
          ? "Microphone permission denied in meeting browser"
          : "Failed to initialize realtime voice agent"
      );
      activeRef.current = false;
    }
  }, [enabled, relayUrl, sessionId]);

  useEffect(() => {
    if (!enabled || !sessionId) return undefined;
    void setup();
    return () => {
      teardown();
    };
  }, [enabled, sessionId, setup, teardown]);

  return { realtimeStatus, teardown };
}
