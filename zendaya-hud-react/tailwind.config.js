/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        zen: {
          violet: "#a855f7",
          cyan: "#06b6d4",
          red: "#ef4444",
          ink: "#07090f",
          text: "rgba(255,255,255,0.85)",
          dim: "rgba(255,255,255,0.45)",
          faint: "rgba(255,255,255,0.25)",
        },
      },
      fontFamily: {
        display: ['"Orbitron"', "sans-serif"],
        mono: ['"Share Tech Mono"', "monospace"],
      },
    },
  },
  plugins: [],
};
