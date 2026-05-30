import * as THREE from "three";
// Soft circular GPU particle. Size attenuates with distance; alpha falls
// off radially so points read as glowing dots, not squares. Additive
// blending stacks them into halo-like clouds around the orb.
export const particleVertex = /* glsl */ `
  attribute float aSize;
  attribute vec3 aColor;
  varying vec3 vColor;
  uniform float uPixelRatio;
  uniform float uSize;
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aSize * uSize * uPixelRatio * (1.0 / -mv.z);
    vColor = aColor;
  }
`;
export const particleFragment = /* glsl */ `
  varying vec3 vColor;
  uniform float uOpacity;
  void main() {
    vec2 c = gl_PointCoord - vec2(0.5);
    float d = length(c);
    float a = smoothstep(0.5, 0.0, d);
    if (a < 0.01) discard;
    gl_FragColor = vec4(vColor, a * uOpacity);
  }
`;
export function makeParticleMaterial(opts = {}) {
    const { size = 90, opacity = 0.75, pixelRatio = 1 } = opts;
    return new THREE.ShaderMaterial({
        vertexShader: particleVertex,
        fragmentShader: particleFragment,
        uniforms: {
            uSize: { value: size },
            uOpacity: { value: opacity },
            uPixelRatio: { value: pixelRatio },
        },
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
    });
}
