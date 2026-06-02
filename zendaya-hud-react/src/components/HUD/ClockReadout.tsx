import { useEffect, useState } from "react";
import { useZendaya } from "../../store/zendayaStore";

/** Floating digital time + date line for the Orbital/Analog faces. */
export default function ClockReadout() {
  const activeModule = useZendaya((s) => s.activeModule);
  const clockFace = useZendaya((s) => s.clockFace);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  // The Digits face renders its own large time, so it gets no readout.
  if (activeModule !== "clock" || clockFace === "digits") return null;

  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const date = now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });

  return (
    <div className="zen-clock-readout">
      <div className="zen-clock-time">
        {hh}:{mm}
        <span className="zen-clock-sec">:{ss}</span>
      </div>
      <div className="zen-clock-date">{date}</div>
    </div>
  );
}
