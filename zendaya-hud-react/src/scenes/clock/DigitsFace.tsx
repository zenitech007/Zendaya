import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeColors } from "../../themes/useThemeColors";
import { buildDigitPoints } from "./digitFont";
import { presenceOf, type FaceProps } from "./faceCommon";

function hhmmOf(d: Date): string {
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/** Particle HH:MM glyphs wrapped by a thin seconds ring with a sweeping node. */
export default function DigitsFace({ progressRef, fadeRef }: FaceProps) {
  const colors = useThemeColors();
  const [hhmm, setHhmm] = useState(() => hhmmOf(new Date()));
  const positions = useMemo(() => buildDigitPoints(hhmm), [hhmm]);

  const group = useRef<THREE.Group>(null!);
  const glyphMat = useRef<THREE.PointsMaterial>(null);
  const ringMat = useRef<THREE.MeshBasicMaterial>(null);
  const nodeMat = useRef<THREE.MeshBasicMaterial>(null);
  const node = useRef<THREE.Mesh>(null);

  const glyphColor = useMemo(() => colors.accent.clone(), [colors]);
  const ringColor = useMemo(() => colors.primary.clone(), [colors]);

  useEffect(() => {
    const id = window.setInterval(() => setHhmm(hhmmOf(new Date())), 1000);
    return () => window.clearInterval(id);
  }, []);

  useFrame(() => {
    const presence = presenceOf(progressRef.current.v, fadeRef.current.v);
    if (group.current) group.current.visible = presence > 0.001;
    if (glyphMat.current) glyphMat.current.opacity = presence;
    if (ringMat.current) ringMat.current.opacity = presence * 0.4;
    if (nodeMat.current) nodeMat.current.opacity = presence;

    const sec = new Date().getSeconds() / 60;
    const ang = sec * Math.PI * 2 - Math.PI / 2;
    if (node.current) node.current.position.set(Math.cos(ang) * 1.7, Math.sin(ang) * 1.7, 0);
  });

  return (
    <group ref={group} rotation={[Math.PI * 0.06, 0, 0]}>
      <points key={hhmm}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          ref={glyphMat}
          color={glyphColor}
          size={0.055}
          transparent
          opacity={0}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
      <mesh>
        <torusGeometry args={[1.7, 0.01, 8, 120]} />
        <meshBasicMaterial
          ref={ringMat}
          color={ringColor}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={node}>
        <sphereGeometry args={[0.045, 16, 16]} />
        <meshBasicMaterial
          ref={nodeMat}
          color={glyphColor}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}
