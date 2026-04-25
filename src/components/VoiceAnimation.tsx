import React, { useMemo } from "react";

type VoiceAnimationProps = {
  audioLevel: number; // 0..1
  listening?: boolean;
  speaking?: boolean;
  size?: number; // px - for scaling UI
};

export const VoiceAnimation: React.FC<VoiceAnimationProps> = ({
  audioLevel,
  listening = false,
  speaking = false,
  size = 160,
}) => {
  // clamp and smooth audio level visually
  const level = Math.min(1, Math.max(0, audioLevel ?? 0));

  const glowIntensity = useMemo(() => {
    // calculate glow multiplier
    const base = 0.45;
    return base + level * 1.4 + (speaking ? 0.6 : 0);
  }, [level, speaking]);

  const faceFill = listening ? "#0f1724" : "#0b0b0d";

  return (
    <div style={{ width: size, height: size, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div
        aria-hidden
        style={{
          position: "relative",
          width: "82%",
          height: "82%",
          borderRadius: "9999px",
          background: "rgba(6,6,10,0.42)",
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          border: "1px solid rgba(255,255,255,0.04)",
          boxShadow: `0 6px ${20 * glowIntensity}px rgba(6,182,212,${0.06 * glowIntensity})`,
          transition: "box-shadow 140ms linear, transform 140ms",
          transform: speaking ? `scale(${1 + level * 0.04})` : "none",
          overflow: "hidden",
        }}
      >
        {/* face SVG simplified; we animate glow rings around it */}
        <svg viewBox="0 0 120 120" width="88%" height="88%" role="img" aria-hidden>
          <defs>
            <radialGradient id="va" cx="30%" cy="25%">
              <stop offset="0%" stopColor="#6ee7b7" stopOpacity={0.06 + level * 0.08} />
              <stop offset="60%" stopColor="#7c3aed" stopOpacity={0.06 + level * 0.06} />
              <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.02 + level * 0.02} />
            </radialGradient>
            <filter id="vGlow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation={3 + level * 5} result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <circle cx="60" cy="60" r="56" fill="url(#va)" opacity={0.65 + level * 0.12} />

          <g transform="translate(12,6)">
            <ellipse cx="48" cy="36" rx="32" ry="28" fill={faceFill} filter="url(#vGlow)" />
            <path d="M16 28 C 16 14, 80 10, 84 28 C86 34, 78 44, 66 46 C48 48, 20 48, 16 28 Z"
              fill="none" stroke={`rgba(124,58,237,${0.18 + level * 0.25})`} strokeWidth="1.6" strokeLinecap="round" />
          </g>

          <g transform="translate(18,26)">
            <path d="M24 8 C 40 -2, 80 2, 82 20 C 84 40, 62 64, 42 64 C 22 64, 14 36, 24 8 Z"
              fill="#0f1724" />
            <circle cx="40" cy="30" r={1.4 + level * 3.2} fill="#9be7ff" opacity={0.7 + level * 0.3} />
            <circle cx="64" cy="30" r={1.4 + level * 3.2} fill="#c7a7ff" opacity={0.7 + level * 0.3} />
            <path d="M36 12 L48 8 L60 12" stroke={`rgba(6,182,212,${0.18 + level * 0.22})`} strokeWidth="1.2" strokeLinecap="round" fill="none" />
          </g>

          {/* animated neon arcs behind face showing level */}
          <g transform="translate(0,0)">
            <path d="M60 8 a52 52 0 0 1 0 104" stroke={`rgba(124,58,237,${0.08 + level * 0.32})`} strokeWidth={1 + level * 3} fill="none" strokeLinecap="round" opacity={0.9} />
            <path d="M60 18 a42 42 0 0 1 0 84" stroke={`rgba(6,182,212,${0.06 + level * 0.24})`} strokeWidth={1 + level * 2} fill="none" strokeLinecap="round" opacity={0.85} />
          </g>
        </svg>
      </div>

      {/* subtle waveform bar below (tiny visual aid) */}
      <div style={{ position: "absolute", bottom: -8, left: "50%", transform: "translateX(-50%)", display: "flex", gap: 4 }}>
        {Array.from({ length: 6 }).map((_, i) => {
          const h = 4 + level * (8 + i * 3) * (1 + (i % 2) * 0.4);
          const opacity = 0.35 + level * 0.6;
          return (
            <div key={i} style={{
              width: 4,
              height: `${h}px`,
              borderRadius: 999,
              background: `linear-gradient(180deg, rgba(124,58,237,${0.6 * opacity}), rgba(6,182,212,${0.8 * opacity}))`,
              transition: "height 120ms linear",
            }} />
          );
        })}
      </div>
    </div>
  );
};
