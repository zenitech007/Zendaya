import { useEffect, useRef, useState } from "react";
import { getAiStatus, type AiState } from "../lib/api";

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
