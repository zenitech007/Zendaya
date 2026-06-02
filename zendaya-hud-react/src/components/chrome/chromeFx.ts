import gsap from "gsap";
import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import { useZendaya } from "../../store/zendayaStore";
import type { ChromeFx } from "../../store/zendayaStore";
import { selectScene } from "../../scenes/sceneRouting";

/** The chrome reaction runs over the same window as the 1.2 s scene morph. */
export const MORPH_MS = 1200;
const DUR = MORPH_MS / 1000;

/**
 * Build (and immediately play) the selected chrome reaction on an SVG frame.
 * Returns the GSAP timeline so callers can kill it on re-trigger / unmount.
 * Each timeline lasts exactly DUR seconds. Animates the whole <svg>; the inner
 * CSS-driven idle rotation continues underneath.
 */
export function playChromeFx(fx: ChromeFx, el: SVGSVGElement): gsap.core.Timeline {
  gsap.set(el, { transformOrigin: "center center" });
  const tl = gsap.timeline();
  switch (fx) {
    case "aperture":
      // Contract inward, then reopen — a camera-iris blink.
      tl.to(el, { scale: 0.82, duration: DUR * 0.42, ease: "power2.in" })
        .to(el, { scale: 1, duration: DUR * 0.58, ease: "power3.out" });
      break;
    case "spin":
      // Brief rotation kick + brightness flare, then settle.
      tl.to(el, { rotation: "+=26", filter: "brightness(1.9)", duration: DUR * 0.35, ease: "power1.in" })
        .to(el, { rotation: "+=0", filter: "brightness(1)", duration: DUR * 0.65, ease: "power2.out" });
      break;
    case "radar":
      // One full sweep + a brightness pulse that crests mid-sweep.
      tl.to(el, { rotation: "+=360", duration: DUR, ease: "none" }, 0)
        .to(el, { filter: "brightness(1.7)", duration: DUR * 0.5, ease: "power1.out" }, 0)
        .to(el, { filter: "brightness(1)", duration: DUR * 0.5, ease: "power1.in" }, DUR * 0.5);
      break;
  }
  return tl;
}

/**
 * Fires the active `chromeFx` on the given SVG ref whenever the 3D stage scene
 * changes. No reaction on first mount; a pure preference change does not refire.
 */
export function useChromeReaction(ref: RefObject<SVGSVGElement>) {
  const fx = useZendaya((s) => s.chromeFx);
  const scene = useZendaya((s) => s.scene);
  const activeModule = useZendaya((s) => s.activeModule);
  const stage = selectScene({ scene, activeModule });
  const prev = useRef<string>(stage);
  const tl = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => {
    if (stage === prev.current) return;
    prev.current = stage;
    const el = ref.current;
    if (!el) return;
    tl.current?.kill();
    tl.current = playChromeFx(fx, el);
    return () => { tl.current?.kill(); };
  }, [stage, fx, ref]);
}
