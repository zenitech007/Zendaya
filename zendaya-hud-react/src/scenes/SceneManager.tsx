import { useEffect, useRef } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";
import IdleOrbScene from "./IdleOrbScene";
import GlobeScene from "./GlobeScene";

/** Pure routing: which scene should be shown for the given store signals. */
export function selectScene(s: { scene: string; activeModule: string }): "idle" | "globe" {
  return s.scene === "map" || s.activeModule === "map" ? "globe" : "idle";
}

/**
 * Owns the shared orb->globe morph progress (0 idle … 1 globe), GSAP-tweened on
 * scene change, and corner-docks the whole stage for utility (non-map) modules.
 */
export default function SceneManager() {
  const stage = useRef<THREE.Group>(null!);
  const progressRef = useRef({ v: 0 });

  const scene = useZendaya((s) => s.scene);
  const activeModule = useZendaya((s) => s.activeModule);
  const docked = useZendaya((s) => s.docked);
  const dockCorner = useZendaya((s) => s.dockCorner);

  const target = selectScene({ scene, activeModule });

  // Drive the morph progress.
  useEffect(() => {
    const tween = gsap.to(progressRef.current, {
      v: target === "globe" ? 1 : 0,
      duration: 1.2,
      ease: "power3.inOut",
    });
    return () => {
      tween.kill();
    };
  }, [target]);

  // Corner-dock the stage for docked utility modules (never for the globe).
  useEffect(() => {
    const g = stage.current;
    if (!g) return;
    const dockToCorner = docked && target !== "globe";
    const dockX = dockCorner === "bl" ? -2.8 : 2.8;
    const posTween = gsap.to(g.position, {
      x: dockToCorner ? dockX : 0,
      y: dockToCorner ? -1.6 : 0,
      z: 0,
      duration: 0.8,
      ease: "power3.inOut",
    });
    const scaleTween = gsap.to(g.scale, {
      x: dockToCorner ? 0.35 : 1,
      y: dockToCorner ? 0.35 : 1,
      z: dockToCorner ? 0.35 : 1,
      duration: 0.8,
      ease: "power3.inOut",
    });
    return () => {
      posTween.kill();
      scaleTween.kill();
    };
  }, [docked, dockCorner, target]);

  return (
    <>
      <ambientLight intensity={0.7} />
      <group ref={stage}>
        <IdleOrbScene progressRef={progressRef} />
        <GlobeScene progressRef={progressRef} />
      </group>
    </>
  );
}
