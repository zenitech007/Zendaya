import * as THREE from "three";

// Holographic projection material: animated scan-lines + fresnel edge +
// subtle vertical scroll. Use for the map sphere atmosphere and any
// "projected" panel surface. Plug uTime via useFrame.
export const hologramVertex = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying vec2 vUv;
  varying vec3 vPos;
  void main() {
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vViewDir = normalize(cameraPosition - wp.xyz);
    vUv = uv;
    vPos = position;
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

export const hologramFragment = /* glsl */ `
  varying vec3 vNormalW;
  varying vec3 vViewDir;
  varying vec2 vUv;
  varying vec3 vPos;
  uniform vec3 uColor;
  uniform float uTime;
  uniform float uIntensity;
  uniform float uScanFreq;

  // Hash for noise dithering.
  float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

  void main() {
    float rim = 1.0 - max(dot(vNormalW, vViewDir), 0.0);
    rim = pow(clamp(rim, 0.0, 1.0), 1.6);

    // Scan-line: bright bands sweep up.
    float scan = sin((vPos.y - uTime * 0.5) * uScanFreq) * 0.5 + 0.5;
    scan = pow(scan, 8.0);

    // Dither / interference shimmer.
    float n = hash(vUv * 800.0 + uTime * 5.0);

    float a = (rim * 0.7 + scan * 0.35 + n * 0.05) * uIntensity;
    gl_FragColor = vec4(uColor, clamp(a, 0.0, 1.0));
  }
`;

export interface HologramOptions {
  color?: THREE.ColorRepresentation;
  intensity?: number;
  scanFreq?: number;
}

export function makeHologramMaterial(opts: HologramOptions = {}): THREE.ShaderMaterial {
  const { color = "#5cf2ff", intensity = 0.9, scanFreq = 40 } = opts;
  return new THREE.ShaderMaterial({
    vertexShader: hologramVertex,
    fragmentShader: hologramFragment,
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uTime: { value: 0 },
      uIntensity: { value: intensity },
      uScanFreq: { value: scanFreq },
    },
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.DoubleSide,
  });
}
