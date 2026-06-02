import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import MusicPlayer from "./MusicPlayer";
import TelemetryWidget from "./TelemetryWidget";
import PerceptionIndicator from "./PerceptionIndicator";

export default function Hud() {
  const mood = useZendaya((s) => s.telemetry?.mood);
  const setBgDim = useZendaya((s) => s.setBgDim);
  useEffect(() => {
    if (!mood || typeof setBgDim !== "function") return;
    const moodToBgDim: Record<string, number> = {
      neutral: 0.7,
      focused: 0.6,
      tired: 0.85,
      alert: 0.5,
    };
    setBgDim(moodToBgDim[mood] ?? 0.7);
  }, [mood, setBgDim]);

  return (
    <div className="pointer-events-none fixed inset-0 z-20">
      <Wordmark />
      <Caption />
      <MusicPlayer />
      <TelemetryWidget />
      <PerceptionIndicator />
    </div>
  );
}

function Wordmark() {
  const docked = useZendaya((s) => s.docked);
  return (
    <AnimatePresence>
      {!docked && (
        <div
          key="wordmark"
          className="absolute inset-0 flex items-center justify-center"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, letterSpacing: "0.06em" }}
            animate={{ opacity: 1, scale: 1, letterSpacing: "0.18em" }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
            className="zen-wordmark"
          >
            Z.E.N.D.A.Y.A
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

function Caption() {
  const text = useZendaya((s) => s.text);
  const ai = useZendaya((s) => s.ai);
  const docked = useZendaya((s) => s.docked);
  const visible = !!text && !docked && (ai === "speaking" || ai === "thinking");

  return (
    <div className="absolute left-1/2 -translate-x-1/2 bottom-16 w-full flex justify-center">
      <AnimatePresence mode="wait">
        {visible && (
          <motion.div
            key={text}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="zen-caption max-w-2xl px-6"
          >
            {text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
