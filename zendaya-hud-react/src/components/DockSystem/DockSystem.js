import { jsx as _jsx } from "react/jsx-runtime";
import { motion } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import { useInteractionSound } from "../../hooks/useSpatialAudio";
// Bottom-edge dock — buttons mirror the available WS actions for a
// keyboard-free demo. In production these are driven by Python via WS.
const ITEMS = [
    { id: "voice", label: "Voice" },
    { id: "map", label: "Map" },
    { id: "terminal", label: "Term" },
    { id: "minimize", label: "Mini" },
];
export default function DockSystem() {
    const minimized = useZendaya((s) => s.minimized);
    return (_jsx(motion.div, { initial: { y: 80, opacity: 0 }, animate: { y: minimized ? 80 : 0, opacity: minimized ? 0 : 1 }, transition: { duration: 0.55, ease: [0.16, 1, 0.3, 1] }, className: "fixed bottom-4 left-1/2 -translate-x-1/2 z-30 flex gap-2 px-3 py-2 rounded-2xl backdrop-blur-md bg-white/5 border border-white/10", children: ITEMS.map((it) => (_jsx(DockButton, { id: it.id, label: it.label }, it.id))) }));
}
function DockButton({ id, label }) {
    const { play } = useInteractionSound();
    function onClick() {
        play("click");
        const z = useZendaya.getState();
        switch (id) {
            case "voice":
                z.setVoiceActive(!z.voiceActive);
                play(z.voiceActive ? "close" : "open");
                break;
            case "map":
                if (z.scene === "map") {
                    z.setScene("main");
                    z.setDocked(false);
                    z.setPanel("none");
                }
                else {
                    z.setScene("map");
                    z.setDocked(true);
                    z.setPanel("globe");
                }
                break;
            case "terminal":
                z.setTerminalOpen(!z.terminalOpen);
                play(z.terminalOpen ? "close" : "open");
                break;
            case "minimize":
                z.setMinimized(true);
                // Auto-restore after a beat so the demo doesn't strand the UI.
                window.setTimeout(() => useZendaya.getState().setMinimized(false), 4000);
                break;
        }
    }
    return (_jsx("button", { onClick: onClick, onMouseEnter: () => play("hover"), className: "font-display text-xs tracking-widest uppercase px-3 py-1.5 rounded-xl text-zen-cyan/90 hover:text-white hover:bg-white/10 transition-colors", children: label }));
}
