import type { ThemeTokens } from "./types";

export const THEMES: Record<string, ThemeTokens> = {
  forge: {
    id: "forge", name: "Forge",
    primary: "#ff8a1e", accent: "#19d3a0", bg: ["#1a0d05", "#070302"],
    textGlow: "#ffb060", sceneColor: "#ff8a3c", bloom: 1.3,
    chrome: "ring", ambient: "warm-pad", grain: 0.18,
  },
  iris: {
    id: "iris", name: "Iris",
    primary: "#2fd6ff", accent: "#ff4d4d", bg: ["#06182a", "#02060c"],
    textGlow: "#9fe9ff", sceneColor: "#2fd6ff", bloom: 1.1,
    chrome: "aperture", ambient: "airy-pad", grain: 0.30,
  },
};

export const THEME_ORDER: string[] = ["forge", "iris"];
