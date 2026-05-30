import * as THREE from "three";

// Fresnel rim-glow for the orb halo. Brighter at glancing angles, fades
// toward the camera-facing center. Additive blending, no depth write so
// it layers behind bloom without z-fighting.
export const glowVertex = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  void main() {
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - wp.xyz);
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

export const glowFragment = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  uniform vec3 uColor;
  uniform float uIntensity;
  uniform float uPower;
  void main() {
    float rim = 1.0 - max(dot(vNormalW, vViewDir), 0.0);
    rim = pow(clamp(rim, 0.0, 1.0), uPower);
    gl_FragColor = vec4(uColor * rim * uIntensity, rim * uIntensity);
  }
`;

export interface GlowOptions {
  color?: THREE.ColorRepresentation;
  intensity?: number;
  power?: number;
}

export function makeGlowMaterial(opts: GlowOptions = {}): THREE.ShaderMaterial {
  const { color = "#7a5cff", intensity = 1.0, power = 2.5 } = opts;
  return new THREE.ShaderMaterial({
    vertexShader: glowVertex,
    fragmentShader: glowFragment,
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uIntensity: { value: intensity },
      uPower: { value: power },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
  });
}
