import { useMemo } from "react";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";
import { THEMES } from "./registry";

export interface ThemeColors {
  scene: THREE.Color;
  primary: THREE.Color;
  accent: THREE.Color;
  bloom: number;
}

/**
 * Active-theme colors as THREE.Color objects for 3D materials.
 * Memoized on activeThemeId; unknown ids fall back to Forge.
 */
export function useThemeColors(): ThemeColors {
  const id = useZendaya((s) => s.activeThemeId);
  return useMemo(() => {
    const t = THEMES[id] ?? THEMES.forge;
    return {
      scene: new THREE.Color(t.sceneColor),
      primary: new THREE.Color(t.primary),
      accent: new THREE.Color(t.accent),
      bloom: t.bloom,
    };
  }, [id]);
}
