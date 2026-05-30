import { AnimatePresence, motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import MusicPlayer from "./MusicPlayer";

export default function Hud() {
  return (
    <div className="pointer-events-none fixed inset-0 z-20">
      <Wordmark />
      <Caption />
      <MusicPlayer />
    </div>
  );
}

function Wordmark() {
  const docked = useZendaya((s) => s.docked);
  return (
    <AnimatePresence>
      {!docked && (
        <motion.div
          key="wordmark"
          initial={{ opacity: 0, y: 18, letterSpacing: "0.25em" }}
          animate={{ opacity: 1, y: 0, letterSpacing: "0.42em" }}
          exit={{ opacity: 0, y: 12 }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
          className="absolute left-1/2 -translate-x-1/2 zen-wordmark"
          style={{ top: "calc(50% + 180px)" }}
        >
          ZENDAYA
        </motion.div>
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
