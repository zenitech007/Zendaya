import { useEffect, useRef } from "react";
import { useZendaya, type AiState, type BodyAction } from "../store/zendayaStore";
import { normaliseVisemes } from "../store/normaliseVisemes";
import { voicePlayer } from "../audio/voicePlayer";
import {
  openMap, goHome, openModule, setThemeById, dock, undock,
  showTerminal, hideTerminal, activateVoice, deactivateVoice,
  minimize, restore, showNotification,
} from "../commands/hudControls";

const WS_URL =
  new URLSearchParams(location.search).get("ws") ||
  "ws://127.0.0.1:7475/ws";

const VALID_AI: AiState[] = ["idle", "aware", "listening", "thinking", "speaking", "searching", "mapping", "alert", "error"];
const VALID_BODY: BodyAction[] = ["nod", "shake", "wave", "shrug"];

// Connects to the Python state server's /ws endpoint and translates each
// payload into store mutations. Single connection per app, with auto-reconnect.
export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let stopped = false;
    let backoff = 800;
    let heartbeat: ReturnType<typeof setInterval> | null = null;

    function clearHeartbeat() {
      if (heartbeat !== null) {
        clearInterval(heartbeat);
        heartbeat = null;
      }
    }

    function connect() {
      if (stopped) return;
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        useZendaya.getState().setConnected(true);
        backoff = 800;
        clearHeartbeat();
        heartbeat = setInterval(() => {
          if (ws.readyState === 1) ws.send(JSON.stringify({ ping: true }));
        }, 10000);
        ws.addEventListener("close", clearHeartbeat);
      };

      ws.onclose = () => {
        clearHeartbeat();
        useZendaya.getState().setConnected(false);
        wsRef.current = null;
        if (!stopped) {
          window.setTimeout(connect, backoff);
          backoff = Math.min(backoff * 1.6, 8000);
        }
      };

      ws.onerror = () => {
        try {
          ws.close();
        } catch {
          /* ignore */
        }
      };

      ws.onmessage = (ev) => {
        let data: any;
        try {
          data = JSON.parse(ev.data);
        } catch {
          return;
        }
        const z = useZendaya.getState();

        if (typeof data.state === "string") {
          const s = data.state as AiState;
          if (VALID_AI.includes(s)) z.setAi(s);
        }
        if (typeof data.text === "string" && data.text.length > 0) {
          z.setText(data.text);
        }
        if (typeof data.audio_level === "number") {
          z.setAudioLevel(Math.max(0, Math.min(1, data.audio_level)));
        }
        if (typeof data.panel === "string") {
          z.setPanel(data.panel);
        }
        if (typeof data.action === "string") {
          dispatchAction(data.action, data.payload ?? {});
        }
        if ("now_playing" in data) {
          const np = data.now_playing;
          if (np === null) {
            z.setNowPlaying(null);
          } else if (np && typeof np === "object" && typeof np.track === "string") {
            z.setNowPlaying({
              track: np.track,
              artist: np.artist ?? "",
              album: np.album,
              artUrl: np.art_url,
              is_playing: !!np.is_playing,
              progress_ms: np.progress_ms ?? 0,
              duration_ms: np.duration_ms ?? 0,
              source: np.source === "local" ? "local" : "spotify",
              streamUrl: typeof np.stream_url === "string" ? np.stream_url : undefined,
              trackId: typeof np.track_id === "string" ? np.track_id : undefined,
            });
          }
        }
        if (typeof data.amplitude === "number") {
          z.setAudioLevel(Math.max(0, Math.min(1, data.amplitude)));
        }
        if (data.visemes && typeof data.visemes === "object" && !Array.isArray(data.visemes)) {
          z.setVisemes(normaliseVisemes(data.visemes));
        }
        if (data.telemetry !== undefined && (data.telemetry === null || typeof data.telemetry === "object")) {
          z.setTelemetry(data.telemetry as any);
        }
        if (data.perception !== undefined && (data.perception === null || typeof data.perception === "object")) {
          z.setPerception(data.perception as any);
        }
        if (typeof data.body_action === "string" && (VALID_BODY as string[]).includes(data.body_action)) {
          z.firePulseBodyAction(data.body_action as BodyAction);
        }
        if (data.audio && typeof data.audio === "object" && !Array.isArray(data.audio)) {
          // Teed TTS PCM — play directly via the singleton, NOT through the
          // store (a chunk arrives every ~90 ms; routing through Zustand would
          // re-render the whole tree each time).
          voicePlayer.handle(data.audio);
        }
      };
    }

    connect();
    return () => {
      stopped = true;
      clearHeartbeat();
      try {
        wsRef.current?.close();
      } catch {
        /* ignore */
      }
      wsRef.current = null;
    };
  }, []);
}

// Blueprint actions → store mutations, routed through the shared hudControls
// module (the same functions the in-HUD slash commands use). The visual
// reactions themselves live in the scene + chrome components which subscribe to
// the store and animate on change.
export function dispatchAction(action: string, payload: Record<string, any>) {
  switch (action) {
    case "open_map":
      openMap();
      break;
    case "close_map":
      goHome();
      break;
    case "open_module":
      openModule(
        typeof payload.name === "string" ? payload.name : "",
        typeof payload.corner === "string" ? payload.corner : undefined,
      );
      break;
    case "close_module":
      goHome();
      break;
    case "dock_orb":
      dock();
      break;
    case "undock_orb":
      undock();
      break;
    case "show_terminal":
      showTerminal();
      break;
    case "hide_terminal":
      hideTerminal();
      break;
    case "activate_voice":
      activateVoice();
      break;
    case "deactivate_voice":
      deactivateVoice();
      break;
    case "minimize_ui":
      minimize();
      break;
    case "restore_ui":
      restore();
      break;
    case "show_notification":
      showNotification(typeof payload.text === "string" ? payload.text : "");
      break;
    case "set_theme":
      setThemeById(typeof payload.name === "string" ? payload.name : "");
      break;
    case "music_control": {
      const cmd = typeof payload.cmd === "string" ? payload.cmd : "";
      if (cmd === "play" || cmd === "pause" || cmd === "next" || cmd === "prev") {
        useZendaya.getState().pushMusicCmd(cmd);
      }
      break;
    }
    default:
      // unknown action — ignore silently
      break;
  }
}
