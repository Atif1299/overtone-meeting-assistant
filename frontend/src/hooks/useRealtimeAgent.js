import { useCallback, useEffect, useRef, useState } from "react";
import { RealtimeClient } from "@openai/realtime-api-beta";
import { WavRecorder, WavStreamPlayer } from "wavtools";

function markInactive(activeRef, setRealtimeStatus, onStatusChangeRef) {
  activeRef.current = false;
  setRealtimeStatus("disconnected");
  onStatusChangeRef.current?.("connecting");
}

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

  const teardown = useCallback(async () => {
    const client = clientRef.current;
    const recorder = recorderRef.current;
    const player = playerRef.current;
    clientRef.current = null;
    recorderRef.current = null;
    playerRef.current = null;
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
    activeRef.current = false;
    setRealtimeStatus("disconnected");
  }, []);

  const setup = useCallback(async () => {
    if (!enabled || !sessionId || !relayUrl || activeRef.current) return false;
    activeRef.current = true;

    const client = new RealtimeClient({ url: relayUrl });
    const recorder = new WavRecorder({ sampleRate: 24000 });
    const player = new WavStreamPlayer({ sampleRate: 24000 });
    clientRef.current = client;
    recorderRef.current = recorder;
    playerRef.current = player;
    setRealtimeStatus("connecting");
    onStatusChangeRef.current?.("connecting");

    const forceInactive = () => {
      markInactive(activeRef, setRealtimeStatus, onStatusChangeRef);
    };

    try {
      await recorder.begin();
      await player.connect();

      client.on("error", (event) => {
        console.error("Realtime client error", event);
        isSpeakingRef.current = false;
        onErrorRef.current?.("Realtime relay error");
        forceInactive();
      });

      client.on("disconnected", () => {
        isSpeakingRef.current = false;
        forceInactive();
      });

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

      client.on("realtime.event", ({ event } = {}) => {
        const type = event?.type;
        if (type === "input_audio_buffer.speech_started") {
          onStatusChangeRef.current?.("listening");
        }
        if (type === "response.created" || type === "response.audio.delta") {
          onStatusChangeRef.current?.("speaking");
        }
      });

      await client.connect();

      // If the relay closes the socket without emitting "disconnected", force reconnect.
      const socket =
        client?.realtime?.ws ||
        client?.realtime?.socket ||
        client?.ws ||
        null;
      if (socket && typeof socket.addEventListener === "function") {
        socket.addEventListener("close", () => {
          isSpeakingRef.current = false;
          forceInactive();
        });
      }

      await recorder.record((data) => client.appendInputAudio(data.mono));

      setRealtimeStatus("connected");
      onStatusChangeRef.current?.("listening");
      return true;
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
      try {
        client?.disconnect?.();
        client?.reset?.();
      } catch {
        /* ignore */
      }
      return false;
    }
  }, [enabled, relayUrl, sessionId]);

  const interruptPlayback = useCallback(async () => {
    const player = playerRef.current;
    const client = clientRef.current;
    try {
      const trackSampleOffset = await player?.interrupt?.();
      if (trackSampleOffset?.trackId && client) {
        const { trackId, offset } = trackSampleOffset;
        await client.cancelResponse?.(trackId, offset);
      }
    } catch {
      /* ignore */
    }
    isSpeakingRef.current = false;
    onStatusChangeRef.current?.("listening");
  }, []);

  useEffect(() => {
    if (!enabled || !sessionId) return undefined;
    let stopped = false;

    const loop = async () => {
      while (!stopped) {
        const ok = await setup();
        if (stopped) break;
        if (!ok) {
          await new Promise((resolve) => window.setTimeout(resolve, 1500));
          continue;
        }
        while (!stopped && activeRef.current) {
          await new Promise((resolve) => window.setTimeout(resolve, 500));
        }
        if (stopped) break;
        await teardown();
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
    };
    void loop();

    return () => {
      stopped = true;
      void teardown();
    };
  }, [enabled, sessionId, setup, teardown]);

  return { realtimeStatus, teardown, interruptPlayback };
}
