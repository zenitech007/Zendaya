import { useCallback, useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeColors } from "../../themes/useThemeColors";
import { presenceOf, type FaceProps } from "./faceCommon";

/** Tilted 3D dial: rim + 12 ticks + three box hands pivoting at the centre. */
export default function AnalogFace({ progressRef, fadeRef }: FaceProps) {
  const colors = useThemeColors();
  const group = useRef<THREE.Group>(null!);
  const hourHand = useRef<THREE.Group>(null!);
  const minHand = useRef<THREE.Group>(null!);
  const secHand = useRef<THREE.Group>(null!);
  const mats = useRef<THREE.MeshBasicMaterial[]>([]);

  const rimColor = useMemo(() => colors.primary.clone(), [colors]);
  const handColor = useMemo(() => colors.accent.clone(), [colors]);
  const ticks = useMemo(() => Array.from({ length: 12 }, (_, i) => i), []);
  // Reused across frames so the render loop allocates no Date objects; we still
  // need a Date (not raw Date.now()) for the timezone-aware local hour/minute.
  const clock = useRef(new Date());

  useEffect(() => () => {
    mats.current = [];
  }, []);

  const registerMat = useCallback((el: THREE.MeshBasicMaterial | null) => {
    if (el && !mats.current.includes(el)) mats.current.push(el);
  }, []);

  useFrame(() => {
    const presence = presenceOf(progressRef.current.v, fadeRef.current.v);
    if (group.current) group.current.visible = presence > 0.001;
    for (const m of mats.current) if (m) m.opacity = presence;

    const now = clock.current;
    now.setTime(Date.now());
    const sec = now.getSeconds() + now.getMilliseconds() / 1000;
    const min = now.getMinutes() + sec / 60;
    const hour = (now.getHours() % 12) + min / 60;
    if (secHand.current) secHand.current.rotation.z = -(sec / 60) * Math.PI * 2;
    if (minHand.current) minHand.current.rotation.z = -(min / 60) * Math.PI * 2;
    if (hourHand.current) hourHand.current.rotation.z = -(hour / 12) * Math.PI * 2;
  });

  return (
    <group ref={group} rotation={[Math.PI * 0.16, 0, 0]}>
      <mesh>
        <torusGeometry args={[1.5, 0.012, 8, 160]} />
        <meshBasicMaterial
          ref={registerMat}
          color={rimColor}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {ticks.map((i) => {
        const ang = (i / 12) * Math.PI * 2;
        const r = 1.35;
        return (
          <mesh key={i} position={[Math.cos(ang) * r, Math.sin(ang) * r, 0]} rotation={[0, 0, ang]}>
            <boxGeometry args={[0.12, 0.02, 0.02]} />
            <meshBasicMaterial
              ref={registerMat}
              color={rimColor}
              transparent
              opacity={0}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        );
      })}
      {/* Each hand's box is offset +Y so its base sits at the group origin and
          it pivots about Z at the centre; rotation 0 points to 12 o'clock. */}
      <group ref={hourHand}>
        <mesh position={[0, 0.4, 0.02]}>
          <boxGeometry args={[0.03, 0.8, 0.02]} />
          <meshBasicMaterial
            ref={registerMat}
            color={handColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>
      <group ref={minHand}>
        <mesh position={[0, 0.6, 0.03]}>
          <boxGeometry args={[0.022, 1.2, 0.02]} />
          <meshBasicMaterial
            ref={registerMat}
            color={handColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>
      <group ref={secHand}>
        <mesh position={[0, 0.65, 0.04]}>
          <boxGeometry args={[0.01, 1.3, 0.01]} />
          <meshBasicMaterial
            ref={registerMat}
            color={rimColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>
    </group>
  );
}
