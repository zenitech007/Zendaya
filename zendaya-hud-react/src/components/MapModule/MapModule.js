import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
// Procedural globe — no external texture (avoids CSP / load latency).
// Earth-like noise pattern in fragment shader.
export default function MapModule() {
    const meshRef = useRef(null);
    const material = useMemo(() => {
        return new THREE.ShaderMaterial({
            transparent: true,
            uniforms: {
                uTime: { value: 0 },
                uBlur: { value: 20.0 },
                uOpacity: { value: 0.0 }, // controlled manually or by fadeSubtree
                uColorA: { value: new THREE.Color("#0a2540") },
                uColorB: { value: new THREE.Color("#1ec8ff") },
                uColorC: { value: new THREE.Color("#7a5cff") },
            },
            vertexShader: `
        varying vec3 vNormal;
        varying vec3 vPos;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPos = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
            fragmentShader: `
        varying vec3 vNormal;
        varying vec3 vPos;
        uniform float uTime;
        uniform vec3 uColorA;
        uniform vec3 uColorB;
        uniform vec3 uColorC;

        uniform float uOpacity;
        uniform float uBlur;

        float hash(vec3 p) {
          p = fract(p * 0.3183099 + vec3(0.1, 0.2, 0.3));
          p *= 17.0;
          return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
        }
        float noise(vec3 p) {
          vec3 i = floor(p);
          vec3 f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          float n = mix(
            mix(mix(hash(i), hash(i + vec3(1,0,0)), f.x),
                mix(hash(i + vec3(0,1,0)), hash(i + vec3(1,1,0)), f.x), f.y),
            mix(mix(hash(i + vec3(0,0,1)), hash(i + vec3(1,0,1)), f.x),
                mix(hash(i + vec3(0,1,1)), hash(i + vec3(1,1,1)), f.x), f.y),
            f.z
          );
          return n;
        }

        void main() {
          float n = 0.0;
          vec3 p = vPos * 2.5;
          n += noise(p) * 0.5;
          n += noise(p * 2.0) * 0.25;
          n += noise(p * 4.0) * 0.125;
          
          // Use uBlur to soften the edge of the landmass
          float edgeSoftness = mix(0.1, 0.6, clamp(uBlur / 20.0, 0.0, 1.0));
          float land = smoothstep(0.5 - edgeSoftness, 0.5 + edgeSoftness, n);
          
          vec3 col = mix(uColorA, uColorB, land);
          // Atmosphere highlight on edges.
          vec3 viewDir = normalize(cameraPosition - vPos);
          float fres = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 2.5);
          col = mix(col, uColorC, fres * 0.6);
          gl_FragColor = vec4(col, opacity); // opacity is injected by ThreeJS ShaderMaterial when transparent=true
        }
      `,
        });
    }, []);
    useFrame((_, dt) => {
        if (meshRef.current)
            meshRef.current.rotation.y += dt * 0.08;
        material.uniforms.uTime.value += dt;
    });
    return (_jsxs("mesh", { ref: meshRef, children: [_jsx("sphereGeometry", { args: [1.4, 64, 64] }), _jsx("primitive", { object: material, attach: "material" })] }));
}
