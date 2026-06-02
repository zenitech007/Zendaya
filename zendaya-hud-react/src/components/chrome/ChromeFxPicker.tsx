import type { CSSProperties } from "react";
import { useZendaya, type ChromeFx } from "../../store/zendayaStore";

const FX: { id: ChromeFx; label: string }[] = [
  { id: "aperture", label: "IRIS" },
  { id: "spin", label: "SPIN" },
  { id: "radar", label: "SCAN" },
];

/** Picks the persisted chrome scene-change reaction. Always visible. */
export default function ChromeFxPicker() {
  const fx = useZendaya((s) => s.chromeFx);
  const setChromeFx = useZendaya((s) => s.setChromeFx);

  return (
    <div className="zen-chromefx-picker" role="group" aria-label="Chrome reaction picker">
      {FX.map((f) => (
        <button
          key={f.id}
          type="button"
          className={"zen-fx-dot" + (f.id === fx ? " active" : "")}
          aria-current={f.id === fx || undefined}
          title={f.label}
          onClick={() => setChromeFx(f.id)}
          style={{ "--dot": "var(--zen-primary)" } as CSSProperties}
        >
          <span className="zen-fx-lbl">{f.label}</span>
        </button>
      ))}
    </div>
  );
}
