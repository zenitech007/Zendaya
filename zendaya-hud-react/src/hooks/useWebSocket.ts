import { useEffect, useRef } from "react";
import { useZendaya, type AiState, type ModuleId, type DockCorner, type BodyAction } from "../store/zendayaStore";
import { normaliseVisemes } from "../store/normaliseVisemes";

const WS_URL =
  new URLSearchParams(location.search).get("ws") ||
  "ws://127.0.0.1:7475/ws";

const VALID_AI: AiState[] = ["idle", "aware", "listening", "thinking", "speaking", "searching", "mapping", "alert", "error"];

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
            });
          }
        }
        if (typeof data.amplitude === "number") {
          z.setAudioLevel(Math.max(0, Math.min(1, data.amplitude)));
        }
        if (data.visemes && typeof data.visemes === "object") {
          z.setVisemes(normaliseVisemes(data.visemes));
        }
        if (data.telemetry !== undefined && (data.telemetry === null || typeof data.telemetry === "object")) {
          z.setTelemetry(data.telemetry as any);
        }
        if (data.perception !== undefined && (data.perception === null || typeof data.perception === "object")) {
          z.setPerception(data.perception as any);
        }
        if (typeof data.body_action === "string" && data.body_action) {
          z.firePulseBodyAction(data.body_action as BodyAction);
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

// Blueprint actions → store mutations. The visual timelines themselves
// live in components/animations (they read the store and animate on change).
function dispatchAction(action: string, payload: Record<string, any>) {
  const z = useZendaya.getState();
  switch (action) {
    case "open_map":
      z.setScene("map");
      z.setActiveModule("map");
      z.setPanel("globe");
      break;
    case "close_map":
      z.setScene("main");
      z.setActiveModule("none");
      z.setPanel("none");
      break;
    case "open_module": {
      const valid: ModuleId[] = ["map", "calculator", "clock", "notes", "weather"];
      const name = typeof payload.name === "string" ? (payload.name as ModuleId) : "none";
      if (valid.includes(name)) {
        if (payload.corner === "bl" || payload.corner === "br") {
          z.setDockCorner(payload.corner as DockCorner);
        }
        z.setActiveModule(name);
        if (name === "map") {
          z.setScene("map");
          z.setPanel("globe");
        }
      }
      break;
    }
    case "close_module":
      z.setActiveModule("none");
      z.setScene("main");
      z.setPanel("none");
      break;
    case "dock_orb":
      z.setDocked(true);
      break;
    case "undock_orb":
      z.setDocked(false);
      break;
    case "show_terminal":
      z.setTerminalOpen(true);
      break;
    case "hide_terminal":
      z.setTerminalOpen(false);
      break;
    case "activate_voice":
      z.setVoiceActive(true);
      break;
    case "deactivate_voice":
      z.setVoiceActive(false);
      break;
    case "minimize_ui":
      z.setMinimized(true);
      break;
    case "restore_ui":
      z.setMinimized(false);
      break;
    case "show_notification": {
      const text = typeof payload.text === "string" ? payload.text : "";
      if (text) z.pushNotification(text);
      break;
    }
    default:
      // unknown action — ignore silently
      break;
  }
}
