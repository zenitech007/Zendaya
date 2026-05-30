import { useEffect } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";

function nodTimeline(g: THREE.Group) {
  gsap.to(g.position, { y: -0.15, duration: 0.15, ease: "power2.in" });
  gsap.to(g.position, { y: 0, duration: 0.30, delay: 0.15, ease: "back.out(2)" });
}

function shakeTimeline(g: THREE.Group) {
  gsap.to(g.position, { x: -0.10, duration: 0.10, ease: "sine.inOut" });
  gsap.to(g.position, { x: 0.10, duration: 0.10, delay: 0.10, ease: "sine.inOut" });
  gsap.to(g.position, { x: -0.05, duration: 0.10, delay: 0.20, ease: "sine.inOut" });
  gsap.to(g.position, { x: 0, duration: 0.30, delay: 0.30, ease: "sine.out" });
}

function waveTimeline(g: THREE.Group) {
  gsap.to(g.rotation, { z: 0.20, duration: 0.30, ease: "power2.inOut" });
  gsap.to(g.position, { x: 0.08, duration: 0.30, ease: "power2.inOut" });
  gsap.to(g.rotation, { z: 0, duration: 0.50, delay: 0.30, ease: "power2.inOut" });
  gsap.to(g.position, { x: 0, duration: 0.50, delay: 0.30, ease: "power2.inOut" });
}

function shrugTimeline(g: THREE.Group) {
  gsap.to(g.scale, { x: 1.12, y: 1.12, z: 1.12, duration: 0.15, ease: "power2.out" });
  gsap.to(g.scale, { x: 1.0, y: 1.0, z: 1.0, duration: 0.35, delay: 0.15, ease: "elastic.out(1, 0.6)" });
}

function fallbackWobble(g: THREE.Group) {
  // raf-only mini-wobble if gsap fails — visual proof of pulse.
  const start = performance.now();
  const initial = g.scale.x;
  function frame() {
    const t = (performance.now() - start) / 200;
    if (t >= 1) {
      g.scale.setScalar(initial);
      return;
    }
    g.scale.setScalar(initial * (1 + 0.08 * Math.sin(t * Math.PI)));
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

export function useBodyAction(groupRef: React.MutableRefObject<THREE.Group | null>) {
  const pulse = useZendaya((s) => s.bodyActionPulse);
  useEffect(() => {
    const g = groupRef.current;
    if (!g || !pulse.action) return;
    try {
      gsap.killTweensOf([g.position, g.rotation, g.scale]);
      switch (pulse.action) {
        case "nod":   nodTimeline(g);   break;
        case "shake": shakeTimeline(g); break;
        case "wave":  waveTimeline(g);  break;
        case "shrug": shrugTimeline(g); break;
      }
    } catch (e) {
      console.warn("[orb] body-action GSAP failed, falling back to raf wobble", e);
      fallbackWobble(g);
    }
  }, [pulse.ts, groupRef, pulse.action]);
}
