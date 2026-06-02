/**
 * Pure store-state → 3D stage scene mapping. Lives in its own module so chrome
 * (and other consumers) can route without importing the whole 3D scene graph.
 */
export type StageScene = "idle" | "globe" | "weather" | "clock";

export function selectScene(s: { scene: string; activeModule: string }): StageScene {
  if (s.scene === "map" || s.activeModule === "map") return "globe";
  if (s.activeModule === "weather") return "weather";
  if (s.activeModule === "clock") return "clock";
  return "idle";
}
