import { useEffect, useMemo } from "react";
import { useFrame } from "@react-three/fiber";
import gsap from "gsap";
import * as THREE from "three";
import { fibonacciSphere, buildGlobePoints } from "./pointcloud";
import { useThemeColors } from "../themes/useThemeColors";

export interface DissolveFieldProps {
  progressRef: React.MutableRefObject<{ v: number }>;
  count?: number;
  orbRadius?: number;
  globeRadius?: number;
  /** Override target positions (e.g. a weather form). Length must be count*3. */
  targetPositions?: Float32Array;
  /** Plain mode: skip land/ocean coloring; tint orb→accent by progress. */
  plain?: boolean;
}

/**
 * Continuous particle field. Each particle interpolates from an orb-shell
 * position (progress 0) to a globe position (progress 1), bowing outward and
 * swirling at mid-transition. Continents come from baked per-particle landness.
 * Particles fade in by progress 0.18 so the solid IdleOrbScene owns the rest state.
 */
export default function DissolveField({
  progressRef,
  count = 9000,
  orbRadius = 0.62,
  globeRadius = 1.5,
  targetPositions,
  plain = false,
}: DissolveFieldProps) {
  const colors = useThemeColors();

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const orb = fibonacciSphere(count, orbRadius);
    const { positions: globe, landness } = buildGlobePoints(count, globeRadius);
    const target = targetPositions ?? globe;
    const seed = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) seed[i] = Math.random();
    // `position` is required by three for bounds; the real position is computed
    // in the vertex shader from aOrbPos/aGlobePos.
    g.setAttribute("position", new THREE.BufferAttribute(orb.slice(), 3));
    g.setAttribute("aOrbPos", new THREE.BufferAttribute(orb, 3));
    g.setAttribute("aGlobePos", new THREE.BufferAttribute(target, 3));
    g.setAttribute("aLandness", new THREE.BufferAttribute(landness, 1));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 3));
    return g;
  }, [count, orbRadius, globeRadius, targetPositions]);

  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
        uniforms: {
          uProgress: { value: 0 },
          uTime: { value: 0 },
          uSize: { value: 30.0 },
          uOpacity: { value: 1.0 },
          uColorOrb: { value: colors.scene.clone() },
          uColorLand: { value: colors.accent.clone() },
          uColorOcean: { value: colors.scene.clone() },
          uPlain: { value: plain ? 1 : 0 },
          uColorPlain: { value: colors.accent.clone() },
        },
        vertexShader: `
          uniform float uProgress;
          uniform float uSize;
          attribute vec3 aOrbPos;
          attribute vec3 aGlobePos;
          attribute float aLandness;
          attribute vec3 aSeed;
          varying float vLandness;

          void main() {
            vLandness = aLandness;
            // 0 -> 1 -> 0 bow: zero at both ends, peaks mid-transition.
            float bow = sin(uProgress * 3.14159265);

            vec3 pos = mix(aOrbPos, aGlobePos, uProgress);
            // scatter outward along a per-particle random direction
            vec3 dir = normalize(aSeed * 2.0 - 1.0);
            pos += dir * bow * 1.4;
            // swirl around Y while scattered
            float ang = bow * 2.2 + aSeed.x * 6.2831853;
            float s = sin(ang), c = cos(ang);
            pos.xz = mat2(c, -s, s, c) * pos.xz;

            vec4 mv = modelViewMatrix * vec4(pos, 1.0);
            gl_Position = projectionMatrix * mv;
            gl_PointSize = uSize * (1.0 + bow * 0.6) / -mv.z;
          }
        `,
        fragmentShader: `
          uniform float uOpacity;
          uniform float uProgress;
          uniform vec3 uColorOrb;
          uniform vec3 uColorLand;
          uniform vec3 uColorOcean;
          uniform float uPlain;
          uniform vec3 uColorPlain;
          varying float vLandness;

          void main() {
            // round, soft sprite
            float r = length(gl_PointCoord - vec2(0.5));
            if (r > 0.5) discard;
            float alpha = smoothstep(0.5, 0.1, r);

            float land = step(0.55, vLandness);
            vec3 globeCol = mix(uColorOcean * 0.4, uColorLand, land);
            // dim ocean particles once settled so continents read
            float oceanFade = mix(1.0, 0.25, (1.0 - land) * uProgress);
            vec3 colGlobe = mix(uColorOrb, globeCol, uProgress);

            // plain (weather) coloring: orb -> theme accent, brightness from noise
            vec3 colPlain = mix(uColorOrb, uColorPlain, uProgress);
            colPlain *= (0.7 + 0.6 * vLandness);

            vec3 col = mix(colGlobe, colPlain, uPlain);
            float fade = mix(oceanFade, 1.0, uPlain);

            // fade particles in by progress 0.18 (solid orb owns the rest state)
            float born = smoothstep(0.0, 0.18, uProgress);

            gl_FragColor = vec4(col, alpha * uOpacity * fade * born);
          }
        `,
      }),
    // initial uniform colors are captured on mount; theme changes melt via the effect below
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // Palette melt: tween color uniforms when the active theme changes.
  useEffect(() => {
    const u = material.uniforms;
    gsap.to(u.uColorOrb.value, {
      r: colors.scene.r, g: colors.scene.g, b: colors.scene.b,
      duration: 0.6, ease: "power2.inOut",
    });
    gsap.to(u.uColorLand.value, {
      r: colors.accent.r, g: colors.accent.g, b: colors.accent.b,
      duration: 0.6, ease: "power2.inOut",
    });
    gsap.to(u.uColorOcean.value, {
      r: colors.scene.r, g: colors.scene.g, b: colors.scene.b,
      duration: 0.6, ease: "power2.inOut",
    });
    gsap.to(u.uColorPlain.value, {
      r: colors.accent.r, g: colors.accent.g, b: colors.accent.b,
      duration: 0.6, ease: "power2.inOut",
    });
  }, [colors, material]);

  useFrame((_, dt) => {
    material.uniforms.uProgress.value = progressRef.current.v;
    material.uniforms.uTime.value += dt;
  });

  return <points geometry={geometry} material={material} frustumCulled={false} />;
}
