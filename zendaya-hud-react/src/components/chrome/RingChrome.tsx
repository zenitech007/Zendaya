import { useRef } from "react";
import type { CSSProperties } from "react";
import { useChromeReaction } from "./chromeFx";

const ORIGIN: CSSProperties = { transformOrigin: "200px 200px" };

export default function RingChrome() {
  const ref = useRef<SVGSVGElement>(null);
  useChromeReaction(ref);
  const ticks = Array.from({ length: 60 });
  return (
    <svg
      ref={ref}
      className="zen-ring-chrome"
      data-testid="ring-chrome"
      viewBox="0 0 400 400"
      aria-hidden
    >
      <g className="zen-rot" style={ORIGIN}>
        {ticks.map((_, i) => {
          const a = (i / ticks.length) * Math.PI * 2;
          const major = i % 5 === 0;
          const r1 = 186;
          const r2 = major ? 168 : 176;
          return (
            <line
              key={i}
              x1={200 + Math.cos(a) * r1}
              y1={200 + Math.sin(a) * r1}
              x2={200 + Math.cos(a) * r2}
              y2={200 + Math.sin(a) * r2}
              stroke="var(--zen-primary)"
              strokeWidth={major ? 2 : 1}
              opacity={0.5}
            />
          );
        })}
      </g>
      <circle
        className="zen-rot-slow"
        cx="200"
        cy="200"
        r="150"
        fill="none"
        stroke="var(--zen-primary)"
        strokeWidth="10"
        strokeDasharray="180 38 300 38 220 38"
        opacity="0.9"
        style={{ ...ORIGIN, filter: "drop-shadow(0 0 6px var(--zen-primary))" }}
      />
      <circle
        className="zen-rot-rev"
        cx="200"
        cy="200"
        r="120"
        fill="none"
        stroke="var(--zen-primary)"
        strokeWidth="4"
        strokeDasharray="300 60"
        opacity="0.7"
        style={ORIGIN}
      />
      <circle
        className="zen-rot"
        cx="200"
        cy="200"
        r="132"
        fill="none"
        stroke="var(--zen-accent)"
        strokeWidth="5"
        strokeDasharray="120 760"
        opacity="0.95"
        style={{ ...ORIGIN, filter: "drop-shadow(0 0 6px var(--zen-accent))" }}
      />
    </svg>
  );
}
