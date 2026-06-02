import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";
import { selectScene, type StageScene } from "./sceneRouting";
import IdleOrbScene from "./IdleOrbScene";
import GlobeScene from "./GlobeScene";
import ClockScene from "./ClockScene";
import WeatherScene from "./WeatherScene";

// Keep the old import path working for tests/consumers that import the router.
export { selectScene };

/**
 * Owns the shared orb→scene morph progress (0 idle … 1 active scene), GSAP-tweened
 * on scene change, mounts the active heavy scene (and keeps it alive through the
 * exit morph), and corner-docks the whole stage for utility (idle) modules.
 */
export default function SceneManager() {
  const stage = useRef<THREE.Group>(null!);
  const progressRef = useRef({ v: 0 });

  const scene = useZendaya((s) => s.scene);
  const activeModule = useZendaya((s) => s.activeModule);
  const docked = useZendaya((s) => s.docked);
  const dockCorner = useZendaya((s) => s.dockCorner);

  const target = selectScene({ scene, activeModule });

  // Which heavy scene is mounted. Mount immediately on enter; defer unmount to
  // the end of the exit morph so the dissolve plays out before it disappears.
  const [mounted, setMounted] = useState<StageScene>(target);

  // Drive the morph progress.
  useEffect(() => {
    const tween = gsap.to(progressRef.current, {
      v: target === "idle" ? 0 : 1,
      duration: 1.2,
      ease: "power3.inOut",
    });
    return () => {
      tween.kill();
    };
  }, [target]);

  // Mount on enter; defer unmount until the exit morph finishes (~1.3 s).
  useEffect(() => {
    if (target !== "idle") {
      setMounted(target);
      return;
    }
    const id = window.setTimeout(() => setMounted("idle"), 1300);
    return () => window.clearTimeout(id);
  }, [target]);

  // Corner-dock the stage only for docked utility modules in the idle scene.
  useEffect(() => {
    const g = stage.current;
    if (!g) return;
    const dockToCorner = docked && target === "idle";
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
        {mounted === "globe" && <GlobeScene progressRef={progressRef} />}
        {mounted === "weather" && <WeatherScene progressRef={progressRef} />}
        {mounted === "clock" && <ClockScene progressRef={progressRef} />}
      </group>
    </>
  );
}
