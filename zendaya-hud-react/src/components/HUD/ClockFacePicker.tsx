import { useZendaya, type ClockFace } from "../../store/zendayaStore";

const FACES: { id: ClockFace; label: string }[] = [
  { id: "orbital", label: "ORBITAL" },
  { id: "digits", label: "DIGITS" },
  { id: "analog", label: "ANALOG" },
];

/** Theme-picker-style dot row; visible only while the clock scene is active. */
export default function ClockFacePicker() {
  const activeModule = useZendaya((s) => s.activeModule);
  const clockFace = useZendaya((s) => s.clockFace);
  const setClockFace = useZendaya((s) => s.setClockFace);

  if (activeModule !== "clock") return null;

  return (
    <div className="zen-clock-face-picker">
      {FACES.map((f) => (
        <button
          key={f.id}
          type="button"
          className={`zen-face-dot${clockFace === f.id ? " active" : ""}`}
          onClick={() => setClockFace(f.id)}
        >
          <span className="zen-face-lbl">{f.label}</span>
        </button>
      ))}
    </div>
  );
}
