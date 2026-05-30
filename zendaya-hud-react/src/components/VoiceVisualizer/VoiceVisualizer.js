import { jsx as _jsx } from "react/jsx-runtime";
import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useRef } from "react";
import { useZendaya } from "../../store/zendayaStore";
import { useVoiceState } from "../../hooks/useVoiceState";
// 2D bar visualizer overlay. Driven by audioLevel from the store.
// Animated in/out by Framer Motion when voiceActive flips.
export default function VoiceVisualizer() {
    const { isActive: visible } = useVoiceState();
    return (_jsx(AnimatePresence, { children: visible && (_jsx(motion.div, { initial: { opacity: 0, y: 24 }, animate: { opacity: 1, y: 0 }, exit: { opacity: 0, y: 24 }, transition: { duration: 0.45, ease: "easeOut" }, className: "pointer-events-none fixed bottom-10 left-1/2 -translate-x-1/2 flex items-end gap-1 h-16", children: Array.from({ length: 28 }).map((_, i) => (_jsx(Bar, { index: i }, i))) }, "voice-viz")) }));
}
function Bar({ index }) {
    const ref = useRef(null);
    useEffect(() => {
        let raf = 0;
        function tick() {
            const z = useZendaya.getState();
            const el = ref.current;
            if (!el) {
                raf = requestAnimationFrame(tick);
                return;
            }
            const t = performance.now() * 0.004;
            const wave = (Math.sin(t + index * 0.45) * 0.5 + 0.5);
            const lvl = z.audioLevel;
            // Floor for ambient bob even at zero level.
            const h = 6 + (wave * 0.4 + lvl * 0.9) * 56;
            el.style.height = `${h}px`;
            raf = requestAnimationFrame(tick);
        }
        raf = requestAnimationFrame(tick);
        return () => cancelAnimationFrame(raf);
    }, [index]);
    return (_jsx("div", { ref: ref, className: "w-[3px] rounded-sm", style: {
            background: "linear-gradient(to top, #7a5cff, #5cf2ff)",
            boxShadow: "0 0 8px rgba(122,92,255,0.65)",
        } }));
}
