import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import { fetchTrackList, streamUrl, postNowPlaying } from "../../api/music";
import { nextTrack, prevTrack, type QueueTrack } from "../../music/queue";

function fmt(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  const m = Math.floor(s / 60);
  const rem = s % 60;
  return `${m}:${rem.toString().padStart(2, "0")}`;
}

function safePlay(a: HTMLAudioElement) {
  try {
    const p = a.play();
    if (p && typeof (p as Promise<void>).catch === "function") {
      (p as Promise<void>).catch(() => {/* autoplay blocked until a user gesture */});
    }
  } catch {
    /* happy-dom / autoplay */
  }
}

export default function MusicPlayer() {
  const np = useZendaya((s) => s.nowPlaying);
  const musicCmd = useZendaya((s) => s.musicCmd);

  const audioRef = useRef<HTMLAudioElement>(null);
  const currentIdRef = useRef<string | null>(null);
  const queueRef = useRef<QueueTrack[]>([]);

  const [playing, setPlaying] = useState(false);
  const [curMs, setCurMs] = useState(0);
  const [durMs, setDurMs] = useState(0);

  // Build the queue once (best-effort; empty if the backend is offline).
  useEffect(() => {
    let alive = true;
    fetchTrackList().then((list) => { if (alive) queueRef.current = list; });
    return () => { alive = false; };
  }, []);

  // Load a track into <audio>, optionally play it, and mirror the state back.
  function loadAndPlay(id: string, url: string, play: boolean, seekMs = 0) {
    const a = audioRef.current;
    if (!a) return;
    currentIdRef.current = id;
    a.src = streamUrl(url || id);
    try { a.load(); } catch { /* happy-dom */ }
    if (seekMs > 0) { try { a.currentTime = seekMs / 1000; } catch { /* ignore */ } }
    if (play) safePlay(a);
    postNowPlaying({ track_id: id, is_playing: play, position_ms: seekMs });
  }

  function advance(dir: 1 | -1) {
    const list = queueRef.current;
    const pick = dir === 1
      ? nextTrack(list, currentIdRef.current)
      : prevTrack(list, currentIdRef.current);
    if (!pick) return;
    loadAndPlay(pick.id, pick.stream_url, true);
  }

  // React to a NEW backend-selected track (e.g. "play some jazz"). Reload is
  // triggered ONLY by a trackId change — safe because zendaya.py's poll loop is
  // edge-triggered on (track, is_playing), so an echo of our own local
  // navigation carries the trackId we already hold and is ignored here.
  useEffect(() => {
    if (!np || !np.trackId) return;
    if (np.trackId === currentIdRef.current) return;
    loadAndPlay(np.trackId, np.streamUrl ?? np.trackId, np.is_playing);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [np?.trackId]);

  // Apply a voice/chat transport command (re-fires on every seq bump).
  useEffect(() => {
    if (!musicCmd) return;
    const a = audioRef.current;
    if (!a) return;
    switch (musicCmd.cmd) {
      case "play": safePlay(a); break;
      case "pause": try { a.pause(); } catch { /* ignore */ } break;
      case "next": advance(1); break;
      case "prev": advance(-1); break;
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [musicCmd?.seq]);

  function togglePlay() {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) safePlay(a); else a.pause();
  }

  function seek(e: React.MouseEvent<HTMLDivElement>) {
    const a = audioRef.current;
    if (!a || !a.duration || !isFinite(a.duration)) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const t = pct * a.duration;
    try { a.currentTime = t; } catch { /* ignore */ }
    setCurMs(t * 1000);
    postNowPlaying({ track_id: currentIdRef.current, is_playing: !a.paused, position_ms: Math.floor(t * 1000) });
  }

  const pct = durMs > 0 ? Math.min(100, (curMs / durMs) * 100) : 0;

  return (
    <>
      <audio
        ref={audioRef}
        data-testid="hud-audio"
        onTimeUpdate={(e) => setCurMs(e.currentTarget.currentTime * 1000)}
        onLoadedMetadata={(e) => { const d = e.currentTarget.duration; setDurMs(isFinite(d) ? d * 1000 : 0); }}
        onDurationChange={(e) => { const d = e.currentTarget.duration; setDurMs(isFinite(d) ? d * 1000 : 0); }}
        onPlay={() => {
          setPlaying(true);
          const a = audioRef.current;
          postNowPlaying({ track_id: currentIdRef.current, is_playing: true, position_ms: Math.floor((a?.currentTime ?? 0) * 1000) });
        }}
        onPause={() => {
          setPlaying(false);
          const a = audioRef.current;
          postNowPlaying({ track_id: currentIdRef.current, is_playing: false, position_ms: Math.floor((a?.currentTime ?? 0) * 1000) });
        }}
        onEnded={() => advance(1)}
        onError={() => advance(1)}
      />
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
                  background: np.artUrl
                    ? `url(${np.artUrl}) center/cover`
                    : "linear-gradient(135deg, var(--zen-accent), var(--zen-primary))",
                  boxShadow: "0 12px 28px rgba(0,0,0,0.45), 0 0 22px color-mix(in srgb, var(--zen-primary) 35%, transparent)",
                }}
              />
              <div className="flex-1 min-w-0">
                <div className="text-[10px] tracking-[0.32em] uppercase mb-1" style={{ color: "rgba(255,255,255,0.5)" }}>
                  {np.source === "local" ? "Local · Now Playing" : "Spotify · Now Playing"}
                </div>
                <div className="font-semibold text-base truncate" style={{ color: "#fff", letterSpacing: "0.02em" }}>
                  {np.track}
                </div>
                <div className="text-sm truncate" style={{ color: "rgba(255,255,255,0.65)" }}>
                  {np.artist}
                </div>
              </div>
            </div>

            <div className="mt-5 zen-player-progress" onClick={seek} style={{ cursor: "pointer" }}>
              <div className="zen-player-progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <div className="flex justify-between mt-1.5 text-[10px] font-mono" style={{ color: "rgba(255,255,255,0.45)" }}>
              <span>{fmt(curMs)}</span>
              <span>{fmt(durMs)}</span>
            </div>

            <div className="flex items-center justify-center gap-3 mt-4">
              <button className="zen-player-btn" onClick={() => advance(-1)} aria-label="Previous">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5-6v12z" /></svg>
              </button>
              <button className="zen-player-btn primary" onClick={togglePlay} aria-label={playing ? "Pause" : "Play"}>
                {playing ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M6 5h4v14H6zm8 0h4v14h-4z" /></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z" /></svg>
                )}
              </button>
              <button className="zen-player-btn" onClick={() => advance(1)} aria-label="Next">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M16 6h2v12h-2zM6 6l8.5 6L6 18z" /></svg>
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
