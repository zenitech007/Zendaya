# HUD Hologram Redesign — Phase B: 3D Scene Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single hardcoded orange orb + buggy shader-globe with a themed, continuous particle field that performs a cinematic "scatter & reform" dissolve from a resting orb into a holographic point-cloud globe whenever a "show me the map" intent fires.

**Architecture:** One `SceneManager` owns a shared `progressRef` (a plain `{ v: number }` mutable ref, GSAP-tweened 0↔1 over 1.2s). At rest (`progress≈0`) a solid mesh orb (`IdleOrbScene`, ported from the current `Orb` with all pulse/voice/viseme/body-action personality) is visible. As `progress` rises, the orb fades out while a GPU particle system (`DissolveField`) fades in, scatters outward (a `sin(progress·π)` "bow"), swirls, then locks into a Fibonacci-sphere globe whose continents are masked by a ported value-noise function (`GlobeScene` spins it). All colors come from the active theme via a new `useThemeColors()` hook and GSAP-melt between palettes on theme change. A DOM `Atmosphere` layer makes the per-theme `--zen-grain` token visible as filmic scanlines. No store, backend, or routing changes — Phase B consumes signals (`scene`, `activeModule`, `docked`, `dockCorner`, `activeThemeId`) that already exist.

**Tech Stack:** React 18 + TypeScript, Three.js 0.169 via @react-three/fiber 8, @react-three/postprocessing (Bloom), GSAP 3, Zustand 4 (read-only here), Vitest 2.1.9 + happy-dom + @testing-library/react 16.

---

## Working Constraints (read before every task)

These are hard security/scope rules for this repo. They override convenience:

- **Leave the pre-existing uncommitted diff alone.** There is unrelated work in the working tree the user explicitly opted not to touch.
- **Never** run `git add -A`, `git add .`, or `git add -u`. Stage **only** the exact files named in each task's commit step, by path.
- **Never** touch, stage, or commit any of these protected paths: `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`.
- **All commits must disable signing:** use `git -c commit.gpgsign=false commit ...`.
- After every commit, run `git status` and confirm none of the protected paths were swept in.
- This entire phase lives under `zendaya-hud-react/src/`. Do not modify backend, Python, or config files.
- Run all `npm` commands from `C:\Users\IKA\Zendaya\zendaya-hud-react`.

## What this phase does NOT change

- **No store changes.** `scene`, `activeModule`, `docked`, `dockCorner`, `activeThemeId` already exist and already route correctly. Do not edit `src/store/zendayaStore.ts`.
- **No backend / websocket changes.** The `set_theme` action and scene routing already land in the store.
- **`src/animations/` (timelines.ts, transitions.ts, easing.ts) becomes dead** once `MainScene` is removed in Task 7. Leave it in place — it is harmless (unused exports do not fail `tsc`) and gets pruned in Phase C. Do not delete it in this phase.

## File Structure

Created in this phase (all under `zendaya-hud-react/src/`):

| File | Responsibility |
|------|----------------|
| `themes/useThemeColors.ts` | Hook → `{ scene, primary, accent: THREE.Color; bloom: number }` for the active theme; memoized, forge fallback. |
| `scenes/pointcloud.ts` | Pure math: `fibonacciSphere`, ported `valueNoise3` + `landMask`, `buildGlobePoints`. No React, no THREE objects beyond `Float32Array`. |
| `scenes/DissolveField.tsx` | The `<points>` particle system + morph shader (orb shell ↔ globe). Palette-melts on theme change. |
| `scenes/IdleOrbScene.tsx` | Port of `Orb.tsx`: solid mesh orb, themed, with an opacity fade driven by `progressRef`. |
| `scenes/GlobeScene.tsx` | Wraps `DissolveField` in a slowly-spinning group (spin scaled by progress). |
| `scenes/SceneManager.tsx` | Owns `progressRef`, GSAP-tweens it on scene change, corner-docks the stage for utility modules, mounts `IdleOrbScene` + `GlobeScene`. Exports pure `selectScene`. |
| `components/Atmosphere/Atmosphere.tsx` | Decorative full-viewport DOM layer that consumes `--zen-grain`. |

Modified:

| File | Change |
|------|--------|
| `App.tsx` | Swap `<MainScene/>` → `<SceneManager/>`, mount `<Atmosphere/>`, theme-scale Bloom intensity. |
| `index.css` | Append `.zen-atmosphere` rules. |

