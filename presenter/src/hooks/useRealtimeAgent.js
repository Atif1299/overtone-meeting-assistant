import { useCallback, useEffect, useRef, useState } from "react";
import { RealtimeClient } from "@openai/realtime-api-beta";
import { WavRecorder, WavStreamPlayer } from "wavtools";

const BARGE_IN_RMS = 0.045;
const BARGE_IN_HOLD_MS = 90;
const ECHO_GUARD_MS = 150;
const BARGE_IN_SPEAKING_GAIN = 1.6;

function pcmRms(mono) {
  if (!mono || !mono.length) return 0;
  let sum = 0;
  for (let i = 0; i < mono.length; i += 1) {
    const sample = mono[i] / 32768;
    sum += sample * sample;
  }
  return Math.sqrt(sum / mono.length);
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
  const speakingStartedAtRef = useRef(0);
  const bargeHoldStartRef = useRef(0);

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
    speakingStartedAtRef.current = 0;
    bargeHoldStartRef.current = 0;
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
        activeRef.current = false;
        setRealtimeStatus("disconnected");
        onStatusChangeRef.current?.("connecting");
      });

      client.on("conversation.interrupted", async () => {
        const trackSampleOffset = await player.interrupt();
        if (trackSampleOffset?.trackId) {
          const { trackId, offset } = trackSampleOffset;
          try {
            await client.cancelResponse(trackId, offset);
          } catch {
            /* ignore */
          }
        }
        isSpeakingRef.current = false;
        speakingStartedAtRef.current = 0;
        bargeHoldStartRef.current = 0;
        onStatusChangeRef.current?.("listening");
      });

      client.on("conversation.updated", async ({ item, delta }) => {
        if (delta?.audio) {
          if (!isSpeakingRef.current) {
            speakingStartedAtRef.current = Date.now();
          }
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
          speakingStartedAtRef.current = 0;
          bargeHoldStartRef.current = 0;
          onStatusChangeRef.current?.("listening");
        }
      });

      const interruptPlayback = async () => {
        try {
          const trackSampleOffset = await player.interrupt();
          if (trackSampleOffset?.trackId) {
            const { trackId, offset } = trackSampleOffset;
            try {
              await client.cancelResponse(trackId, offset);
            } catch {
              /* ignore */
            }
          }
        } catch {
          /* ignore */
        }
        isSpeakingRef.current = false;
        speakingStartedAtRef.current = 0;
        bargeHoldStartRef.current = 0;
        onStatusChangeRef.current?.("listening");
      };

      client.on("realtime.event", ({ event } = {}) => {
        const type = event?.type;
        if (
          type === "input_audio_buffer.speech_started" ||
          type === "response.cancelled" ||
          type === "conversation.interrupted"
        ) {
          void interruptPlayback();
          return;
        }
        if (type === "response.created" || type === "response.audio.delta") {
          if (!isSpeakingRef.current) {
            speakingStartedAtRef.current = Date.now();
          }
          isSpeakingRef.current = true;
          onStatusChangeRef.current?.("speaking");
        }
      });
      await client.connect();
      await recorder.record((data) => {
        const energy = pcmRms(data.mono);
        if (isSpeakingRef.current) {
          const sincePlay = Date.now() - speakingStartedAtRef.current;
          const threshold = BARGE_IN_RMS * BARGE_IN_SPEAKING_GAIN;
          if (sincePlay > ECHO_GUARD_MS && energy > threshold) {
            if (!bargeHoldStartRef.current) {
              bargeHoldStartRef.current = Date.now();
            } else if (Date.now() - bargeHoldStartRef.current >= BARGE_IN_HOLD_MS) {
              bargeHoldStartRef.current = 0;
              void interruptPlayback();
            }
          } else {
            bargeHoldStartRef.current = 0;
          }
        } else {
          bargeHoldStartRef.current = 0;
        }
        client.appendInputAudio(data.mono);
      });

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
      return false;
    }
  }, [enabled, relayUrl, sessionId]);

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
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
      }
    };
    void loop();

    return () => {
      stopped = true;
      void teardown();
    };
  }, [enabled, sessionId, setup, teardown]);

  return { realtimeStatus, teardown };
}
