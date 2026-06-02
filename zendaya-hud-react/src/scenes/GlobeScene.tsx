import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import DissolveField from "./DissolveField";

export interface GlobeSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
}

/** The point-cloud globe: spins only once the field has reformed (spin ∝ progress). */
export default function GlobeScene({ progressRef }: GlobeSceneProps) {
  const spin = useRef<THREE.Group>(null!);
  useFrame((_, dt) => {
    if (spin.current) spin.current.rotation.y += dt * 0.12 * progressRef.current.v;
  });
  return (
    <group ref={spin}>
      <DissolveField progressRef={progressRef} />
    </group>
  );
}
