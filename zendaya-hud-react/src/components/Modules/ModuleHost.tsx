import { AnimatePresence } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import Calculator from "./Calculator";
import Clock from "./Clock";
import Notes from "./Notes";
import Weather from "./Weather";

// Mounts the currently active 2D module above the Canvas. The 3D map is
// rendered inside MainScene (it lives in the same WebGL context as the orb),
// so it is NOT handled here — only flat HTML modules.
export default function ModuleHost() {
  const activeModule = useZendaya((s) => s.activeModule);

  return (
    <AnimatePresence mode="wait">
      {activeModule === "calculator" && <Calculator key="calculator" />}
      {activeModule === "clock" && <Clock key="clock" />}
      {activeModule === "notes" && <Notes key="notes" />}
      {activeModule === "weather" && <Weather key="weather" />}
    </AnimatePresence>
  );
}
