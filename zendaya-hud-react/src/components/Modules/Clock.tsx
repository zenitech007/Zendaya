import { useEffect, useState } from "react";
import ModulePanel from "./ModulePanel";

export default function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const dateStr = now.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // Analog face geometry
  const cx = 100;
  const cy = 100;
  const r = 84;
  const hourAngle =
    ((now.getHours() % 12) + now.getMinutes() / 60) * (Math.PI / 6) - Math.PI / 2;
  const minAngle = (now.getMinutes() + now.getSeconds() / 60) * (Math.PI / 30) - Math.PI / 2;
  const secAngle = now.getSeconds() * (Math.PI / 30) - Math.PI / 2;
  const hand = (a: number, len: number, w: number, color: string) => (
    <line
      x1={cx}
      y1={cy}
      x2={cx + Math.cos(a) * len}
      y2={cy + Math.sin(a) * len}
      stroke={color}
      strokeWidth={w}
      strokeLinecap="round"
    />
  );

  return (
    <ModulePanel title="Clock">
      <div className="flex items-center justify-center mb-3">
        <svg width="180" height="180" viewBox="0 0 200 200">
          <circle
            cx={cx}
            cy={cy}
            r={r}
            fill="rgba(255,138,60,0.04)"
            stroke="rgba(255,138,60,0.35)"
            strokeWidth="2"
          />
          {Array.from({ length: 12 }).map((_, i) => {
            const a = (i * Math.PI) / 6 - Math.PI / 2;
            return (
              <line
                key={i}
                x1={cx + Math.cos(a) * (r - 8)}
                y1={cy + Math.sin(a) * (r - 8)}
                x2={cx + Math.cos(a) * r}
                y2={cy + Math.sin(a) * r}
                stroke="rgba(255,138,60,0.5)"
                strokeWidth="2"
              />
            );
          })}
          {hand(hourAngle, r * 0.5, 4, "#ffd9b8")}
          {hand(minAngle, r * 0.72, 3, "#ffd9b8")}
          {hand(secAngle, r * 0.82, 1.5, "#ff8a3c")}
          <circle cx={cx} cy={cy} r="4" fill="#ff8a3c" />
        </svg>
      </div>
      <div className="text-center text-3xl tracking-[0.2em]" style={{ color: "#ff8a3c" }}>
        {hh}:{mm}
        <span style={{ opacity: 0.6, fontSize: "0.6em" }}>:{ss}</span>
      </div>
      <div className="text-center text-xs mt-2 tracking-widest" style={{ opacity: 0.7 }}>
        {dateStr}
      </div>
    </ModulePanel>
  );
}
