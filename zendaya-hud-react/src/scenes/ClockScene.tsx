import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { useZendaya, type ClockFace } from "../store/zendayaStore";
import OrbitalFace from "./clock/OrbitalFace";
import DigitsFace from "./clock/DigitsFace";
import AnalogFace from "./clock/AnalogFace";

export interface ClockSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
}

/**
 * Hosts the three clock faces. The selected face comes from the store; switching
 * crossfades a shared `fadeRef` (out → swap → in) instead of hard-cutting. Each
 * face multiplies its presence by `fadeRef.v`, so the tween dims/raises it.
 */
export default function ClockScene({ progressRef }: ClockSceneProps) {
  const clockFace = useZendaya((s) => s.clockFace);
  const fadeRef = useRef({ v: 1 });
  const [shownFace, setShownFace] = useState<ClockFace>(clockFace);

  useEffect(() => {
    if (clockFace === shownFace) return;
    const tl = gsap.timeline();
    tl.to(fadeRef.current, { v: 0, duration: 0.18, ease: "power2.in" });
    tl.add(() => setShownFace(clockFace));
    tl.to(fadeRef.current, { v: 1, duration: 0.22, ease: "power2.out" });
    return () => {
      tl.kill();
    };
  }, [clockFace, shownFace]);

  return (
    <group>
      {shownFace === "orbital" && <OrbitalFace progressRef={progressRef} fadeRef={fadeRef} />}
      {shownFace === "digits" && <DigitsFace progressRef={progressRef} fadeRef={fadeRef} />}
      {shownFace === "analog" && <AnalogFace progressRef={progressRef} fadeRef={fadeRef} />}
    </group>
  );
}
