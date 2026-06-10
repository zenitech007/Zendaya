import { useEffect, useRef, useState } from "react";
import {
  getAiStatus,
  getBodyAction,
  getMouth,
  getPerception,
  getTelemetry,
  getVisemes,
  type AiState,
  type BodyAction,
  type FaceState,
  type Telemetry,
  type VisemeWeights,
} from "../lib/api";

export interface AiStatusView {
  state: AiState;
  text: string;
  connected: boolean;
}

const POLL_MS = 250;

export function useAiStatus(): AiStatusView {
  const [view, setView] = useState<AiStatusView>({
    state: "idle",
    text: "",
    connected: false,
  });
  const lastTextRef = useRef<string>("");

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();

    async function tick() {
      try {
        const s = await getAiStatus(ctrl.signal);
        if (cancelled) return;
        // Only push a new text when the backend actually changed it,
        // so React doesn't re-render on every poll while the bubble
        // sits at the same content.
        const nextText = s.text || lastTextRef.current;
        if (s.text) lastTextRef.current = s.text;
        setView({ state: s.state, text: nextText, connected: true });
      } catch {
        if (cancelled) return;
        setView((v) => ({ ...v, connected: false }));
      }
    }

    tick();
    const id = window.setInterval(tick, POLL_MS);
    return () => {
      cancelled = true;
      ctrl.abort();
      window.clearInterval(id);
    };
  }, []);

  return view;
}

// Mouth amplitude polled at 30Hz so the avatar's lipsync feels live.
// We don't store it in React state — re-rendering at 30Hz would be wasteful.
// Instead the hook hands back a ref that the render loop reads each frame.
const MOUTH_POLL_MS = 33;

export function useMouthRef(): React.MutableRefObject<number> {
  const ref = useRef(0);

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();

    async function tick() {
      try {
        const m = await getMouth(ctrl.signal);
        if (cancelled) return;
        ref.current = m.level;
      } catch {
        if (cancelled) return;
        ref.current = 0;
      }
    }

    tick();
    const id = window.setInterval(tick, MOUTH_POLL_MS);
    return () => {
      cancelled = true;
      ctrl.abort();
      window.clearInterval(id);
    };
  }, []);

  return ref;
}

// Visemes — same 30Hz poll cadence as mouth amplitude.
const VISEME_POLL_MS = 33;
const ZERO_VISEMES: VisemeWeights = { aa: 0, ih: 0, ee: 0, oh: 0, ou: 0 };

export function useVisemeRef(): React.MutableRefObject<VisemeWeights> {
  const ref = useRef<VisemeWeights>({ ...ZERO_VISEMES });
  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    async function tick() {
      try {
        const v = await getVisemes(ctrl.signal);
        if (cancelled) return;
        ref.current = v;
      } catch {
        if (cancelled) return;
        ref.current = { ...ZERO_VISEMES };
      }
    }
    tick();
    const id = window.setInterval(tick, VISEME_POLL_MS);
    return () => {
      cancelled = true;
      ctrl.abort();
      window.clearInterval(id);
    };
  }, []);
  return ref;
}

// Face position — used by the avatar's gaze code. Polled fast (~10Hz)
// because human eye contact doesn't need 30Hz.
const PERCEPTION_POLL_MS = 100;

export function useFaceRef(): React.MutableRefObject<FaceState> {
  const ref = useRef<FaceState>({ present: false, x: 0, y: 0, ts: 0 });
  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    async function tick() {
      try {
        const p = await getPerception(ctrl.signal);
        if (cancelled) return;
        ref.current = p.face;
      } catch {
        if (cancelled) return;
        ref.current = { present: false, x: 0, y: 0, ts: 0 };
      }
    }
    tick();
    const id = window.setInterval(tick, PERCEPTION_POLL_MS);
    return () => {
      cancelled = true;
      ctrl.abort();
      window.clearInterval(id);
    };
  }, []);
  return ref;
}

// Body actions — fire once per ts change.
const BODY_POLL_MS = 250;

export function useBodyAction(): BodyAction {
  const [action, setAction] = useState<BodyAction>({ action: "", ts: 0 });
  const lastTs = useRef<number>(0);
  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    async function tick() {
      try {
        const b = await getBodyAction(ctrl.signal);
        if (cancelled) return;
        if (b.ts > lastTs.current) {
          lastTs.current = b.ts;
          setAction(b);
        }
      } catch {
        // ignore
      }
    }
    tick();
    const id = window.setInterval(tick, BODY_POLL_MS);
    return () => {
      cancelled = true;
      ctrl.abort();
      window.clearInterval(id);
    };
  }, []);
  return action;
}

// Telemetry — 1 Hz is plenty for the HUD.
const TELEMETRY_POLL_MS = 1000;
const DEFAULT_TELEMETRY: Telemetry = {
  cpu: 0,
  mem: 0,
  mic_level: 0,
  mood: "neutral",
  vision_active: false,
  gestures_active: false,
  hud_enabled: true,
  last_gesture: { name: "none", ts: 0 },
  online: false,
  user_name: "",
  language: "english",
};

export function useTelemetry(): Telemetry {
  const [t, setT] = useState<Telemetry>(DEFAULT_TELEMETRY);
  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    async function tick() {
      try {
        const tel = await getTelemetry(ctrl.signal);
        if (cancelled) return;
        setT(tel);
      } catch {
        // keep last value on transient errors
      }
    }
    tick();
    const id = window.setInterval(tick, TELEMETRY_POLL_MS);
    return () => {
      cancelled = true;
      ctrl.abort();
      window.clearInterval(id);
    };
  }, []);
  return t;
}