Removed (Task 7, after confirming no importers): `scenes/MainScene.tsx`, `components/Orb/Orb.tsx`, `components/MapModule/MapModule.tsx`.

Test files: `src/__tests__/useThemeColors.test.ts`, `src/__tests__/pointcloud.test.ts`, `src/__tests__/sceneManager.test.ts`, `src/__tests__/Atmosphere.test.tsx`.

---

### Task 1: `useThemeColors` hook

**Files:**
- Create: `zendaya-hud-react/src/themes/useThemeColors.ts`
- Test: `zendaya-hud-react/src/__tests__/useThemeColors.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/useThemeColors.test.ts`:

```ts
import { describe, it, expect, beforeEach } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { useThemeColors } from "../themes/useThemeColors";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => useZendaya.setState({ activeThemeId: "forge" }));

describe("useThemeColors", () => {
  it("returns the forge scene color and bloom by default", () => {
    const { result } = renderHook(() => useThemeColors());
    expect(result.current.scene.getHexString()).toBe("ff8a3c");
    expect(result.current.bloom).toBe(1.3);
  });

  it("tracks a theme change to iris", () => {
    const { result } = renderHook(() => useThemeColors());
    act(() => useZendaya.setState({ activeThemeId: "iris" }));
    expect(result.current.scene.getHexString()).toBe("2fd6ff");
    expect(result.current.bloom).toBe(1.1);
  });

  it("falls back to forge for an unknown theme id", () => {
    useZendaya.setState({ activeThemeId: "nope" });
    const { result } = renderHook(() => useThemeColors());
    expect(result.current.scene.getHexString()).toBe("ff8a3c");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- useThemeColors`
Expected: FAIL — `Cannot find module '../themes/useThemeColors'`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/themes/useThemeColors.ts`:

```ts
import { useMemo } from "react";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";
import { THEMES } from "./registry";

export interface ThemeColors {
  scene: THREE.Color;
  primary: THREE.Color;
  accent: THREE.Color;
  bloom: number;
}

/**
 * Active-theme colors as THREE.Color objects for 3D materials.
 * Memoized on activeThemeId; unknown ids fall back to Forge.
 */
