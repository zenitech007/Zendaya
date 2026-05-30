import { gsap } from "gsap";
import * as THREE from "three";
import { DUR, EASE } from "./easing";
import { fadeSubtree, tweenUniform } from "./transitions";
import { useZendaya } from "../store/zendayaStore";
// Animate store scalars by tweening a local proxy and calling the setter.
// Lets GSAP drive Zustand values without subscribing the timeline to React.
function tweenStoreScalar(getter, setter, target, duration, ease) {
    const proxy = { v: getter() };
    return gsap.to(proxy, {
        v: target,
        duration,
        ease,
        onUpdate: () => setter(proxy.v),
    });
}
export function dockOrbShowMap({ orb, map }) {
    const z = useZendaya.getState();
    const corner = z.dockCorner ?? "br";
    const dockX = corner === "bl" ? -2.8 : 2.8;
    const tl = gsap.timeline({ defaults: { duration: DUR.scene, ease: EASE.cinematic } });
    // Prepare holographic expansion scale
    tl.set(map.scale, { x: 1.08, y: 1.08, z: 1.08 }, 0);
    // Map phase 1: holographic emergence & dock orb to chosen bottom corner
    tl.to(orb.position, { x: dockX, y: -1.6, z: 0 }, 0)
        .to(orb.scale, { x: 0.35, y: 0.35, z: 0.35 }, 0)
        .to(map.position, { x: 0, y: 0, z: 0 }, 0)
        .to(map.scale, { x: 1.0, y: 1.0, z: 1.0 }, 0)
        .add(fadeSubtree(map, 1, DUR.scene, EASE.cinematic), 0)
        .add(tweenStoreScalar(() => useZendaya.getState().bgDim, z.setBgDim, 0.65, DUR.scene, EASE.cinematic), 0)
        .add(tweenStoreScalar(() => useZendaya.getState().fogDensity, z.setFogDensity, 0.12, DUR.scene, EASE.cinematic), 0);
    // Animate the MapModule shader's uBlur uniform (if available) from 20 -> 0
    map.children.forEach(child => {
        if (child.material instanceof THREE.ShaderMaterial) {
            tl.add(tweenUniform(child.material, "uBlur", 0, DUR.scene, EASE.cinematic), 0);
        }
    });
    return tl;
}
export function undockOrbHideMap({ orb, map }) {
    const z = useZendaya.getState();
    const tl = gsap.timeline({ defaults: { duration: DUR.scene, ease: EASE.cinematic } });
    // Map phase out: shrink and fade while orb returns
    tl.to(orb.position, { x: 0, y: 0, z: 0 }, 0)
        .to(orb.scale, { x: 1, y: 1, z: 1 }, 0)
        .to(map.scale, { x: 1.05, y: 1.05, z: 1.05 }, 0) // slightly expands outwards while fading instead of collapsing
        .add(fadeSubtree(map, 0, DUR.base, "power2.in"), 0)
        .add(tweenStoreScalar(() => useZendaya.getState().bgDim, z.setBgDim, 0, DUR.base, "power2.in"), 0)
        .add(tweenStoreScalar(() => useZendaya.getState().fogDensity, z.setFogDensity, 0.04, DUR.base, "power2.in"), 0);
    // Animate the MapModule shader's uBlur uniform (if available) from 0 -> 20
    map.children.forEach(child => {
        if (child.material instanceof THREE.ShaderMaterial) {
            tl.add(tweenUniform(child.material, "uBlur", 20.0, DUR.base, "power2.in"), 0);
        }
    });
    return tl;
}
// Quick "voice activated" pulse \u2014 punches the orb's scale up briefly.
export function voiceActivatePulse(orb) {
    const tl = gsap.timeline();
    tl.to(orb.scale, { x: 1.2, y: 1.2, z: 1.2, duration: 0.12, ease: "power2.out" })
        .to(orb.scale, { x: 1, y: 1, z: 1, duration: 0.35, ease: EASE.settle });
    return tl;
}
