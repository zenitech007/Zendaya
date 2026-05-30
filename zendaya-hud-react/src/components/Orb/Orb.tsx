import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useZendaya, type AiState } from "../../store/zendayaStore";

const ORB_COLOR = new THREE.Color("#ff8a3c");

const STATE_PULSE: Record<AiState, number> = {
  idle:      0.00,
  aware:     0.04,
  listening: 0.10,
  thinking:  0.06,
  speaking:  0.14,
  searching: 0.06,
  mapping:   0.04,
  alert:     0.10,
  error:     0.06,
};

interface OrbProps {
  radius?: number;
}

export default function Orb({ radius = 1.0 }: OrbProps) {
  const group = useRef<THREE.Group>(null!);
  const core = useRef<THREE.Mesh>(null!);
  const glow = useRef<THREE.Mesh>(null!);

  const smoothed = useRef({ pulse: 0, voiceScale: 1 });

  const coreMat = useMemo(
    () =>
      new THREE.MeshBasicMaterial({
        color: ORB_COLOR,
        transparent: true,
        opacity: 0.95,
      }),
    []
  );

  const glowMat = useMemo(() => {
    return new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: ORB_COLOR.clone() },
        uIntensity: { value: 1.0 },
      },
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          vec4 mv = modelViewMatrix * vec4(position, 1.0);
          vNormal = normalize(normalMatrix * normal);
          vViewDir = normalize(-mv.xyz);
          gl_Position = projectionMatrix * mv;
        }
      `,
      fragmentShader: `
        uniform vec3 uColor;
        uniform float uIntensity;
        varying vec3 vNormal;
        varying vec3 vViewDir;
        void main() {
          float fres = 1.0 - max(dot(vNormal, vViewDir), 0.0);
          float a = pow(fres, 2.2) * uIntensity;
          gl_FragColor = vec4(uColor, a);
        }
      `,
      transparent: true,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false,
    });
  }, []);

  useFrame((_, dt) => {
    const z = useZendaya.getState();
    const targetPulse = STATE_PULSE[z.ai] ?? 0;
    const s = smoothed.current;

    s.pulse += (targetPulse - s.pulse) * Math.min(1, dt * 3);

    const targetVoice = 1 + z.audioLevel * 0.15;
    s.voiceScale += (targetVoice - s.voiceScale) * Math.min(1, dt * 10);

    const t = performance.now() * 0.001;
    const breath = 1 + Math.sin(t * 1.2) * s.pulse;

    if (group.current) {
      const scale = s.voiceScale * breath;
      group.current.scale.setScalar(scale);
    }

    if (glowMat.uniforms) {
      glowMat.uniforms.uIntensity.value = 0.85 + s.pulse * 1.6;
    }
  });

  return (
    <group ref={group}>
      {/* Soft outer fresnel glow */}
      <mesh ref={glow} scale={1.8}>
        <sphereGeometry args={[radius, 48, 48]} />
        <primitive object={glowMat} attach="material" />
      </mesh>
      {/* Solid orange core */}
      <mesh ref={core}>
        <sphereGeometry args={[radius * 0.55, 48, 48]} />
        <primitive object={coreMat} attach="material" />
      </mesh>
    </group>
  );
}