export function useThemeColors(): ThemeColors {
  const id = useZendaya((s) => s.activeThemeId);
  return useMemo(() => {
    const t = THEMES[id] ?? THEMES.forge;
    return {
      scene: new THREE.Color(t.sceneColor),
      primary: new THREE.Color(t.primary),
      accent: new THREE.Color(t.accent),
      bloom: t.bloom,
    };
  }, [id]);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- useThemeColors`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/themes/useThemeColors.ts src/__tests__/useThemeColors.test.ts
git -c commit.gpgsign=false commit -m "feat: add useThemeColors hook for themed 3D materials"
git status
```

Confirm no protected paths were staged.

---

### Task 2: Point-cloud geometry math

**Files:**
- Create: `zendaya-hud-react/src/scenes/pointcloud.ts`
- Test: `zendaya-hud-react/src/__tests__/pointcloud.test.ts`

This ports the GLSL value-noise from the old `MapModule.tsx` fragment shader to CPU TypeScript so continents can be baked into per-particle attributes. Pure functions — fully unit-testable.

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/pointcloud.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import {
  fibonacciSphere,
  valueNoise3,
  landMask,
  buildGlobePoints,
} from "../scenes/pointcloud";

describe("pointcloud", () => {
  it("fibonacciSphere returns count*3 floats all on the given radius", () => {
    const pts = fibonacciSphere(500, 1.5);
    expect(pts.length).toBe(1500);
    for (let i = 0; i < 500; i++) {
      const r = Math.hypot(pts[i * 3], pts[i * 3 + 1], pts[i * 3 + 2]);
      expect(r).toBeGreaterThan(1.49);
      expect(r).toBeLessThan(1.51);
    }
  });

  it("valueNoise3 is deterministic and within [0,1]", () => {
    const a = valueNoise3(1.2, 3.4, 5.6);
    const b = valueNoise3(1.2, 3.4, 5.6);
    expect(a).toBe(b);
    expect(a).toBeGreaterThanOrEqual(0);
    expect(a).toBeLessThanOrEqual(1);
  });

  it("landMask is normalized to [0,1]", () => {
    for (let i = 0; i < 50; i++) {
      const v = landMask(Math.sin(i), Math.cos(i * 1.3), Math.sin(i * 0.7));
      expect(v).toBeGreaterThanOrEqual(0);
      expect(v).toBeLessThanOrEqual(1);
    }
  });

  it("buildGlobePoints returns matching positions and landness lengths", () => {
    const { positions, landness } = buildGlobePoints(1000, 1.5);
    expect(positions.length).toBe(3000);
    expect(landness.length).toBe(1000);
    for (let i = 0; i < 1000; i++) {
      expect(landness[i]).toBeGreaterThanOrEqual(0);
      expect(landness[i]).toBeLessThanOrEqual(1);
    }
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- pointcloud`
Expected: FAIL — `Cannot find module '../scenes/pointcloud'`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/scenes/pointcloud.ts`:

```ts
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- pointcloud`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/scenes/pointcloud.ts src/__tests__/pointcloud.test.ts
git -c commit.gpgsign=false commit -m "feat: add point-cloud sphere + ported land-mask noise"
git status
```

---

### Task 3: `DissolveField` particle system

**Files:**
- Create: `zendaya-hud-react/src/scenes/DissolveField.tsx`
- Verify: `npx tsc --noEmit` (no unit test — WebGL shaders can't run under happy-dom; correctness is verified by `tsc` here and the manual checklist in Task 8)

- [ ] **Step 1: Write the component**

Create `zendaya-hud-react/src/scenes/DissolveField.tsx`:

```tsx
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
}: DissolveFieldProps) {
  const colors = useThemeColors();

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const orb = fibonacciSphere(count, orbRadius);
    const { positions: globe, landness } = buildGlobePoints(count, globeRadius);
    const seed = new Float32Array(count * 3);
    for (let i = 0; i < count * 3; i++) seed[i] = Math.random();
    // `position` is required by three for bounds; the real position is computed
    // in the vertex shader from aOrbPos/aGlobePos.
    g.setAttribute("position", new THREE.BufferAttribute(orb.slice(), 3));
    g.setAttribute("aOrbPos", new THREE.BufferAttribute(orb, 3));
    g.setAttribute("aGlobePos", new THREE.BufferAttribute(globe, 3));
    g.setAttribute("aLandness", new THREE.BufferAttribute(landness, 1));
    g.setAttribute("aSeed", new THREE.BufferAttribute(seed, 3));
    return g;
  }, [count, orbRadius, globeRadius]);

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
            vec3 col = mix(uColorOrb, globeCol, uProgress);

            // fade particles in by progress 0.18 (solid orb owns the rest state)
            float born = smoothstep(0.0, 0.18, uProgress);

            gl_FragColor = vec4(col, alpha * uOpacity * oceanFade * born);
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
  }, [colors, material]);

  useFrame((_, dt) => {
    material.uniforms.uProgress.value = progressRef.current.v;
    material.uniforms.uTime.value += dt;
  });

  return <points geometry={geometry} material={material} frustumCulled={false} />;
}
```

- [ ] **Step 2: Type-check**

Run: `npx tsc --noEmit`
Expected: PASS (no errors). If `React.MutableRefObject` is flagged as needing an import, it is a global type from `@types/react` and resolves without an explicit import — confirm `tsc` is clean.

- [ ] **Step 3: Commit**

```bash
git add src/scenes/DissolveField.tsx
git -c commit.gpgsign=false commit -m "feat: add DissolveField orb-to-globe particle system"
git status
```

---

### Task 4: `IdleOrbScene` (themed mesh orb with fade)

**Files:**
- Create: `zendaya-hud-react/src/scenes/IdleOrbScene.tsx`
- Verify: `npx tsc --noEmit`

This is a faithful port of `components/Orb/Orb.tsx` (keep pulse/voice/viseme-ripple/breath + `useBodyAction`) with two changes: color comes from `useThemeColors` (GSAP-melt on theme change), and a `uOpacity` uniform fades the orb out as `progressRef.v` rises past 0.55 (handing off to the particles).

- [ ] **Step 1: Write the component**

Create `zendaya-hud-react/src/scenes/IdleOrbScene.tsx`:

```tsx
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
```

- [ ] **Step 2: Type-check**

Run: `npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add src/scenes/IdleOrbScene.tsx
git -c commit.gpgsign=false commit -m "feat: add themed IdleOrbScene with dissolve fade"
git status
```

---

### Task 5: `SceneManager` + `GlobeScene`

**Files:**
- Create: `zendaya-hud-react/src/scenes/GlobeScene.tsx`
- Create: `zendaya-hud-react/src/scenes/SceneManager.tsx`
- Test: `zendaya-hud-react/src/__tests__/sceneManager.test.ts` (tests the pure `selectScene` export)

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/sceneManager.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { selectScene } from "../scenes/SceneManager";

describe("selectScene", () => {
  it("returns idle for the default scene", () => {
    expect(selectScene({ scene: "main", activeModule: "none" })).toBe("idle");
  });
  it("returns globe when the scene is map", () => {
    expect(selectScene({ scene: "map", activeModule: "none" })).toBe("globe");
  });
  it("returns globe when the map module is active", () => {
    expect(selectScene({ scene: "main", activeModule: "map" })).toBe("globe");
  });
  it("returns idle for a non-map module", () => {
    expect(selectScene({ scene: "main", activeModule: "calculator" })).toBe("idle");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- sceneManager`
