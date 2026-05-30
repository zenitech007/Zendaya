import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
// Shared chrome for every 2D module: title bar, close hint, glass card,
// motion enter/exit. Positioned opposite to the orb's dock corner.
export default function ModulePanel({ title, children }) {
    const dockCorner = useZendaya((s) => s.dockCorner);
    const setActiveModule = useZendaya((s) => s.setActiveModule);
    // Orb docks bottom-right by default → panel sits top-left, and vice versa.
    const positionStyle = dockCorner === "br"
        ? { top: "8%", left: "8%" }
        : { top: "8%", right: "8%" };
    return (_jsxs(motion.div, { initial: { opacity: 0, y: 20, scale: 0.96, filter: "blur(8px)" }, animate: { opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }, exit: { opacity: 0, y: 20, scale: 0.96, filter: "blur(8px)" }, transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] }, className: "pointer-events-auto absolute z-30 w-[440px] max-w-[44vw] rounded-2xl border", style: {
            ...positionStyle,
            borderColor: "rgba(255,138,60,0.35)",
            background: "linear-gradient(180deg, rgba(20,12,6,0.72) 0%, rgba(8,5,3,0.85) 100%)",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
            boxShadow: "0 18px 60px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,138,60,0.08) inset, 0 0 60px rgba(255,138,60,0.12)",
            color: "#ffd9b8",
            fontFamily: '"Share Tech Mono", monospace',
        }, children: [_jsxs("div", { className: "flex items-center justify-between px-4 py-2 border-b", style: { borderColor: "rgba(255,138,60,0.25)" }, children: [_jsx("div", { className: "tracking-[0.35em] text-xs", style: { color: "#ff8a3c" }, children: title.toUpperCase() }), _jsx("button", { onClick: () => setActiveModule("none"), className: "text-xs hover:text-white transition-colors", style: { color: "rgba(255,138,60,0.7)" }, "aria-label": "Close module", children: "\u2715" })] }), _jsx("div", { className: "p-4", children: children })] }));
}
