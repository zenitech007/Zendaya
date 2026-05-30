import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
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
    return (_jsxs(AnimatePresence, { mode: "wait", children: [activeModule === "calculator" && _jsx(Calculator, {}, "calculator"), activeModule === "clock" && _jsx(Clock, {}, "clock"), activeModule === "notes" && _jsx(Notes, {}, "notes"), activeModule === "weather" && _jsx(Weather, {}, "weather")] }));
}