Expected: FAIL — `Cannot find module '../scenes/SceneManager'`.

- [ ] **Step 3: Write `GlobeScene`**

Create `zendaya-hud-react/src/scenes/GlobeScene.tsx`:

```tsx
import { useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import DissolveField from "./DissolveField";

export interface GlobeSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
}

/** The point-cloud globe: spins only once the field has reformed (spin ∝ progress). */
export default function GlobeScene({ progressRef }: GlobeSceneProps) {
  const spin = useRef<THREE.Group>(null!);
  useFrame((_, dt) => {
    if (spin.current) spin.current.rotation.y += dt * 0.12 * progressRef.current.v;
  });
  return (
    <group ref={spin}>
      <DissolveField progressRef={progressRef} />
    </group>
  );
}
```

- [ ] **Step 4: Write `SceneManager`**

Create `zendaya-hud-react/src/scenes/SceneManager.tsx`:

```tsx
import { useEffect, useRef } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";
import IdleOrbScene from "./IdleOrbScene";
import GlobeScene from "./GlobeScene";

/** Pure routing: which scene should be shown for the given store signals. */
export function selectScene(s: { scene: string; activeModule: string }): "idle" | "globe" {
  return s.scene === "map" || s.activeModule === "map" ? "globe" : "idle";
}

/**
 * Owns the shared orb->globe morph progress (0 idle … 1 globe), GSAP-tweened on
 * scene change, and corner-docks the whole stage for utility (non-map) modules.
 */
export default function SceneManager() {
  const stage = useRef<THREE.Group>(null!);
  const progressRef = useRef({ v: 0 });

  const scene = useZendaya((s) => s.scene);
  const activeModule = useZendaya((s) => s.activeModule);
  const docked = useZendaya((s) => s.docked);
  const dockCorner = useZendaya((s) => s.dockCorner);

  const target = selectScene({ scene, activeModule });

  // Drive the morph progress.
  useEffect(() => {
    const tween = gsap.to(progressRef.current, {
      v: target === "globe" ? 1 : 0,
      duration: 1.2,
      ease: "power3.inOut",
    });
    return () => {
      tween.kill();
    };
  }, [target]);

  // Corner-dock the stage for docked utility modules (never for the globe).
  useEffect(() => {
    const g = stage.current;
    if (!g) return;
    const dockToCorner = docked && target !== "globe";
    const dockX = dockCorner === "bl" ? -2.8 : 2.8;
    const posTween = gsap.to(g.position, {
      x: dockToCorner ? dockX : 0,
      y: dockToCorner ? -1.6 : 0,
      z: 0,
      duration: 0.8,
      ease: "power3.inOut",
    });
    const scaleTween = gsap.to(g.scale, {
      x: dockToCorner ? 0.35 : 1,
      y: dockToCorner ? 0.35 : 1,
      z: dockToCorner ? 0.35 : 1,
      duration: 0.8,
      ease: "power3.inOut",
    });
    return () => {
      posTween.kill();
      scaleTween.kill();
    };
  }, [docked, dockCorner, target]);

  return (
    <>
      <ambientLight intensity={0.7} />
      <group ref={stage}>
        <IdleOrbScene progressRef={progressRef} />
        <GlobeScene progressRef={progressRef} />
      </group>
    </>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npm test -- sceneManager`
