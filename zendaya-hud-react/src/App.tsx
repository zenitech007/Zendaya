import { Canvas } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { motion, AnimatePresence } from "framer-motion";
import SceneManager from "./scenes/SceneManager";
import Hud from "./components/HUD/Hud";
import ModuleHost from "./components/Modules/ModuleHost";
import ThemeRoot from "./themes/ThemeRoot";
import ChromeFrame from "./components/chrome/ChromeFrame";
import Atmosphere from "./components/Atmosphere/Atmosphere";
import { THEMES } from "./themes/registry";
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
  const activeThemeId = useZendaya((s) => s.activeThemeId);
  const bloom = 0.45 * (THEMES[activeThemeId]?.bloom ?? 1);
  const dpr: [number, number] = quality === "high" ? [1, 2] : [1, 1];

  return (
    <ThemeRoot>
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
            <SceneManager />
            <EffectComposer enableNormalPass={false}>
              <Bloom
                intensity={bloom}
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
              <ChromeFrame />
              <ModuleHost />
            </motion.div>
          )}
        </AnimatePresence>

        <Atmosphere />
      </div>
    </ThemeRoot>
  );
}
