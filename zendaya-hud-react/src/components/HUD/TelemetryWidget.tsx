import { useZendaya } from "../../store/zendayaStore";

function Row({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 opacity-60">{label}</span>
      <div className="w-20 h-1 bg-orange-300/10 rounded overflow-hidden">
        <div className="h-full bg-orange-400/60" style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="w-10 text-right">{value.toFixed(0)}{unit}</span>
    </div>
  );
}

export default function TelemetryWidget() {
  const t = useZendaya((s) => s.telemetry);
  if (!t) return null;

  return (
    <div className="absolute top-4 right-4 flex flex-col gap-1 text-xs
                    text-orange-300/80 font-mono select-none pointer-events-none">
      <Row label="CPU" value={t.cpu} unit="%" />
      <Row label="MEM" value={t.mem} unit="%" />
      <div className="opacity-60">mood: {t.mood}</div>
      {!t.online && <div className="text-red-400/80">offline</div>}
    </div>
  );
}