Expected: PASS (4 tests). (Importing `SceneManager` pulls in @react-three/fiber, GSAP, three, and the child components, but none execute WebGL at module-eval time, so the import is safe under happy-dom.)

- [ ] **Step 6: Type-check**

Run: `npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/scenes/GlobeScene.tsx src/scenes/SceneManager.tsx src/__tests__/sceneManager.test.ts
git -c commit.gpgsign=false commit -m "feat: add SceneManager + GlobeScene with progress-driven morph"
git status
```

---

### Task 6: `Atmosphere` layer (makes `--zen-grain` live)

**Files:**
- Create: `zendaya-hud-react/src/components/Atmosphere/Atmosphere.tsx`
- Modify: `zendaya-hud-react/src/index.css` (append at end of file)
- Test: `zendaya-hud-react/src/__tests__/Atmosphere.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/Atmosphere.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import Atmosphere from "../components/Atmosphere/Atmosphere";

describe("Atmosphere", () => {
  it("renders a decorative full-viewport grain layer", () => {
    const { getByTestId } = render(<Atmosphere />);
    const el = getByTestId("atmosphere");
    expect(el.className).toContain("zen-atmosphere");
    expect(el.getAttribute("aria-hidden")).toBe("true");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm test -- Atmosphere`
Expected: FAIL — `Cannot find module '../components/Atmosphere/Atmosphere'`.

- [ ] **Step 3: Write the component**

Create `zendaya-hud-react/src/components/Atmosphere/Atmosphere.tsx`:

```tsx
/**
 * Filmic grain + scanline overlay. Opacity is driven by the active theme's
 * --zen-grain CSS variable, so each theme gets a different amount of texture.
 * Purely decorative: pointer-events:none, aria-hidden.
 */
export default function Atmosphere() {
  return <div className="zen-atmosphere" aria-hidden data-testid="atmosphere" />;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm test -- Atmosphere`
Expected: PASS (1 test).

- [ ] **Step 5: Append the CSS**

Append to the end of `zendaya-hud-react/src/index.css`:

```css
/* ---------- Atmosphere — theme-driven grain + scanlines ---------- */
.zen-atmosphere {
  position: absolute;
  inset: 0;
  z-index: 50;
  pointer-events: none;
  opacity: var(--zen-grain);
  mix-blend-mode: overlay;
  background-image: repeating-linear-gradient(
    0deg,
    rgba(255, 255, 255, 0.05) 0px,
    rgba(255, 255, 255, 0.05) 1px,
    transparent 1px,
    transparent 3px
  );
  transition: opacity 0.6s ease;
}
.zen-atmosphere::after {
  content: "";
  position: absolute;
  inset: 0;
  background: radial-gradient(
    ellipse at center,
    transparent 55%,
    color-mix(in srgb, var(--zen-primary) 12%, transparent) 100%
  );
}
```

- [ ] **Step 6: Commit**

```bash
git add src/components/Atmosphere/Atmosphere.tsx src/__tests__/Atmosphere.test.tsx src/index.css
git -c commit.gpgsign=false commit -m "feat: add Atmosphere grain layer consuming --zen-grain"
git status
```

---

### Task 7: Wire into `App.tsx` and remove the old scene

**Files:**
- Modify: `zendaya-hud-react/src/App.tsx`
- Remove: `zendaya-hud-react/src/scenes/MainScene.tsx`, `zendaya-hud-react/src/components/Orb/Orb.tsx`, `zendaya-hud-react/src/components/MapModule/MapModule.tsx`

- [ ] **Step 1: Confirm there are no remaining importers of the files to be removed**

Run (PowerShell, from `zendaya-hud-react`):
```
Select-String -Path src\**\*.tsx,src\**\*.ts -Pattern "MainScene|components/Orb|MapModule" | Select-Object Path,LineNumber,Line
```
Expected after reading: the only matches are inside `App.tsx` (imports `MainScene`), `scenes/MainScene.tsx` (imports `Orb`/`MapModule`), and a comment in `components/Modules/ModuleHost.tsx`. There must be **no test files** referencing them (there are none). The stale compiled `src/App.js` may also match — **ignore it; it is a build artifact, not part of the Vite/TS source graph. Do not edit or delete it.**

