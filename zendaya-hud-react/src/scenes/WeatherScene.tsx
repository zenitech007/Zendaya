import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import DissolveField from "./DissolveField";
import { buildFormPoints } from "./weatherForms";
import { useWeather } from "../hooks/useWeather";

export interface WeatherSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
}

/**
 * Morphs the orb point-cloud into the current weather form and gently rotates.
 * Remounts the field (via `key={form}`) when the condition changes so the
 * geometry rebuilds to the new form. All color comes from the active theme.
 */
export default function WeatherScene({ progressRef }: WeatherSceneProps) {
  const { form } = useWeather();
  const spin = useRef<THREE.Group>(null!);
  const positions = useMemo(() => buildFormPoints(form, 9000, 1.4), [form]);

  useFrame((_, dt) => {
    if (spin.current) spin.current.rotation.y += dt * 0.08 * progressRef.current.v;
  });

  return (
    <group ref={spin}>
      <DissolveField
        key={form}
        progressRef={progressRef}
        count={9000}
        targetPositions={positions}
        plain
      />
    </group>
  );
}
