import type { CSSProperties } from "react";

const ORIGIN: CSSProperties = { transformOrigin: "200px 200px" };

export default function ApertureChrome() {
  const blades = Array.from({ length: 12 });
  return (
    <svg
      className="zen-aperture-chrome"
      data-testid="aperture-chrome"
      viewBox="0 0 400 400"
      aria-hidden
    >
      {/* outer rim */}
      <circle
        cx="200" cy="200" r="160" fill="none"
        stroke="var(--zen-primary)" strokeWidth="2"
        opacity="0.85"
        style={{ filter: "drop-shadow(0 0 10px var(--zen-primary))" }}
      />

      {/* aperture blades */}
      <g className="zen-rot-slow" style={ORIGIN}>
        {blades.map((_, i) => {
          const a = (i / blades.length) * Math.PI * 2;
          const inner = 62;
          const outer = 150;
          return (
            <line
              key={i}
              x1={200 + Math.cos(a) * inner}
              y1={200 + Math.sin(a) * inner}
              x2={200 + Math.cos(a + 0.5) * outer}
              y2={200 + Math.sin(a + 0.5) * outer}
              stroke="var(--zen-primary)"
              strokeWidth="2"
              opacity="0.45"
            />
          );
        })}
      </g>

      {/* dashed rotating ring */}
      <circle
        className="zen-rot-rev"
        cx="200" cy="200" r="120" fill="none"
        stroke="var(--zen-primary)" strokeWidth="2"
        strokeDasharray="6 12"
        opacity="0.6"
        style={ORIGIN}
      />

      {/* pupil + glow */}
      <circle cx="200" cy="200" r="54" fill="none"
        stroke="var(--zen-primary)" strokeWidth="3"
        opacity="0.95"
        style={{ filter: "drop-shadow(0 0 12px var(--zen-primary))" }}
      />
      <circle cx="200" cy="200" r="6" fill="var(--zen-accent)"
        style={{ filter: "drop-shadow(0 0 8px var(--zen-accent))" }}
      />
    </svg>
  );
}
