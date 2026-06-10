import { useEffect, useState } from "react";
import { getFaceMode, type FaceMode } from "../lib/api";

const POLL_MS = 2000;

// Poll /face_mode and toggle the Tauri window's visibility when the active
// mode is "minimize" (background) — or when it's any other mode that isn't
// "pet"/"anime" (the pet is the 3D VRM face; hud/minimize hand the screen
// over to the HUD wrapper or to nothing). Falls back to a no-op outside Tauri.
export function useFaceMode(): FaceMode {
  const [mode, setMode] = useState<FaceMode>("pet");

  useEffect(() => {
    let cancelled = false;
    const ctrl = new AbortController();
    let lastApplied: FaceMode | null = null;

    async function apply(next: FaceMode) {
      if (next === lastApplied) return;
      lastApplied = next;
      try {
        const mod = await import("@tauri-apps/api/window");
        const win = mod.getCurrentWindow();
        if (next === "pet" || next === "anime") {
          await win.show();
          await win.setAlwaysOnTop(true);
        } else {
          await win.hide();
        }
      } catch {
        // Not running under Tauri (or API unavailable) — ignore.
      }
    }

    async function tick() {
      try {
        const r = await getFaceMode(ctrl.signal);
        if (cancelled) return;
        setMode(r.mode);
        void apply(r.mode);
      } catch {
        // backend offline — leave the last known mode in place
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

  return mode;
}
