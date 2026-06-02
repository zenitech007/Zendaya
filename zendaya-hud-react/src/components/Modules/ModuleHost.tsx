import { AnimatePresence } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import Calculator from "./Calculator";
import Notes from "./Notes";

export default function ModuleHost() {
  const activeModule = useZendaya((s) => s.activeModule);
  return (
    <AnimatePresence mode="wait">
      {activeModule === "calculator" && <Calculator key="calculator" />}
      {activeModule === "notes" && <Notes key="notes" />}
    </AnimatePresence>
  );
}