- [ ] **Step 2: Rewrite `App.tsx`**

Replace the entire contents of `zendaya-hud-react/src/App.tsx` with:

```tsx
import { Canvas } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import { motion, AnimatePresence } from "framer-motion";
import SceneManager from "./scenes/SceneManager";
import Hud from "./components/HUD/Hud";
import ModuleHost from "./components/Modules/ModuleHost";
import ThemeRoot from "./themes/ThemeRoot";
import ChromeFrame from "./components/chrome/ChromeFrame";
import Atmosphere from "./components/Atmosphere/Atmosphere";
import { THEMES } from "./themes/registry";
import { useWebSocket } from "./hooks/useWebSocket";
import { useAdaptiveQuality } from "./hooks/useAdaptiveQuality";
import { useAudioEngine } from "./hooks/useAudioEngine";
import { useZendaya } from "./store/zendayaStore";

export default function App() {
  useWebSocket();
  useAdaptiveQuality();
  useAudioEngine();
  const minimized = useZendaya((s) => s.minimized);
  const quality = useZendaya((s) => s.quality);
  const activeThemeId = useZendaya((s) => s.activeThemeId);
  const bloom = 0.45 * (THEMES[activeThemeId]?.bloom ?? 1);
  const dpr: [number, number] = quality === "high" ? [1, 2] : [1, 1];

  return (
    <ThemeRoot>
      <div className="relative w-full h-full bg-black">
        <motion.div
          className="absolute inset-0"
          animate={{
            scale: minimized ? 0.25 : 1,
            x: minimized ? "38%" : "0%",
            y: minimized ? "38%" : "0%",
            opacity: minimized ? 0.85 : 1,
          }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <Canvas
            camera={{ position: [0, 0, 6], fov: 38, near: 0.05, far: 100 }}
            gl={{ alpha: true, antialias: quality === "high", powerPreference: "high-performance" }}
            dpr={dpr}
          >
            <SceneManager />
            <EffectComposer enableNormalPass={false}>
              <Bloom
                intensity={bloom}
                luminanceThreshold={0.35}
                luminanceSmoothing={0.6}
                mipmapBlur
              />
            </EffectComposer>
          </Canvas>
        </motion.div>

        <AnimatePresence>
          {!minimized && (
            <motion.div
              key="hud-overlay"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.5 }}
              className="absolute inset-0"
            >
              <Hud />
              <ChromeFrame />
              <ModuleHost />
            </motion.div>
          )}
        </AnimatePresence>

        <Atmosphere />
      </div>
    </ThemeRoot>
  );
}
```

- [ ] **Step 3: Remove the obsolete scene files**

Run (from `zendaya-hud-react`):
```bash
git rm src/scenes/MainScene.tsx src/components/Orb/Orb.tsx src/components/MapModule/MapModule.tsx
```

- [ ] **Step 4: Type-check + full build**

Run: `npm run build`
Expected: `tsc --noEmit` passes and `vite build` completes with no errors. (`src/animations/*` is now unused but compiles fine; unused exports do not fail the build.)

- [ ] **Step 5: Commit**

```bash
git add src/App.tsx
git -c commit.gpgsign=false commit -m "feat: swap MainScene for SceneManager + Atmosphere; remove legacy orb/map"
git status
```

(The `git rm` from Step 3 is already staged; this commit captures both the `App.tsx` edit and the deletions. Confirm `git status` shows the three files deleted and no protected paths staged.)

---

### Task 8: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full build**

Run: `npm run build`
Expected: PASS (tsc + vite build, no errors).

- [ ] **Step 2: Full test suite**

Run: `npm test`
Expected: PASS — all suites green, including the new `useThemeColors`, `pointcloud`, `sceneManager`, `Atmosphere` tests plus the existing `ChromeFrame` and Phase A suites.

- [ ] **Step 3: Protected-file audit**

Run: `git status` and `git log --oneline -8`
Expected: the new commits touch only files under `zendaya-hud-react/src/`. Confirm NONE of these were modified/staged at any point: `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`. Confirm the pre-existing uncommitted diff is still present and untouched (it should still show as modified/unstaged — that is expected and correct).

