import { create } from "zustand";

export type AiState = "idle" | "aware" | "listening" | "thinking" | "speaking" | "searching" | "mapping" | "alert" | "error";

export type SceneId = "main" | "map" | "dashboard";

export type ModuleId =
  | "none"
  | "map"
  | "calculator"
  | "clock"
  | "notes"
  | "weather";

export type DockCorner = "bl" | "br";

export interface Notification {
  id: number;
  text: string;
  ts: number;
}

export interface NowPlaying {
  track: string;
  artist: string;
  album?: string;
  artUrl?: string;
  is_playing: boolean;
  progress_ms: number;
  duration_ms: number;
  source: "spotify" | "local";
}

interface ZendayaState {
  // Live state from backend
  ai: AiState;
  text: string;
  audioLevel: number;
  connected: boolean;

  // UI scenes / panels
  scene: SceneId;
  panel: string;        // "globe" | "none" | ...
  activeModule: ModuleId;
  dockCorner: DockCorner;
  docked: boolean;      // orb docked into the corner?
  voiceActive: boolean; // mic open / waveform visible
  terminalOpen: boolean;
  minimized: boolean;
  speakerAzimuth: number; // 0 is center, -1 is left, 1 is right

  notifications: Notification[];
  nowPlaying: NowPlaying | null;

  // Cinematic atmosphere (blueprint \u00a76 + \u00a77 + \u00a78)
  bgDim: number;        // 0..1; how much to dim/blur background during scene swaps
  fogDensity: number;   // Three.js exponential fog density; tweened by GSAP

  // Adaptive quality (blueprint \u00a710). "high" = full effects + dpr2,
  // "low" = drop bloom intensity + dpr1 when sustained FPS < 45.
  quality: "high" | "low";
  fps: number;

  // setters
  setAi: (s: AiState) => void;
  setText: (t: string) => void;
  setAudioLevel: (l: number) => void;
  setConnected: (b: boolean) => void;
  setScene: (s: SceneId) => void;
  setPanel: (p: string) => void;
  setActiveModule: (m: ModuleId) => void;
  setDockCorner: (c: DockCorner) => void;
  setDocked: (b: boolean) => void;
  setVoiceActive: (b: boolean) => void;
  setTerminalOpen: (b: boolean) => void;
  setMinimized: (b: boolean) => void;
  setSpeakerAzimuth: (a: number) => void;
  pushNotification: (text: string) => void;
  popNotification: (id: number) => void;
  setNowPlaying: (np: NowPlaying | null) => void;
  setBgDim: (v: number) => void;
  setFogDensity: (v: number) => void;
  setQuality: (q: "high" | "low") => void;
  setFps: (n: number) => void;
}

let _nid = 0;

export const useZendaya = create<ZendayaState>((set) => ({
  ai: "idle",
  text: "",
  audioLevel: 0,
  connected: false,

  scene: "main",
  panel: "none",
  activeModule: "none",
  dockCorner: "br",
  docked: false,
  voiceActive: false,
  terminalOpen: false,
  minimized: false,
  speakerAzimuth: 0,

  notifications: [],
  nowPlaying: null,
  bgDim: 0,
  fogDensity: 0.04,
  quality: "high",
  fps: 60,

  setAi: (s) => set({ ai: s }),
  setText: (t) => set({ text: t }),
  setAudioLevel: (l) => set({ audioLevel: l }),
  setConnected: (b) => set({ connected: b }),
  setScene: (s) => set({ scene: s }),
  setPanel: (p) => set({ panel: p }),
  setActiveModule: (m) => set({ activeModule: m, docked: m !== "none" }),
  setDockCorner: (c) => set({ dockCorner: c }),
  setDocked: (b) => set({ docked: b }),
  setVoiceActive: (b) => set({ voiceActive: b }),
  setTerminalOpen: (b) => set({ terminalOpen: b }),
  setMinimized: (b) => set({ minimized: b }),
  setSpeakerAzimuth: (a) => set({ speakerAzimuth: a }),
  pushNotification: (text) =>
    set((s) => ({
      notifications: [
        ...s.notifications,
        { id: ++_nid, text, ts: Date.now() },
      ].slice(-5),
    })),
  popNotification: (id) =>
    set((s) => ({ notifications: s.notifications.filter((n) => n.id !== id) })),
  setNowPlaying: (np) =>
    set((s) => ({
      nowPlaying: np,
      docked: np !== null ? true : s.activeModule !== "none",
    })),
  setBgDim: (v) => set({ bgDim: Math.max(0, Math.min(1, v)) }),
  setFogDensity: (v) => set({ fogDensity: Math.max(0, v) }),
  setQuality: (q) => set({ quality: q }),
  setFps: (n) => set({ fps: n }),
}));
