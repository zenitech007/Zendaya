import { Canvas } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { motion, AnimatePresence } from "framer-motion";
import MainScene from "./scenes/MainScene";
import Hud from "./components/HUD/Hud";
import ModuleHost from "./components/Modules/ModuleHost";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAdaptiveQuality } from "./hooks/useAdaptiveQuality";
import { useAudioEngine } from "./hooks/useAudioEngine";
import { useZendaya } from "./store/zendayaStore";

export default function App() {
  useWebSocket();
  useAdaptiveQuality();
  useAudioEngine();
  const minimized = useZendaya((s) => s.minimized);
  const quality = useZendaya((s) => s.quality);
  const dpr: [number, number] = quality === "high" ? [1, 2] : [1, 1];

  return (
    <div className="relative w-full h-full bg-black">
      <motion.div
        className="absolute inset-0"
        animate={{
          scale: minimized ? 0.25 : 1,
          x: minimized ? "38%" : "0%",
          y: minimized ? "38%" : "0%",
          opacity: minimized ? 0.85 : 1,
        }}
        transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
      >
        <Canvas
          camera={{ position: [0, 0, 6], fov: 38, near: 0.05, far: 100 }}
          gl={{ alpha: true, antialias: quality === "high", powerPreference: "high-performance" }}
          dpr={dpr}
        >
          <MainScene />
          <EffectComposer enableNormalPass={false}>
            <Bloom
              intensity={0.55}
              luminanceThreshold={0.35}
              luminanceSmoothing={0.6}
              mipmapBlur
            />
          </EffectComposer>
        </Canvas>
      </motion.div>

      <AnimatePresence>
        {!minimized && (
          <motion.div
            key="hud-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            className="absolute inset-0"
          >
            <Hud />
            <ModuleHost />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
