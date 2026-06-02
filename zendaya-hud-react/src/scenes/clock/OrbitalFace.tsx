import { useCallback, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeColors } from "../../themes/useThemeColors";
import { presenceOf, type FaceProps } from "./faceCommon";

// Hours / minutes / seconds rings, each tilted differently for a 3D orbit look.
const RINGS = [
  { radius: 1.5, tilt: 0.0 },
  { radius: 1.1, tilt: 0.5 },
  { radius: 0.7, tilt: -0.5 },
];

/** Three tilted orbital rings with a node sweeping each to the current value. */
export default function OrbitalFace({ progressRef, fadeRef }: FaceProps) {
  const colors = useThemeColors();
  const group = useRef<THREE.Group>(null!);
  const nodes = useRef<THREE.Mesh[]>([]);
  const mats = useRef<THREE.MeshBasicMaterial[]>([]);

  const ringColor = useMemo(() => colors.primary.clone(), [colors]);
  const nodeColor = useMemo(() => colors.accent.clone(), [colors]);

  const registerNode = useCallback((el: THREE.Mesh | null) => {
    if (el && !nodes.current.includes(el)) nodes.current.push(el);
  }, []);
  const registerMat = useCallback((el: THREE.MeshBasicMaterial | null) => {
    if (el && !mats.current.includes(el)) mats.current.push(el);
  }, []);

  useFrame(() => {
    const presence = presenceOf(progressRef.current.v, fadeRef.current.v);
    if (group.current) group.current.visible = presence > 0.001;
    for (const m of mats.current) if (m) m.opacity = presence * 0.6;

    const now = new Date();
    const fracs = [
      (now.getHours() % 12) / 12,
      now.getMinutes() / 60,
      now.getSeconds() / 60,
    ];
    for (let i = 0; i < RINGS.length; i++) {
      const node = nodes.current[i];
      if (!node) continue;
      const ang = fracs[i] * Math.PI * 2 - Math.PI / 2; // start at 12 o'clock
      const r = RINGS[i].radius;
      node.position.set(Math.cos(ang) * r, Math.sin(ang) * r, 0);
    }
  });

  return (
    <group ref={group} rotation={[Math.PI * 0.18, 0, 0]}>
      {RINGS.map((ring, i) => (
        <group key={i} rotation={[ring.tilt, ring.tilt * 0.5, 0]}>
          <mesh>
            <torusGeometry args={[ring.radius, 0.012, 8, 120]} />
            <meshBasicMaterial
              ref={registerMat}
              color={ringColor}
              transparent
              opacity={0}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
          <mesh ref={registerNode}>
            <sphereGeometry args={[0.05, 16, 16]} />
            <meshBasicMaterial
              ref={registerMat}
              color={nodeColor}
              transparent
              opacity={0}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}