- [ ] **Step 4: Manual visual checklist**

Run: `npm run dev`, open the app, and confirm:
- **Idle:** a single themed glowing orb (Forge = warm orange) sits centered, breathing/pulsing with AI state and reacting to voice — no particle field visible at rest.
- **Transition in:** trigger the map intent (e.g., backend "show me the map", or set `scene: "map"` via the store/devtools). The orb scatters into particles, swirls/flashes, then locks into a rotating point-cloud globe with visible continents (~1.2s). Bloom flares at mid-transition.
- **Transition out:** clearing the map (`scene: "main"`, `activeModule: "none"`) reverses cleanly — particles collapse, the solid orb fades back in.
- **Theme switch:** clicking a theme dot (or backend `set_theme`) melts the orb/globe/particle palette over ~0.6s and changes Bloom intensity and the atmosphere grain amount (Iris = cooler/cyan, grainier).
- **Utility dock:** opening a non-map module (e.g., calculator) docks the orb to the configured corner and shrinks it — globe routing is unaffected.
- **No console errors**, and the previously-latent `opacity is undefined` GLSL error is gone (the buggy `MapModule` shader was removed).

- [ ] **Step 5: Report**

Summarize: files created/removed, test counts, build status, and the manual-checklist results. Note any visual tuning the user may want (particle `uSize`, `count`, scatter distance, dock offsets) as Phase C follow-ups.

---

## Self-Review

**Spec coverage (design doc §13 Phase B = scene engine + hero transition):**
- `SceneManager` ✅ Task 5 · themed `IdleOrbScene` ✅ Task 4 · `GlobeScene` ✅ Task 5 · orb→globe particle dissolve (`DissolveField`) ✅ Task 3 · `Atmosphere` ✅ Task 6 · `themes/useThemeColors.ts` ✅ Task 1 · scene routing `scene==="map" || activeModule==="map"` → globe ✅ `selectScene` Task 5 · palette melt on theme change ✅ Tasks 3 & 4 · Bloom scaled by theme `bloom` token ✅ Task 7 · `--zen-grain` made live ✅ Task 6. Phase C items (WeatherScene, ClockScene, chrome rings-sweep, module reskins, ambient audio, dead-code pruning of `animations/`) are correctly deferred.

**Placeholder scan:** No TBD/TODO/"implement later"/"add error handling" placeholders. Every code step contains complete, runnable content. Every test step shows the actual assertions.

**Type consistency (checked across all tasks):**
- `progressRef: React.MutableRefObject<{ v: number }>` is identical in `DissolveField`, `IdleOrbScene`, `GlobeScene`, and is created by `SceneManager` as `useRef({ v: 0 })` — consistent. ✅
- `selectScene(s: { scene: string; activeModule: string }): "idle" | "globe"` — signature in Task 5 implementation matches every call in the Task 5 test and the `SceneManager` internal call. ✅
- `useThemeColors(): { scene, primary, accent: THREE.Color; bloom: number }` — returns `THREE.Color` objects; consumers (`DissolveField`, `IdleOrbScene`) read `.r/.g/.b` and `.clone()`, both valid on `THREE.Color`. ✅
- `buildGlobePoints(count, radius) → { positions, landness }` (Task 2) — consumed by `DissolveField` destructuring `{ positions: globe, landness }`. ✅ `fibonacciSphere(count, radius) → Float32Array` consumed for `aOrbPos`. ✅
- Theme token names used (`sceneColor`, `primary`, `accent`, `bloom`, `grain`) all exist on `ThemeTokens` (verified against `themes/types.ts`/`registry.ts`). ✅
- `getHexString()` expectations: forge `sceneColor #ff8a3c` → `"ff8a3c"`, iris `#2fd6ff` → `"2fd6ff"` (THREE.Color stores sRGB hex verbatim). ✅
- Store reads (`scene`, `activeModule`, `docked`, `dockCorner`, `activeThemeId`, `ai`, `audioLevel`, `visemes`) and `useBodyAction(ref)` signature all verified against the current store/hook. ✅

**Build/test commands:** `npm run build` = `tsc --noEmit && vite build`; `npm test` = `vitest run`; `npm test -- <name>` filters by file — all real per `package.json`. ✅
