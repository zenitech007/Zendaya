// Deterministic value noise + sphere sampling for the point-cloud globe.
// valueNoise3 / landMask are a CPU port of the GLSL in the old MapModule.tsx,
// so continents bake into per-particle attributes (no texture asset needed).

function fract(x: number): number {
  return x - Math.floor(x);
}
function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}
function hash(x: number, y: number, z: number): number {
  // GLSL: p = fract(p*0.3183099 + vec3(0.1,0.2,0.3)); p *= 17; fract(px*py*pz*(px+py+pz))
  let px = fract(x * 0.3183099 + 0.1);
  let py = fract(y * 0.3183099 + 0.2);
  let pz = fract(z * 0.3183099 + 0.3);
  px *= 17.0;
  py *= 17.0;
  pz *= 17.0;
  return fract(px * py * pz * (px + py + pz));
}

/** Trilinear value noise in [0,1]. */
export function valueNoise3(x: number, y: number, z: number): number {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const iz = Math.floor(z);
  let fx = fract(x);
  let fy = fract(y);
  let fz = fract(z);
  fx = fx * fx * (3.0 - 2.0 * fx);
  fy = fy * fy * (3.0 - 2.0 * fy);
  fz = fz * fz * (3.0 - 2.0 * fz);
  const c000 = hash(ix, iy, iz);
  const c100 = hash(ix + 1, iy, iz);
  const c010 = hash(ix, iy + 1, iz);
  const c110 = hash(ix + 1, iy + 1, iz);
  const c001 = hash(ix, iy, iz + 1);
  const c101 = hash(ix + 1, iy, iz + 1);
  const c011 = hash(ix, iy + 1, iz + 1);
  const c111 = hash(ix + 1, iy + 1, iz + 1);
  return lerp(
    lerp(lerp(c000, c100, fx), lerp(c010, c110, fx), fy),
    lerp(lerp(c001, c101, fx), lerp(c011, c111, fx), fy),
    fz
  );
}

/**
 * Fractal land mask in [0,1] for a point on (or near) the unit sphere.
 * Same octave recipe as the old globe shader; normalized by the max
 * possible amplitude (0.5 + 0.25 + 0.125 = 0.875).
 */
export function landMask(x: number, y: number, z: number): number {
  const px = x * 2.5;
  const py = y * 2.5;
  const pz = z * 2.5;
  let n = 0.0;
  n += valueNoise3(px, py, pz) * 0.5;
  n += valueNoise3(px * 2.0, py * 2.0, pz * 2.0) * 0.25;
  n += valueNoise3(px * 4.0, py * 4.0, pz * 4.0) * 0.125;
  return Math.min(1, Math.max(0, n / 0.875));
}

/** Evenly distributed points on a sphere via the Fibonacci spiral. */
export function fibonacciSphere(count: number, radius: number): Float32Array {
  const out = new Float32Array(count * 3);
  const golden = Math.PI * (3.0 - Math.sqrt(5.0)); // ~2.39996
  for (let i = 0; i < count; i++) {
    const yy = 1 - (i / (count - 1)) * 2; // 1 .. -1
    const r = Math.sqrt(Math.max(0, 1 - yy * yy));
    const theta = golden * i;
    out[i * 3 + 0] = Math.cos(theta) * r * radius;
    out[i * 3 + 1] = yy * radius;
    out[i * 3 + 2] = Math.sin(theta) * r * radius;
  }
  return out;
}

export interface GlobePoints {
  positions: Float32Array; // length count*3
  landness: Float32Array; // length count, each in [0,1]
}

/** Globe positions + per-point landness sampled on the unit-sphere direction. */
export function buildGlobePoints(count: number, radius: number): GlobePoints {
  const positions = fibonacciSphere(count, radius);
  const landness = new Float32Array(count);
  for (let i = 0; i < count; i++) {
    const x = positions[i * 3 + 0] / radius;
    const y = positions[i * 3 + 1] / radius;
    const z = positions[i * 3 + 2] / radius;
    landness[i] = landMask(x, y, z);
  }
  return { positions, landness };
}
