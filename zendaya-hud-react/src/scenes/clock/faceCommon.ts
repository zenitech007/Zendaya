import * as THREE from "three";

/** Shared props for every clock face. */
export interface FaceProps {
  progressRef: React.MutableRefObject<{ v: number }>;
  fadeRef: React.MutableRefObject<{ v: number }>;
}

/**
 * Combined 0..1 presence for a face: the shared orb→scene morph (gated so the
 * face only appears once the morph passes 0.15) multiplied by the per-face
 * crossfade value driven on face switches.
 */
export function presenceOf(progress: number, fade: number): number {
  return THREE.MathUtils.smoothstep(progress, 0.15, 1.0) * fade;
}
