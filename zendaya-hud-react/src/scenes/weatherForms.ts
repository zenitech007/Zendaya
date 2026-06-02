import { fibonacciSphere, valueNoise3 } from "./pointcloud";

export type WeatherForm = "clear" | "clouds" | "rain" | "snow" | "storm" | "fog";

/** Map an Open-Meteo WMO weather_code to a particle form. */
export function wmoToForm(code: number): WeatherForm {
  if (code === 0 || code === 1) return "clear";
  if (code === 2 || code === 3) return "clouds";
  if (code === 45 || code === 48) return "fog";
  if ([71, 73, 75, 77, 85, 86].includes(code)) return "snow";
  if ([95, 96, 99].includes(code)) return "storm";
  if ((code >= 51 && code <= 67) || (code >= 80 && code <= 82)) return "rain";
  return "clouds";
}

// Per-form noise frequency / displacement / vertical flatten. These shape the
// point cloud only; particle color comes from the theme in DissolveField.
const CFG: Record<WeatherForm, { freq: number; amp: number; flatten: number }> = {
  clear: { freq: 1.2, amp: 0.05, flatten: 0.0 },
  clouds: { freq: 2.0, amp: 0.35, flatten: 0.0 },
  rain: { freq: 3.0, amp: 0.18, flatten: 0.55 },
  snow: { freq: 2.4, amp: 0.3, flatten: 0.0 },
  storm: { freq: 3.4, amp: 0.5, flatten: 0.2 },
  fog: { freq: 1.6, amp: 0.12, flatten: 0.7 },
};

/**
 * Generate a deterministic point cloud (length = count*3) for a weather form by
 * displacing a Fibonacci sphere with form-specific value noise. No texture asset.
 */
export function buildFormPoints(form: WeatherForm, count: number, radius = 1.4): Float32Array {
  const base = fibonacciSphere(count, radius);
  const positions = new Float32Array(count * 3);
  const { freq, amp, flatten } = CFG[form];
  for (let i = 0; i < count; i++) {
    let x = base[i * 3 + 0];
    let y = base[i * 3 + 1];
    let z = base[i * 3 + 2];
    const nx = x / radius;
    const ny = y / radius;
    const nz = z / radius;
    const n = valueNoise3(nx * freq + 11.3, ny * freq + 4.7, nz * freq + 19.1);
    const disp = 1 + (n - 0.5) * 2 * amp;
    x *= disp;
    y *= disp;
    z *= disp;
    y *= 1 - flatten; // squash toward an equatorial disc for layered forms
    positions[i * 3 + 0] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
  }
  return positions;
}
