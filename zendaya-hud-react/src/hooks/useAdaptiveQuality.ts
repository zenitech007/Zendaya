import { useEffect, useRef } from "react";
import { useZendaya } from "../store/zendayaStore";

// Samples FPS via rAF. If the rolling 2s average drops below LOW_THRESHOLD,
// drops store.quality to "low" (which the Canvas + post-processing read to
// reduce dpr / bloom). Pops back to "high" once we sustain HIGH_THRESHOLD.
// Single source of truth so multiple components don't each measure FPS.

const LOW_THRESHOLD = 45;
const HIGH_THRESHOLD = 55;
const SAMPLE_WINDOW_MS = 2000;

export function useAdaptiveQuality() {
  const setQuality = useZendaya((s) => s.setQuality);
  const setFps = useZendaya((s) => s.setFps);
  const samples = useRef<number[]>([]);

  useEffect(() => {
    let raf = 0;
    let last = performance.now();
    let lastReport = last;

    function tick(now: number) {
      const dt = now - last;
      last = now;
      if (dt > 0) {
        const fps = 1000 / dt;
        samples.current.push(fps);
        // Keep ~last 2s of samples (assume ~60 entries/sec).
        if (samples.current.length > 240) samples.current.shift();
      }

      if (now - lastReport >= SAMPLE_WINDOW_MS) {
        lastReport = now;
        const arr = samples.current;
        if (arr.length > 0) {
          const avg = arr.reduce((a, b) => a + b, 0) / arr.length;
          setFps(Math.round(avg));
          const z = useZendaya.getState();
          if (z.quality === "high" && avg < LOW_THRESHOLD) {
            setQuality("low");
          } else if (z.quality === "low" && avg > HIGH_THRESHOLD) {
            setQuality("high");
          }
        }
      }

      raf = requestAnimationFrame(tick);
    }

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [setQuality, setFps]);
}
