export type ChromeStyle = "ring" | "aperture" | "gauge" | "radar";

export interface ThemeTokens {
  id: string;            // "iris"
  name: string;          // "Iris"
  // palette
  primary: string;       // main chrome + glow color (hex)
  accent: string;        // accent sweep / highlight (hex)
  bg: [string, string];  // radial background stops [inner, outer]
  textGlow: string;      // wordmark/caption glow color
  // 3D stage (consumed in Phase B)
  sceneColor: string;    // tint for orb/globe/scenes
  bloom: number;         // bloom intensity multiplier
  // chrome + atmosphere
  chrome: ChromeStyle;   // which chrome component renders
  ambient: string;       // ambient audio pad id
  grain: number;         // 0..1 background grain/scanline amount
}
