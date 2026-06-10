import { useTelemetry } from "../hooks/useAiStatus";

function Bar({ value, label, danger = 75 }: { value: number; label: string; danger?: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const color =
    pct > danger ? "bg-red-500" : pct > danger * 0.7 ? "bg-amber-400" : "bg-emerald-400";
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 text-[10px] uppercase tracking-wider opacity-70">
        {label}
      </span>
      <div className="flex-1 h-1.5 bg-white/10 rounded">
        <div className={`h-full ${color} rounded`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right tabular-nums text-[10px] opacity-80">
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

function Dot({ on, label }: { on: boolean; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span
        className={`inline-block w-2 h-2 rounded-full ${
          on ? "bg-emerald-400 shadow-[0_0_6px_theme(colors.emerald.400)]" : "bg-white/15"
        }`}
      />
      <span className="text-[10px] opacity-80">{label}</span>
    </div>
  );
}

export default function Hud() {
  const t = useTelemetry();
  if (!t.hud_enabled) return null;

  const gestureAge = t.last_gesture.ts > 0 ? Math.max(0, Date.now() / 1000 - t.last_gesture.ts) : Infinity;
  const gestureFresh = gestureAge < 4;

  return (
    <div
      className="absolute bottom-3 left-3 w-[230px] rounded-lg bg-black/55 backdrop-blur-md border border-white/10 px-3 py-2 text-white font-mono pointer-events-none"
      data-tauri-drag-region={false}
    >
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[11px] tracking-widest text-emerald-300">ZENDAYA</span>
        <span className="text-[10px] opacity-70">
          {t.online ? "online" : "offline"} · {t.mood}
        </span>
      </div>
      <div className="space-y-1">
        <Bar value={t.cpu} label="CPU" />
        <Bar value={t.mem} label="MEM" />
        <Bar value={t.mic_level * 100} label="VOX" danger={90} />
      </div>
      <div className="mt-2 flex items-center justify-between">
        <Dot on={t.vision_active} label="vision" />
        <Dot on={t.gestures_active} label="gestures" />
        <Dot on={gestureFresh} label={gestureFresh ? t.last_gesture.name : "—"} />
      </div>
      {t.user_name && (
        <div className="mt-1.5 text-[10px] opacity-60">
          user: {t.user_name} · lang: {t.language}
        </div>
      )}
    </div>
  );
}
