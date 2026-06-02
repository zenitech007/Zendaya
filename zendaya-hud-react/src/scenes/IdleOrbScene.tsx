import { useEffect, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya, type AiState } from "../store/zendayaStore";
import { useBodyAction } from "../hooks/useBodyAction";
import { useThemeColors } from "../themes/useThemeColors";

const STATE_PULSE: Record<AiState, number> = {
  idle: 0.0, aware: 0.04, listening: 0.1, thinking: 0.06,
  speaking: 0.14, searching: 0.06, mapping: 0.04, alert: 0.1, error: 0.06,
};

export interface IdleOrbSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
  radius?: number;
}

export default function IdleOrbScene({ progressRef, radius = 1.0 }: IdleOrbSceneProps) {
  const group = useRef<THREE.Group>(null!);
  const bodyGroup = useRef<THREE.Group>(null!);
  const smoothed = useRef({ pulse: 0, voiceScale: 1, ripple: 0 });
  const colors = useThemeColors();
  useBodyAction(bodyGroup);

  const coreMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        uniforms: {
          uColor: { value: colors.scene.clone() },
          uRippleStrength: { value: 0.0 },
          uRippleFreq: { value: 8.0 },
          uTime: { value: 0.0 },
          uOpacity: { value: 1.0 },
        },
        vertexShader: `
          uniform float uTime;
          uniform float uRippleStrength;
          uniform float uRippleFreq;
          void main() {
            float ripple = sin(uTime * uRippleFreq + position.x * 6.0)
                         * sin(uTime * uRippleFreq * 1.3 + position.y * 6.0);
            vec3 displaced = position + normal * ripple * uRippleStrength * 0.06;
            gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
          }
        `,
        fragmentShader: `
          uniform vec3 uColor;
          uniform float uOpacity;
          void main() {
            gl_FragColor = vec4(uColor, 0.95 * uOpacity);
          }
        `,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  const glowMat = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
        uniforms: {
          uColor: { value: colors.scene.clone() },
          uIntensity: { value: 1.0 },
          uOpacity: { value: 1.0 },
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
          uniform float uOpacity;
          varying vec3 vNormal;
          varying vec3 vViewDir;
          void main() {
            float fres = 1.0 - max(dot(vNormal, vViewDir), 0.0);
            float a = pow(fres, 2.2) * uIntensity;
            gl_FragColor = vec4(uColor, a * uOpacity);
          }
        `,
      }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // Palette melt on theme change.
  useEffect(() => {
    [coreMat, glowMat].forEach((m) => {
      gsap.to(m.uniforms.uColor.value, {
        r: colors.scene.r, g: colors.scene.g, b: colors.scene.b,
        duration: 0.6, ease: "power2.inOut",
      });
    });
  }, [colors, coreMat, glowMat]);

  useFrame((_, dt) => {
    const z = useZendaya.getState();
    const s = smoothed.current;

    const targetPulse = STATE_PULSE[z.ai] ?? 0;
    s.pulse += (targetPulse - s.pulse) * Math.min(1, dt * 3);

    const targetVoice = 1 + z.audioLevel * 0.15;
    s.voiceScale += (targetVoice - s.voiceScale) * Math.min(1, dt * 10);

    const visemeSum =
      z.visemes.aa + z.visemes.ih + z.visemes.ee + z.visemes.oh + z.visemes.ou;
    s.ripple += (Math.min(1, visemeSum) - s.ripple) * Math.min(1, dt * 8);
    coreMat.uniforms.uRippleStrength.value = s.ripple;
    coreMat.uniforms.uTime.value = performance.now() * 0.001;

    const t = performance.now() * 0.001;
    const breath = 1 + Math.sin(t * 1.2) * s.pulse;
    if (group.current) group.current.scale.setScalar(s.voiceScale * breath);

    glowMat.uniforms.uIntensity.value = 0.85 + s.pulse * 1.6;

    // Fade the solid orb out as the dissolve begins (gone by progress 0.55).
    const fade = 1 - THREE.MathUtils.smoothstep(progressRef.current.v, 0.0, 0.55);
    coreMat.uniforms.uOpacity.value = fade;
    glowMat.uniforms.uOpacity.value = fade;
    if (group.current) group.current.visible = fade > 0.001;
  });

  return (
    <group ref={group}>
      <group ref={bodyGroup}>
        <mesh scale={1.8}>
          <sphereGeometry args={[radius, 48, 48]} />
          <primitive object={glowMat} attach="material" />
        </mesh>
        <mesh>
          <sphereGeometry args={[radius * 0.55, 48, 48]} />
          <primitive object={coreMat} attach="material" />
        </mesh>
      </group>
    </group>
  );
}
