import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";

function fmt(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, "0")}`;
}

async function postCmd(text: string) {
  try {
    await fetch("http://127.0.0.1:7475/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch {
    /* ignore */
  }
}

export default function MusicPlayer() {
  const np = useZendaya((s) => s.nowPlaying);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!np || !np.is_playing) return;
    const id = window.setInterval(() => setTick((t) => t + 1), 500);
    return () => window.clearInterval(id);
  }, [np?.is_playing]);

  // Approximate progress between server pushes by adding elapsed wall time.
  const progress = np
    ? Math.min(np.duration_ms, np.progress_ms + (np.is_playing ? tick * 500 : 0))
    : 0;
  const pct = np && np.duration_ms > 0 ? (progress / np.duration_ms) * 100 : 0;

  return (
    <AnimatePresence>
      {np && (
        <motion.div
          key="music-player"
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
          className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 zen-player-card pointer-events-auto"
          style={{ width: "min(440px, 86vw)", padding: "24px 26px 22px" }}
        >
          <div className="flex items-center gap-4">
            <div
              className="rounded-xl overflow-hidden flex-shrink-0"
              style={{
                width: 84,
                height: 84,
                background:
                  np.artUrl
                    ? `url(${np.artUrl}) center/cover`
                    : "linear-gradient(135deg, #ec4899, #a855f7)",
                boxShadow: "0 12px 28px rgba(0,0,0,0.45), 0 0 22px rgba(168,85,247,0.35)",
              }}
            />
            <div className="flex-1 min-w-0">
              <div
                className="text-[10px] tracking-[0.32em] uppercase mb-1"
                style={{ color: "rgba(255,255,255,0.5)" }}
              >
                {np.source === "local" ? "Local · Now Playing" : "Spotify · Now Playing"}
              </div>
              <div
                className="font-semibold text-base truncate"
                style={{ color: "#fff", letterSpacing: "0.02em" }}
              >
                {np.track}
              </div>
              <div
                className="text-sm truncate"
                style={{ color: "rgba(255,255,255,0.65)" }}
              >
                {np.artist}
              </div>
            </div>
          </div>

          <div className="mt-5 zen-player-progress">
            <div className="zen-player-progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <div
            className="flex justify-between mt-1.5 text-[10px] font-mono"
            style={{ color: "rgba(255,255,255,0.45)" }}
          >
            <span>{fmt(progress)}</span>
            <span>{fmt(np.duration_ms)}</span>
          </div>

          <div className="flex items-center justify-center gap-3 mt-4">
            <button
              className="zen-player-btn"
              onClick={() => postCmd("previous track")}
              aria-label="Previous"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M6 6h2v12H6zm3.5 6l8.5-6v12z" />
              </svg>
            </button>
            <button
              className="zen-player-btn primary"
              onClick={() => postCmd(np.is_playing ? "pause music" : "resume music")}
              aria-label={np.is_playing ? "Pause" : "Play"}
            >
              {np.is_playing ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 5h4v14H6zm8 0h4v14h-4z" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>
            <button
              className="zen-player-btn"
              onClick={() => postCmd("next track")}
              aria-label="Next"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16 6h2v12h-2zM6 6l8.5 6L6 18z" />
              </svg>
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
