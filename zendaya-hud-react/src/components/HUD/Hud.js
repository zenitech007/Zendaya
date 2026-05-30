import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { motion, AnimatePresence } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
export default function Hud() {
    return (_jsxs("div", { className: "pointer-events-none fixed inset-0 z-20", children: [_jsx(Wordmark, {}), _jsx(SpeechCaption, {})] }));
}
function Wordmark() {
    return (_jsx("div", { className: "absolute left-1/2 -translate-x-1/2 font-display tracking-[0.55em] text-base", style: {
            top: "calc(50% + 110px)",
            color: "#ff8a3c",
            textShadow: "0 0 18px rgba(255,138,60,0.55)",
        }, children: "ZENDAYA" }));
}
function SpeechCaption() {
    const { text, ai } = useZendaya((s) => ({ text: s.text, ai: s.ai }));
    const visible = ai === "speaking" && text;
    return (_jsx(AnimatePresence, { children: visible && (_jsx(motion.div, { initial: { opacity: 0, y: 8 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: 8 }, transition: { duration: 0.35 }, className: "absolute bottom-16 left-1/2 -translate-x-1/2 max-w-2xl text-center font-mono text-sm", style: { color: "rgba(255,200,160,0.85)" }, children: text }, "caption")) }));
}
