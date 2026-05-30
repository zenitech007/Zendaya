import { useZendaya } from "../../store/zendayaStore";

export default function PerceptionIndicator() {
  const p = useZendaya((s) => s.perception);
  if (!p) return null;

  const stale = Date.now() / 1000 - p.last_gesture.ts > 3.0;
  const gestureLabel = p.last_gesture.name && p.last_gesture.name !== "none" && !stale
    ? p.last_gesture.name.replace(/_/g, " ")
    : null;

  return (
    <div className="absolute top-4 left-4 flex items-center gap-2 text-xs
                    text-orange-300/80 font-mono select-none pointer-events-none">
      <span
        className={`w-2 h-2 rounded-full ${
          p.face.present
            ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]"
            : "bg-zinc-500/40"
        }`}
      />
      <span className="opacity-70">{p.face.present ? "sees you" : "looking"}</span>
      {gestureLabel && (
        <span className="ml-2 px-1.5 py-0.5 rounded bg-orange-400/10
                         border border-orange-400/30 animate-pulse">
          {gestureLabel}
        </span>
      )}
    </div>
  );
}
