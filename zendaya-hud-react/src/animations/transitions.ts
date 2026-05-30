import { gsap } from "gsap";
import * as THREE from "three";
import { DUR, EASE } from "./easing";

// Walks a Three.js subtree and tweens every material's opacity to a target.
// Materials are flagged transparent up front so the first frame already
// blends. Returns the GSAP tween so callers can chain into a timeline.
export function fadeSubtree(
  root: THREE.Object3D | null,
  target: number,
  duration: number = DUR.base,
  ease: string = EASE.cinematic
) {
  if (!root) return gsap.to({}, { duration: 0 });

  const mats: { mat: THREE.Material & { opacity?: number }; current: number }[] = [];
  root.traverse((o) => {
    const m = (o as THREE.Mesh).material as
      | (THREE.Material & { opacity?: number })
      | undefined;
    if (!m) return;
    m.transparent = true;
    mats.push({ mat: m, current: m.opacity ?? 1 });
  });

  const proxy = { v: 0 };
  return gsap.to(proxy, {
    v: 1,
    duration,
    ease,
    onUpdate: () => {
      for (const { mat, current } of mats) {
        mat.opacity = current + (target - current) * proxy.v;
      }
    },
    onComplete: () => {
      for (const { mat } of mats) mat.opacity = target;
    },
  });
}

// Smoothly tweens an arbitrary numeric uniform on a ShaderMaterial.
export function tweenUniform(
  mat: THREE.ShaderMaterial | null,
  uniform: string,
  target: number,
  duration: number = DUR.base,
  ease: string = EASE.cinematic
) {
  if (!mat || !mat.uniforms[uniform]) return gsap.to({}, { duration: 0 });
  return gsap.to(mat.uniforms[uniform], { value: target, duration, ease });
}
