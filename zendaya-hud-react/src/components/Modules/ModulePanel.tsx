import { motion } from "framer-motion";
import type { ReactNode } from "react";
import { useZendaya } from "../../store/zendayaStore";

interface Props {
  title: string;
  children: ReactNode;
}

// Shared chrome for every 2D module: title bar, close hint, glass card,
// motion enter/exit. Positioned opposite to the orb's dock corner.
export default function ModulePanel({ title, children }: Props) {
  const dockCorner = useZendaya((s) => s.dockCorner);
  const setActiveModule = useZendaya((s) => s.setActiveModule);

  // Orb docks bottom-right by default → panel sits top-left, and vice versa.
  const positionStyle: React.CSSProperties =
    dockCorner === "br"
      ? { top: "8%", left: "8%" }
      : { top: "8%", right: "8%" };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.96, filter: "blur(8px)" }}
      animate={{ opacity: 1, y: 0, scale: 1, filter: "blur(0px)" }}
      exit={{ opacity: 0, y: 20, scale: 0.96, filter: "blur(8px)" }}
      transition={{ duration: 0.55, ease: [0.16, 1, 0.3, 1] }}
      className="pointer-events-auto absolute z-30 w-[440px] max-w-[44vw] rounded-2xl border"
      style={{
        ...positionStyle,
        borderColor: "color-mix(in srgb, var(--zen-primary) 35%, transparent)",
        background:
          "linear-gradient(180deg, color-mix(in srgb, var(--zen-bg-0) 72%, transparent) 0%, color-mix(in srgb, var(--zen-bg-1) 85%, transparent) 100%)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        boxShadow:
          "0 18px 60px rgba(0,0,0,0.55), 0 0 0 1px color-mix(in srgb, var(--zen-primary) 8%, transparent) inset, 0 0 60px color-mix(in srgb, var(--zen-primary) 12%, transparent)",
        color: "var(--zen-text-glow)",
        fontFamily: '"Share Tech Mono", monospace',
      }}
    >
      <div
        className="flex items-center justify-between px-4 py-2 border-b"
        style={{ borderColor: "color-mix(in srgb, var(--zen-primary) 25%, transparent)" }}
      >
        <div
          className="tracking-[0.35em] text-xs"
          style={{ color: "var(--zen-primary)" }}
        >
          {title.toUpperCase()}
        </div>
        <button
          onClick={() => setActiveModule("none")}
          className="text-xs hover:text-white transition-colors"
          style={{ color: "color-mix(in srgb, var(--zen-primary) 70%, transparent)" }}
          aria-label="Close module"
        >
          ✕
        </button>
      </div>
      <div className="p-4">{children}</div>
    </motion.div>
  );
}
