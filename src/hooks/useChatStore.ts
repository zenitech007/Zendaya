/// <reference types="vite/client" />
// hooks/useChatStore.ts
import { create } from "zustand";
import { supabase } from "../lib/supabaseClient";
import type { Message, ChatState, ResponseMode } from "../types";
import { OpusRecorderWrapper } from "../utils/opusEncoderWrapper";

/**
 * Environment
 */
// compute API base
const WS_BASE = import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000";
const API_BASE_URL = WS_BASE.replace(/^wss?:\/\//, (m: string) => m.startsWith("wss") ? "https://" : "http://").replace(/\/$/, "");

const WS_URL = import.meta.env.VITE_WS_BACKEND_URL || "ws://127.0.0.1:8000";
const VOICE_WS_URL = import.meta.env.VITE_VOICE_WS_URL || WS_URL;

/**
 * Types for the store (merged chat + voice)
 */
type SharedVoiceState = {
  isListening: boolean;
  isSpeaking: boolean;
  isMicMuted: boolean;
  isVoiceConnected: boolean;
  currentAmplitude: number;
  isSpeakerMuted: boolean;
  useVoiceId?: boolean;
};

type NewVoiceState = {
  wsId?: string | null;
  // internal state exposed
  ws?: WebSocket | null;
  micStream?: MediaStream | null;
  initialized: boolean;
  backoffMillis: number;
};

type ChatStoreState = ChatState & SharedVoiceState & NewVoiceState & {
  allowMemories: boolean;
};

type ChatStoreActions = {
  // chat
  addMessage: (msg: Message) => void;
  addOptimisticMessage: (m: Omit<Message, "id" | "created_at" | "session_id">) => Message;
  updateMessage: (id: string, text: string, meta?: any) => void;
  removeMessage: (id: string) => void;
  setMessages: (messages: Message[]) => void;
  setSessionId: (id: string | null) => void;
  setIsLoading: (v: boolean) => void;
  setIsStreaming: (v: boolean) => void;
  setError: (err: string | null) => void;
  setIsSending: (v: boolean) => void;
  toggleSidebar: () => void;
  setResponseMode: (m: ResponseMode) => void;
  clearChat: () => Promise<void>;
  addSystemMessage: (text: string, isError?: boolean) => Message;
  setAllowMemories: (v: boolean) => void;

  // voice
  toggleMicMute: () => void;
  toggleSpeakerMute: () => void;
  handleNewTranscript: (text: string) => void;
  // internal setters for UI sync
  setIsListening: (v: boolean) => void;
  setIsSpeaking: (v: boolean) => void;
  setIsVoiceConnected: (v: boolean) => void;
  setCurrentAmplitude: (level: number) => void;
  playBase64Audio?: (base64: string, contentType?: string) => Promise<void> | void;

  // voice lifecycle
  init: () => void;
  connectVoice: () => void;
  disconnectVoice: () => void;
  startListening: () => Promise<void>;
  stopListening: () => void;
  synthesizeAndPlay: (text: string, autoSpeak?: boolean) => void;
  sendAudioChunk: (chunk: ArrayBuffer) => void;
  enableVoiceId: (enabled?: boolean) => void;
};

/**
 * Exported combined store
 */
export const useChatStore = create<ChatStoreState & ChatStoreActions>((set, get) => {
  // --- Internal non-reactive vars (avoid putting these into state) ---
  let reconnectTimer: number | null = null;
  let wsInstance: WebSocket | null = null;
  let vadAudioCtx: AudioContext | null = null;
  let analyser: AnalyserNode | null = null;
  let processorNode: ScriptProcessorNode | null = null;
  let vadLoopHandle: number | null = null;
  let playbackAudioCtx: AudioContext | null = null;
  let opusEncoder: OpusRecorderWrapper | null = null;
  // VAD silence tracker (counts consecutive low-energy frames)
  let silenceFrames = 0;
  // Ensure we tell the server we want streaming (one-time per session)
  let sessionStreamModeSent = false;

  // --- Helpers ---

  const createWebSocket = (sessionId: string) => {
    // NOTE: Server should accept ?session=... and route events
    const url = `${VOICE_WS_URL.replace(/\/$/, "")}/ws/voice?session=${encodeURIComponent(sessionId)}`;
    const ws = new WebSocket(url);
    // We will send binary audio; keep binaryType flexible
    ws.binaryType = "arraybuffer";

    ws.onopen = () => {
      console.log("[ChatStore] Voice WS open");
      wsInstance = ws;
      set({ ws: wsInstance, backoffMillis: 1000, isVoiceConnected: true });
      get().addSystemMessage("Voice connection established.");
      // Notify server we intend to stream live audio (only once per session)
      try {
        if (!sessionStreamModeSent) {
          ws.send(JSON.stringify({ type: "stream_mode" }));
          sessionStreamModeSent = true;
          console.log("[ChatStore] stream_mode sent to server");
        }
      } catch (e) {
        console.warn("[ChatStore] failed to send stream_mode", e);
      }

      if ((get() as any).allowMemories) {
        try { ws.send(JSON.stringify({ type: "enable_memory", user_id: get().sessionId })); } catch(e) {}
      }
    };

    ws.onmessage = (evt) => {
      try {
        if (typeof evt.data === "string") {
          // Common pattern: server sends JSON control messages
          const parsed = JSON.parse(evt.data);
          handleServerEvent(parsed);
        } else if (evt.data instanceof ArrayBuffer) {
          // Binary audio (raw PCM / opus, depending on server)
          // If server sends binary TTS, we decode/play it
          playArrayBufferAudio(evt.data);
        } else {
          console.warn("[ChatStore] Unknown ws message type", typeof evt.data);
        }
      } catch (e) {
        console.error("[ChatStore] ws message parse error", e);
      }
    };

    ws.onclose = (ev) => {
      console.warn("[ChatStore] Voice WS closed", ev.reason);
      wsInstance = null;
      set({ ws: null, isVoiceConnected: false });
      scheduleReconnect();
    };

    ws.onerror = (err) => {
      console.error("[ChatStore] Voice WS error", err);
      get().addSystemMessage("Voice socket error.", true);
    };

    return ws;
  };

  const scheduleReconnect = () => {
    const backoff = get().backoffMillis ?? 1000;
    if (reconnectTimer) return;
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      const sessionId = get().sessionId;
      if (sessionId) {
        try {
          createWebSocket(sessionId);
          set({ backoffMillis: Math.min(backoff * 2, 30000) });
        } catch (e) {
          console.error("[ChatStore] reconnect failed", e);
          scheduleReconnect();
        }
      }
    }, backoff);
  };

  const handleServerEvent = (msg: any) => {
    // This function is the single place we adapt backend events.
    // Your backend currently sends final-only transcriptions and TTS responses.
    // Example message shapes:
    // { type: 'final_transcription', text: 'hello' }
    // { type: 'audio_base64', content_type: 'audio/wav', base64: '...' }
    // { type: 'event', name: 'something', data: {...} }
    // Adapt as required.

    if (!msg || typeof msg.type !== "string") return;

    switch (msg.type) {
      // ✅ NEW: Add this case to handle the server's acknowledgment
      case "stream_mode_ack":
        console.log("[ChatStore] Server acknowledged stream mode.");
        break;
      // END of new case

      case "final_transcription":
        if (msg.text) {
          get().handleNewTranscript(msg.text);
        }
        break;

      case "partial_transcription":
        // optional: if server sends partials
        // you could dispatch an event or store partial UI
        window.dispatchEvent(new CustomEvent("voice_partial", { detail: msg.text }));
        break;

      case "voice_response": // server returning base64 TTS
        // expected { type: 'voice_response', audio_base64: '...', content_type: 'audio/mpeg' }
        get().playBase64Audio?.(msg.audio_base64, msg.content_type);
        break;

      case "system":
        get().addSystemMessage(msg.message || "System event");
        break;

      default:
        console.log("[ChatStore] Unhandled server event:", msg);
    }
  };

  const playArrayBufferAudio = async (buffer: ArrayBuffer) => {
    if (get().isSpeakerMuted) return;
    try {
      if (!playbackAudioCtx) {
        playbackAudioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      await playbackAudioCtx.resume();
      // Try decoding as audio data (works if server encodes WAV/PCM container)
      try {
        const audioBuffer = await playbackAudioCtx.decodeAudioData(buffer.slice(0));
        get().setIsSpeaking(true);
        const src = playbackAudioCtx.createBufferSource();
        src.buffer = audioBuffer;
        src.connect(playbackAudioCtx.destination);
        src.start();
        src.onended = () => get().setIsSpeaking(false);
      } catch (decodeErr) {
        console.warn("[ChatStore] decodeAudioData failed; server likely sent raw Opus/PCM container", decodeErr);
        // if decode fails, try fallback (you may need to handle raw Opus with a lib)
        get().addSystemMessage("Received audio but could not decode client-side.", true);
      }
    } catch (e) {
      console.error("[ChatStore] playArrayBufferAudio error", e);
    }
  };

  const playBase64Audio = async (base64: string, contentType = "audio/wav") => {
    if (get().isSpeakerMuted) return;
    try {
      const binary = window.atob(base64);
      const len = binary.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
      await playArrayBufferAudio(bytes.buffer);
    } catch (e) {
      console.error("[ChatStore] playBase64Audio error", e);
    }
  };

  const encodePCMToOpusIfAvailable = async (pcm: Float32Array) => {
    // Placeholder: if you want client-side Opus encoding, load a WASM encoder here.
    // Return an ArrayBuffer ready to send to server (Opus packet).
    // If encoder isn't provided, we return null to signal fallback to raw PCM.
    if (!opusEncoder) {
      return null;
    }
    try {
      // Some encoders accept Float32Array, others expect Int16Array PCM.
      // Try Float32 first; if it fails, convert to Int16 and retry.
      if (typeof (opusEncoder as any).encode === "function") {
        try {
          return (opusEncoder as any).encode(pcm);
        } catch (err) {
          // fallback: try int16 path
          try {
            const i16 = float32ToInt16(pcm);
            return (opusEncoder as any).encode(i16);
          } catch (err2) {
            console.error("[Opus] encoding error (float32 and int16 attempts failed)", err, err2);
            return null;
          }
        }
      }

      // If encoder exposes encodeInt16 or similar, try that
      if (typeof (opusEncoder as any).encodeInt16 === "function") {
        const i16 = float32ToInt16(pcm);
        return (opusEncoder as any).encodeInt16(i16);
      }

      // Unknown encoder API
      console.warn("[Opus] encoder present but no known encode method");
      return null;
    } catch (err) {
      console.error("[Opus] encoding error", err);
      return null;
    }
  };

  const convertUint8ToFloat32 = (u8: Uint8Array): Float32Array => {
    const out = new Float32Array(u8.length);
    for (let i = 0; i < u8.length; i++) {
      // Convert unsigned 8-bit centered at 128 to float32 [-1,1]
      out[i] = (u8[i] - 128) / 128;
    }
    return out;
  };

  const float32ToInt16 = (float32: Float32Array): Int16Array => {
    const out = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {
      let s = Math.max(-1, Math.min(1, float32[i]));
      out[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }
    return out;
  };

  const sendBinaryToServer = (buf: ArrayBuffer) => {
    try {
      const ws = wsInstance ?? get().ws;
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(buf);
      }
    } catch (e) {
      console.error("[ChatStore] sendBinaryToServer error", e);
    }
  };

  // --- Initial state ---
  const initial: ChatStoreState = {
    // ChatState (keep shape compatible with your app)
    messages: [],
    sessionId: null,
    isLoading: true,
    isStreaming: false,
    error: null,
    isSending: false,
    isSidebarOpen: true,
    responseMode: "dual" as ResponseMode,
    allowMemories: false,

    // SharedVoiceState
    isListening: false,
    isSpeaking: false,
    isMicMuted: false,
    isVoiceConnected: false,
    currentAmplitude: 0,
    isSpeakerMuted: false,
	useVoiceId: false,

    // NewVoiceState
    ws: null,
    micStream: undefined,
    initialized: false,
    backoffMillis: 1000,
  };

  // --- Store implementation (actions) ---
  return {
    ...initial,

    // ----- Internal mutators (exposed) -----
    setIsListening: (isListening: boolean) => set({ isListening }),
    setIsSpeaking: (isSpeaking: boolean) => set({ isSpeaking }),
    setIsVoiceConnected: (isConnected: boolean) => set({ isVoiceConnected: isConnected }),
    setCurrentAmplitude: (level: number) => set({ currentAmplitude: level }),
	toggleMicMute: () => set((s) => ({ isMicMuted: !s.isMicMuted })),
	toggleSpeakerMute: () => set((s) => ({ isSpeakerMuted: !s.isSpeakerMuted })),
	enableVoiceId: (enabled = true) => {
		try {
		  const ws = wsInstance ?? get().ws;
		  if (ws && ws.readyState === WebSocket.OPEN) {
			ws.send(JSON.stringify({ type: "enable_voice_id", enabled }));
			set({ useVoiceId: enabled });
			get().addSystemMessage(`Voice ID ${enabled ? "enabled" : "disabled"}.`);
		  } else {
			get().addSystemMessage("Voice core not connected; cannot set voice ID.", true);
		  }
		} catch (e) {
		  console.error("[ChatStore] enableVoiceId error", e);
		  get().addSystemMessage("Failed to send voice ID request.", true);
		}
	},

    // ----- Chat actions -----
    setMessages: (messages) => set({ messages }),
    setSessionId: (sessionId) => set({ sessionId }),
    setIsLoading: (isLoading) => set({ isLoading }),
    setIsStreaming: (isStreaming) => set({ isStreaming }),
    setError: (error) => set({ error }),
    setIsSending: (isSending) => set({ isSending }),
    toggleSidebar: () => set((s) => ({ isSidebarOpen: !s.isSidebarOpen })),
    setResponseMode: (mode) => set({ responseMode: mode }),
    setAllowMemories: (v: boolean) => set({ allowMemories: v }),
    addMessage: (message) => set((s) => ({ messages: [...s.messages, message] })),
    addOptimisticMessage: (message) => {
      const optimisticId = `optimistic-${Date.now()}`;
      const newMsg: Message = {
        ...message,
        id: optimisticId,
        created_at: new Date().toISOString(),
        session_id: get().sessionId ?? "unknown",
      } as Message;
      set((s) => ({ messages: [...s.messages, newMsg] }));
      return newMsg;
    },
    updateMessage: (id, newText, newMeta) => {
      set((s) => ({
        messages: s.messages.map((m) => (m.id === id ? { ...m, text: newText, meta: newMeta ? { ...m.meta, ...newMeta } : m.meta } : m)),
      }));
    },
    removeMessage: (id) => set((s) => ({ messages: s.messages.filter((m) => m.id !== id) })),
    clearChat: async () => {
      const sid = get().sessionId;
      if (!sid) return;
      set({ messages: [], error: null, isLoading: true });
      try {
        const { error } = await supabase.from("messages").delete().eq("session_id", sid);
        if (error) throw error;
        set({ isLoading: false });
      } catch (err: any) {
        console.error("clearChat error", err);
        set({ error: "Failed to clear chat history.", isLoading: false });
      }
    },
    addSystemMessage: (text, isError = false) => {
      const sys: Message = {
        id: `system-${Date.now()}`,
        created_at: new Date().toISOString(),
        session_id: get().sessionId ?? "system",
        role: "system",
        text,
        meta: isError ? { error: true } : undefined,
      } as Message;
      set((s) => ({ messages: [...s.messages, sys] }));
      return sys;
    },

    // ----- Legacy transcript handler (keeps behavior) -----
    handleNewTranscript: (text: string) => {
      if (!text || !text.trim()) return;
      get().addOptimisticMessage({ role: "user", text });
      try {
        if ((get() as any).allowMemories) {
          // best-effort, non-blocking
          fetch(`${API_BASE_URL}/memory/ingest`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              content: text,
              user_id: get().sessionId,
              source: "conversation",
              type: "utterance",
              summary: text.slice(0, 300),
              privacy_level: "default"
            })
          }).catch((e) => console.warn("memory ingest failed", e));
        }
      } catch (e) {
        console.warn("memory ingest error", e);
      }
      window.dispatchEvent(new CustomEvent("newTranscriptForAI", { detail: text }));
      try {
        get().synthesizeAndPlay(text, true);
      } catch (e) {
        console.error("[ChatStore] auto-talkback synth error", e);
      }
    },

    // ----- Playback helpers -----
    playBase64Audio: playBase64Audio,

    synthesizeAndPlay: (text: string, autoSpeak = true) => {
      // Ask the server to synthesize (control message)
      // Expected backend contract:
      // { type: 'synthesize', text: '...' } -> server will respond with voice_response or binary audio
      try {
        const ws = wsInstance ?? get().ws;
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "synthesize", text }));
        } else {
          // Option: fallback to HTTP TTS endpoint if available
          get().addSystemMessage("Voice core not connected; cannot synthesize.", true);
        }
      } catch (e) {
        console.error("[ChatStore] synthesizeAndPlay error", e);
      }
    },

    // ----- Store lifecycle -----
    init: () => {
      if (!opusEncoder) opusEncoder = new OpusRecorderWrapper();
    },

    connectVoice: () => {
      const sid = get().sessionId;
      if (!sid) {
        console.warn("[ChatStore] connectVoice: no sessionId");
        return;
      }
      if (wsInstance || get().ws) {
        // If the socket is present in the store but we haven't yet told the server
        // we intend to stream, send the one-time stream_mode control using the
        // store-held WebSocket. This covers cases where wsInstance isn't set but
        // the reactive `ws` is available.
        try {
          if (!sessionStreamModeSent) {
            const ws = get().ws;
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "stream_mode" }));
              sessionStreamModeSent = true;
              console.log("[ChatStore] stream_mode sent to server from connectVoice");
            }
          }
        } catch (e) {
          console.warn("[ChatStore] failed to send stream_mode in connectVoice", e);
        }

        console.log("[ChatStore] connectVoice: already connected");
        return;
      }
      try {
        createWebSocket(sid);
      } catch (e) {
        console.error("[ChatStore] connectVoice create error", e);
        scheduleReconnect();
      }
    },

    disconnectVoice: () => {
      console.log("[ChatStore] disconnectVoice");
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      if (wsInstance) {
        wsInstance.close();
        wsInstance = null;
      }
      // reset stream-mode flag so a reconnect will re-negotiate
      sessionStreamModeSent = false;
      if (vadLoopHandle) {
        cancelAnimationFrame(vadLoopHandle);
        vadLoopHandle = null;
      }
      if (vadAudioCtx) {
        try {
          vadAudioCtx.close();
        } catch (e) {}
        vadAudioCtx = null;
      }
      const mic = get().micStream;
      if (mic) mic.getTracks().forEach((t) => t.stop());
      set({ ws: null, micStream: undefined, isListening: false, initialized: false, isVoiceConnected: false });
    },

    // ----- Mic + VAD -----
    startListening: async () => {
      const { isListening, isMicMuted, addSystemMessage } = get();
      if (isListening) return;
      if (isMicMuted) {
        addSystemMessage("Microphone is muted.", true);
        return;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true }).catch((err) => {
        console.error("[ChatStore] mic permission error", err);
        if (err?.name === "NotAllowedError" || err?.name === "PermissionDeniedError") {
          addSystemMessage("Microphone access denied. Please grant permission.", true);
        } else {
          addSystemMessage("Could not access microphone.", true);
        }
        return null;
      });
      if (!stream) return;

      set({ micStream: stream, isListening: true });

      // If the voice websocket is already open, ensure the server knows we want
      // live streaming mode. The server may require this control message before
      // processing incoming binary audio.
      try {
        const ws = wsInstance ?? get().ws;
        if (ws && ws.readyState === WebSocket.OPEN && !sessionStreamModeSent) {
          ws.send(JSON.stringify({ type: "stream_mode" }));
          sessionStreamModeSent = true;
          console.log("[ChatStore] stream_mode sent to server from startListening");
        }
      } catch (e) {
        console.warn("[ChatStore] failed to send stream_mode in startListening", e);
      }

      try {
        vadAudioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
        const src = vadAudioCtx.createMediaStreamSource(stream);
        analyser = vadAudioCtx.createAnalyser();
        analyser.fftSize = 2048;
        src.connect(analyser);
        const buffer = new Uint8Array(analyser.fftSize);

        // Create a ScriptProcessor to capture audio frames and encode/send via Opus (or fallback)
        try {
          processorNode = (vadAudioCtx.createScriptProcessor || (vadAudioCtx as any).createScriptProcessor).call(vadAudioCtx, 2048, 1, 1);
          src.connect(processorNode);
          processorNode.connect(vadAudioCtx.destination);

          processorNode.onaudioprocess = (e: AudioProcessingEvent) => {
            if (!get().isListening || get().isMicMuted) return;
            const input = e.inputBuffer.getChannelData(0);
            try {
              if (!opusEncoder) opusEncoder = new OpusRecorderWrapper();
              // Preferred synchronous encoder API on the wrapper
              const enc: any = opusEncoder as any;
              if (typeof enc.encodePCM === "function") {
                const packet = enc.encodePCM(input);
                if (packet && packet.buffer) sendBinaryToServer(packet.buffer);
                else if (packet instanceof ArrayBuffer) sendBinaryToServer(packet);
                else {
                  // unknown packet shape -> fallback to raw
                  sendBinaryToServer(input.buffer);
                }
              } else {
                // Fallback: try asynchronous encoder helper
                encodePCMToOpusIfAvailable(input as Float32Array).then((opusPackets) => {
                  try {
                    if (opusPackets) {
                      if (Array.isArray(opusPackets)) {
                        for (const pkt of opusPackets) {
                          if (pkt && (pkt as any).buffer instanceof ArrayBuffer) sendBinaryToServer((pkt as any).buffer);
                          else if (pkt instanceof ArrayBuffer) sendBinaryToServer(pkt);
                        }
                      } else if ((opusPackets as any).byteLength !== undefined) {
                        sendBinaryToServer(opusPackets as ArrayBuffer);
                      } else if ((opusPackets as any).buffer instanceof ArrayBuffer) {
                        sendBinaryToServer((opusPackets as any).buffer);
                      } else {
                        sendBinaryToServer(input.buffer);
                      }
                    } else {
                      sendBinaryToServer(input.buffer);
                    }
                  } catch (innerErr) {
                    console.warn("[ChatStore] async send packet failed", innerErr);
                    sendBinaryToServer(input.buffer);
                  }
                }).catch((err) => {
                  console.error("Opus encode error (async), sending raw PCM fallback", err);
                  sendBinaryToServer(input.buffer);
                });
              }
            } catch (err) {
              console.error("Opus encode error, sending raw PCM fallback", err);
              try { sendBinaryToServer(input.buffer); } catch (sendErr) { console.error(sendErr); }
            }
          };
        } catch (procErr) {
          console.warn("ScriptProcessor not available or failed to create", procErr);
        }

        // keep analyser loop for amplitude UI updates only
        const loop = () => {
          if (!analyser) return;
          analyser.getByteTimeDomainData(buffer);
          // compute energy
          let sum = 0;
          for (let i = 0; i < buffer.length; i++) sum += Math.abs(buffer[i] - 128);
          const energy = sum / buffer.length;
          get().setCurrentAmplitude(energy);

          // Speech start detection: if we're not currently listening and energy
          // spikes above a threshold, begin listening automatically.
          if (!get().isListening && energy > 8) {
            console.log("[VAD] Voice detected — starting stream");
            try {
              get().startListening();
            } catch (e) {
              console.warn('[VAD] startListening failed', e);
            }
          }

          // Speech end detection: if we're currently listening and energy is low for
          // a number of consecutive frames, assume speech ended and stop listening.
          // This helps automatically finalize streams when user stops speaking.
          if (get().isListening && energy < 2) {
            silenceFrames++;
            if (silenceFrames > 20) {
              console.log("[VAD] Silence — stopping stream");
              get().stopListening();
              silenceFrames = 0;
            }
          } else {
            // Reset when energy rises or we're not listening
            silenceFrames = 0;
          }

          vadLoopHandle = requestAnimationFrame(loop);
        };

        loop();
      } catch (e) {
        console.error("[ChatStore] VAD setup failed", e);
        addSystemMessage("Audio context setup failed.", true);
      }
    },

    stopListening: () => {
      console.log("[ChatStore] stopListening");
      const ms = get().micStream;
      if (ms) ms.getTracks().forEach((t) => t.stop());
      if (vadLoopHandle) {
        cancelAnimationFrame(vadLoopHandle);
        vadLoopHandle = null;
      }
      if (processorNode) {
        try {
          processorNode.disconnect();
          processorNode.onaudioprocess = null as any;
        } catch (e) {}
        processorNode = null;
      }
      if (vadAudioCtx) {
        try {
          vadAudioCtx.close();
        } catch (e) {}
        vadAudioCtx = null;
      }
      set({ micStream: undefined, isListening: false });

      // Send finalize marker to server so it knows the stream ended
      if (wsInstance && wsInstance.readyState === WebSocket.OPEN) {
        try {
          wsInstance.send(JSON.stringify({ type: "end_of_stream" }));
        } catch (e) {
          console.warn("[ChatStore] end_of_stream send error", e);
        }
      }
    },

    // manual chunk send (public API)
    sendAudioChunk: (chunk: ArrayBuffer) => {
      try {
        sendBinaryToServer(chunk);
      } catch (e) {
        console.error("[ChatStore] sendAudioChunk error", e);
      }
    },
  };
});

