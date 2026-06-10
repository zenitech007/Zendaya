# HUD Hologram Phase C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the holographic HUD redesign — ship the WeatherScene and ClockScene 3D morphs, make the SVG chrome react to scene changes, finish the theme-token reskin of the surviving 2D panels, give each theme its own ambient-synth character, and prune the dead pre-redesign code.

**Architecture:** Extends the existing three-layer Hologram stack (Atmosphere / 3D Stage / Chrome) driven by the Theme Engine. Both new scenes bind to the same `SceneManager` + shared `progressRef` morph (0↔1, 1.2 s, power3.inOut) that already powers idle↔globe. WeatherScene reuses the Phase B `DissolveField` particle engine retargeted to a condition form; ClockScene hosts three user-switchable faces. Chrome reaction is a persisted, switchable GSAP animation orthogonal to the theme's chrome shape. No backend / Python / config changes — re-skin, not re-plumb.

**Tech Stack:** React 18 + TypeScript, Zustand 4, Vite 5, Vitest 2.1.9 (happy-dom), Three.js 0.169, @react-three/fiber 8, @react-three/postprocessing (Bloom), GSAP 3, framer-motion 11, Web Audio (AmbientEngine). Build: `npm --prefix zendaya-hud-react run build` (`tsc --noEmit && vite build`). Test: `npm --prefix zendaya-hud-react run test` (`vitest run`).

---

## Working constraints (MUST follow — carried from Phases A/B)

- All work lives under `zendaya-hud-react/src/` (+ this `docs/` plan). **No** edits to `backend/`, Python, `pyproject.toml`, `.gitignore`, or any other config.
- **Never** touch / stage / commit the protected paths: `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`.
- Leave the pre-existing uncommitted working-tree diff alone. **Never** `git add -A`, `git add .`, or `git add -u`. Stage only the exact files named in each task's commit step.
- All commits disable signing: `git -c commit.gpgsign=false commit ...`.
- After every commit, run `git status` and confirm no protected paths were swept in.
- Never stage anything under `.superpowers/`.

---

## Build order (low-risk → high-risk)

1. Prune dead code → 2. Module reskins → 3. Per-theme ambient → 4. Store UI-pref slices → 5. Chrome reaction → 6. ClockScene → 7. WeatherScene → 8. Final verification.

Store prefs (Task 4) ship before Chrome (Task 5, needs `chromeFx`) and Clock (Task 6, needs `clockFace`). Each task leaves a building, test-green HUD.

---

### Task 1: Prune dead code

**Files:**
- Delete: `zendaya-hud-react/src/animations/easing.ts`, `transitions.ts`, `timelines.ts`, `index.ts`
- Delete: `zendaya-hud-react/src/components/Modules/Weather.tsx`
- Delete: `zendaya-hud-react/src/components/Modules/Clock.tsx`
- Modify: `zendaya-hud-react/src/components/Modules/ModuleHost.tsx`

- [ ] **Step 1: Confirm `src/animations/` has zero importers**

Run: `npm --prefix zendaya-hud-react exec -- grep -rn "animations/" src --include=*.ts --include=*.tsx` (or use the Grep tool with pattern `from\s+["'].*animations` over `zendaya-hud-react/src`).
Expected: no matches. (If any match exists, STOP and report — do not delete.)

- [ ] **Step 2: Remove the dead animations module + retired panels**

```bash
git rm zendaya-hud-react/src/animations/easing.ts \
       zendaya-hud-react/src/animations/transitions.ts \
       zendaya-hud-react/src/animations/timelines.ts \
       zendaya-hud-react/src/animations/index.ts \
       zendaya-hud-react/src/components/Modules/Weather.tsx \
       zendaya-hud-react/src/components/Modules/Clock.tsx
```

- [ ] **Step 3: Drop Clock/Weather from `ModuleHost.tsx`**

Replace the entire file with:

```tsx
import { AnimatePresence } from "framer-motion";
import { useZendaya } from "../../store/zendayaStore";
import Calculator from "./Calculator";
import Notes from "./Notes";

export default function ModuleHost() {
  const activeModule = useZendaya((s) => s.activeModule);
  return (
    <AnimatePresence mode="wait">
      {activeModule === "calculator" && <Calculator key="calculator" />}
      {activeModule === "notes" && <Notes key="notes" />}
    </AnimatePresence>
  );
}
```

- [ ] **Step 4: Verify build + tests are green**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: build succeeds (no TS errors about missing Clock/Weather/animations), all existing tests PASS.

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/components/Modules/ModuleHost.tsx
git -c commit.gpgsign=false commit -m "chore(hud): prune dead animations module + retired Clock/Weather panels"
git status
```
Confirm `git status` shows no protected paths staged. (The `git rm` deletions are already staged; only `ModuleHost.tsx` needs adding.)

---

### Task 2: Module reskins (theme tokens) + guard test

**Files:**
- Create: `zendaya-hud-react/src/__tests__/reskinGuard.test.ts`
- Modify: `zendaya-hud-react/src/index.css`
- Modify: `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx`
- Modify: `zendaya-hud-react/src/components/Modules/ModulePanel.tsx`
- Modify: `zendaya-hud-react/src/components/Modules/Notes.tsx`

- [ ] **Step 1: Write the failing guard test**

Create `zendaya-hud-react/src/__tests__/reskinGuard.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// Vitest runs with cwd = the package root (zendaya-hud-react).
const root = process.cwd();
const read = (rel: string) => readFileSync(resolve(root, rel), "utf8");

// Per-file list of retired hard-coded literals that must no longer appear.
const BANNED: Record<string, string[]> = {
  "src/index.css": ["168, 85, 247", "168,85,247"],
  "src/components/HUD/MusicPlayer.tsx": ["168,85,247", "168, 85, 247", "#ec4899", "#a855f7"],
  "src/components/Modules/ModulePanel.tsx": ["255,138,60", "255, 138, 60", "#ff8a3c"],
  "src/components/Modules/Notes.tsx": ["255,138,60", "255, 138, 60"],
};

describe("reskin guard — retired theme literals are gone", () => {
  for (const [file, literals] of Object.entries(BANNED)) {
    const src = read(file);
    for (const lit of literals) {
      it(`${file} no longer contains "${lit}"`, () => {
        expect(src).not.toContain(lit);
      });
    }
  }
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- reskinGuard`
Expected: FAIL — the four files still contain the banned literals.

- [ ] **Step 3: Migrate `index.css` `.zen-player-card` + `.zen-player-btn:hover`**

In `zendaya-hud-react/src/index.css`, replace the `.zen-player-card` block:

```css
.zen-player-card {
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--zen-bg-0) 85%, transparent) 0%,
    color-mix(in srgb, var(--zen-bg-1) 92%, transparent) 100%
  );
  border: 1px solid color-mix(in srgb, var(--zen-primary) 35%, transparent);
  border-radius: 18px;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.04) inset,
    0 24px 60px rgba(0, 0, 0, 0.55),
    0 0 60px color-mix(in srgb, var(--zen-primary) 20%, transparent);
  backdrop-filter: blur(14px);
}
```

And replace the `.zen-player-btn:hover` block:

```css
.zen-player-btn:hover {
  background: color-mix(in srgb, var(--zen-primary) 18%, transparent);
  transform: scale(1.05);
}
```

- [ ] **Step 4: Migrate `MusicPlayer.tsx` art fallback + shadow**

In `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx`, change the album-art `<div>` style (the `background` + `boxShadow` lines):

```tsx
              style={{
                width: 84,
                height: 84,
                background:
                  np.artUrl
                    ? `url(${np.artUrl}) center/cover`
                    : "linear-gradient(135deg, var(--zen-accent), var(--zen-primary))",
                boxShadow: "0 12px 28px rgba(0,0,0,0.45), 0 0 22px color-mix(in srgb, var(--zen-primary) 35%, transparent)",
              }}
```

- [ ] **Step 5: Migrate `ModulePanel.tsx` to tokens**

In `zendaya-hud-react/src/components/Modules/ModulePanel.tsx`, replace the outer `motion.div` `style` object and the two inner colored elements:

```tsx
      style={{
        ...positionStyle,
        borderColor: "color-mix(in srgb, var(--zen-primary) 35%, transparent)",
        background:
          "linear-gradient(180deg, color-mix(in srgb, var(--zen-bg-0) 72%, transparent) 0%, color-mix(in srgb, var(--zen-bg-1) 85%, transparent) 100%)",
        backdropFilter: "blur(14px)",
        WebkitBackdropFilter: "blur(14px)",
        boxShadow:
          "0 18px 60px rgba(0,0,0,0.55), 0 0 0 1px color-mix(in srgb, var(--zen-primary) 8%, transparent) inset, 0 0 60px color-mix(in srgb, var(--zen-primary) 12%, transparent)",
        color: "var(--zen-text-glow)",
        fontFamily: '"Share Tech Mono", monospace',
      }}
```

Change the title-bar divider:

```tsx
        style={{ borderColor: "color-mix(in srgb, var(--zen-primary) 25%, transparent)" }}
```

Change the title color:

```tsx
          style={{ color: "var(--zen-primary)" }}
```

Change the close button color:

```tsx
          style={{ color: "color-mix(in srgb, var(--zen-primary) 70%, transparent)" }}
```

- [ ] **Step 6: Migrate `Notes.tsx` to tokens**

In `zendaya-hud-react/src/components/Modules/Notes.tsx`, change the textarea `style` border + color and the char-count color:

```tsx
        style={{
          background: "rgba(0,0,0,0.5)",
          color: "var(--zen-text-glow)",
          fontFamily: '"Share Tech Mono", monospace',
          fontSize: "0.9em",
          lineHeight: 1.5,
          border: "1px solid color-mix(in srgb, var(--zen-primary) 18%, transparent)",
        }}
```

```tsx
        style={{ color: "color-mix(in srgb, var(--zen-primary) 55%, transparent)" }}
```

- [ ] **Step 7: Run the guard test + full suite + build**

Run: `npm --prefix zendaya-hud-react run test && npm --prefix zendaya-hud-react run build`
Expected: reskinGuard PASS (all banned literals gone), full suite PASS, build succeeds.

- [ ] **Step 8: Commit**

```bash
git add zendaya-hud-react/src/__tests__/reskinGuard.test.ts \
        zendaya-hud-react/src/index.css \
        zendaya-hud-react/src/components/HUD/MusicPlayer.tsx \
        zendaya-hud-react/src/components/Modules/ModulePanel.tsx \
        zendaya-hud-react/src/components/Modules/Notes.tsx
git -c commit.gpgsign=false commit -m "feat(hud): reskin surviving panels + music player to theme tokens"
git status
```
Confirm no protected paths staged.

---

### Task 3: Per-theme ambient audio

**Files:**
- Create: `zendaya-hud-react/src/systems/ambientParams.ts`
- Create: `zendaya-hud-react/src/__tests__/ambientParams.test.ts`
- Modify: `zendaya-hud-react/src/systems/AmbientEngine.ts`
- Modify: `zendaya-hud-react/src/hooks/useAudioEngine.ts`

- [ ] **Step 1: Write the failing param-mapping test**

Create `zendaya-hud-react/src/__tests__/ambientParams.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { ambientParamsFor } from "../systems/ambientParams";

describe("ambientParamsFor", () => {
  it("forge and iris have distinct timbres", () => {
    const f = ambientParamsFor("forge");
    const i = ambientParamsFor("iris");
    expect(f.baseFreq).not.toBe(i.baseFreq);
    expect(f.airFreq).not.toBe(i.airFreq);
    expect(f.brightness).not.toBe(i.brightness);
  });

  it("returns in-range params for known themes", () => {
    for (const id of ["forge", "iris"]) {
      const p = ambientParamsFor(id);
      expect(p.baseFreq).toBeGreaterThanOrEqual(30);
      expect(p.baseFreq).toBeLessThanOrEqual(120);
      expect(p.airFreq).toBeGreaterThan(0);
      expect(p.harmonicMix).toBeGreaterThan(0);
      expect(p.brightness).toBeGreaterThan(0);
    }
  });

  it("falls back to forge for an unknown id", () => {
    expect(ambientParamsFor("nope")).toEqual(ambientParamsFor("forge"));
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- ambientParams`
Expected: FAIL — module `../systems/ambientParams` does not exist.

- [ ] **Step 3: Create the ambient-param table**

Create `zendaya-hud-react/src/systems/ambientParams.ts`:

```ts
/**
 * Per-theme ambient-synth timbre params. Maps the active theme id to the
 * shaping values AmbientEngine.applyTheme() crossfades the oscillator bank to.
 * Forge = warmer/lower; Iris = airier/higher. No audio files — synth only.
 */
export interface AmbientParams {
  baseFreq: number;    // core hum fundamental (Hz)
  harmonicMix: number; // scales the energy-texture voice gain
  airFreq: number;     // orbital-air oscillator frequency (Hz)
  brightness: number;  // scales the texture-voice frequency (220 Hz * brightness)
}

const TABLE: Record<string, AmbientParams> = {
  forge: { baseFreq: 52, harmonicMix: 1.0, airFreq: 150, brightness: 0.8 },
  iris:  { baseFreq: 64, harmonicMix: 0.7, airFreq: 230, brightness: 1.25 },
};

export function ambientParamsFor(id: string): AmbientParams {
  return TABLE[id] ?? TABLE.forge;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- ambientParams`
Expected: PASS.

- [ ] **Step 5: Add `applyTheme` to `AmbientEngine.ts`**

In `zendaya-hud-react/src/systems/AmbientEngine.ts`, add the import at the top (after the existing `AudioManager` import):

```ts
import type { AmbientParams } from "./ambientParams";
```

Then add this method to the `AmbientEngineSingleton` class, immediately before `get isRunning()`:

```ts
  // ── Per-theme timbre — crossfade the voice bank to the active theme ───────
  // Voice order from start(): [0]=core hum, [1]=2nd harmonic, [2]=energy
  // texture, [3]=orbital air. setTargetAtTime gives a click-free glide.
  applyTheme(p: AmbientParams) {
    const ctx = AudioManager.ctx;
    if (!ctx || !this._running) return;
    const t = ctx.currentTime;
    const tau = 0.8; // ~0.8 s glide time-constant
    const [core, harm, tex, air] = this.voices;
    if (core) core.osc.frequency.setTargetAtTime(p.baseFreq, t, tau);
    if (harm) harm.osc.frequency.setTargetAtTime(p.baseFreq * 2, t, tau);
    if (tex) {
      tex.osc.frequency.setTargetAtTime(220 * p.brightness, t, tau);
      tex.gain.gain.setTargetAtTime(0.08 * p.harmonicMix, t, tau);
    }
    if (air) air.osc.frequency.setTargetAtTime(p.airFreq, t, tau);
  }
```

- [ ] **Step 6: Wire `applyTheme` into `useAudioEngine.ts`**

In `zendaya-hud-react/src/hooks/useAudioEngine.ts`, add the import (after the `AmbientEngine` import):

```ts
import { ambientParamsFor } from "../systems/ambientParams";
```

In the bootstrap effect, right after `AmbientEngine.start();`, add:

```ts
      // Shape the ambient synth to the current theme.
      AmbientEngine.applyTheme(ambientParamsFor(useZendaya.getState().activeThemeId));
```

Then add a new subscribe effect (place it after the AI-state subscribe effect):

```ts
  // ── Subscribe to theme changes → reshape ambient timbre ──────────────────
  useEffect(() => {
    let prev = useZendaya.getState().activeThemeId;
    const unsub = useZendaya.subscribe((state) => {
      if (state.activeThemeId !== prev) {
        AmbientEngine.applyTheme(ambientParamsFor(state.activeThemeId));
        prev = state.activeThemeId;
      }
    });
    return () => unsub();
  }, []);
```

- [ ] **Step 7: Verify build + full suite**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: build succeeds, all tests PASS. (Audio timbre itself is smoke-tested live — happy-dom has no Web Audio.)

- [ ] **Step 8: Commit**

```bash
git add zendaya-hud-react/src/systems/ambientParams.ts \
        zendaya-hud-react/src/__tests__/ambientParams.test.ts \
        zendaya-hud-react/src/systems/AmbientEngine.ts \
        zendaya-hud-react/src/hooks/useAudioEngine.ts
git -c commit.gpgsign=false commit -m "feat(hud): per-theme ambient synth timbre with click-free crossfade"
git status
```
Confirm no protected paths staged.

---

### Task 4: Store UI-pref slices (`clockFace` + `chromeFx`)

**Files:**
- Modify: `zendaya-hud-react/src/store/zendayaStore.ts`
- Create: `zendaya-hud-react/src/__tests__/clockChromePrefs.test.ts`

- [ ] **Step 1: Write the failing prefs test**

Create `zendaya-hud-react/src/__tests__/clockChromePrefs.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya, readPref } from "../store/zendayaStore";

beforeEach(() => {
  localStorage.clear();
  useZendaya.setState({ clockFace: "orbital", chromeFx: "aperture" });
});

describe("readPref", () => {
  it("returns the stored value when it is in the allow-list", () => {
    localStorage.setItem("k", "digits");
    expect(readPref("k", ["orbital", "digits", "analog"] as const, "orbital")).toBe("digits");
  });
  it("falls back when the stored value is not allowed", () => {
    localStorage.setItem("k", "bogus");
    expect(readPref("k", ["orbital", "digits", "analog"] as const, "orbital")).toBe("orbital");
  });
  it("falls back when nothing is stored", () => {
    expect(readPref("missing", ["aperture", "spin", "radar"] as const, "aperture")).toBe("aperture");
  });
});

describe("clock + chrome UI prefs", () => {
  it("default clockFace is orbital and chromeFx is aperture", () => {
    expect(useZendaya.getState().clockFace).toBe("orbital");
    expect(useZendaya.getState().chromeFx).toBe("aperture");
  });
  it("setClockFace updates state and persists to localStorage", () => {
    useZendaya.getState().setClockFace("analog");
    expect(useZendaya.getState().clockFace).toBe("analog");
    expect(localStorage.getItem("zendaya.hud.clockFace")).toBe("analog");
  });
  it("setChromeFx updates state and persists to localStorage", () => {
    useZendaya.getState().setChromeFx("radar");
    expect(useZendaya.getState().chromeFx).toBe("radar");
    expect(localStorage.getItem("zendaya.hud.chromeFx")).toBe("radar");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- clockChromePrefs`
Expected: FAIL — `readPref`, `clockFace`, `chromeFx`, `setClockFace`, `setChromeFx` do not exist yet.

- [ ] **Step 3: Add types + `readPref` helper to the store**

In `zendaya-hud-react/src/store/zendayaStore.ts`, add after the existing `ModuleId` type (around line 14):

```ts
export type ClockFace = "orbital" | "digits" | "analog";
export type ChromeFx = "aperture" | "spin" | "radar";

const CLOCK_FACES: readonly ClockFace[] = ["orbital", "digits", "analog"];
const CHROME_FX: readonly ChromeFx[] = ["aperture", "spin", "radar"];
const FACE_KEY = "zendaya.hud.clockFace";
const FX_KEY = "zendaya.hud.chromeFx";

/** Read a persisted enum pref from localStorage, falling back if missing/invalid. */
export function readPref<T extends string>(
  key: string,
  allowed: readonly T[],
  fallback: T,
): T {
  try {
    const v = localStorage.getItem(key);
    if (v && (allowed as readonly string[]).includes(v)) return v as T;
  } catch {
    /* ignore */
  }
  return fallback;
}
```

- [ ] **Step 4: Extend the `ZendayaState` interface**

In the `ZendayaState` interface, add after `activeThemeId: string;` (around line 88):

```ts
  // UI preferences (persisted to localStorage; never from the backend)
  clockFace: ClockFace;
  chromeFx: ChromeFx;
```

And add to the setters section, after `setTheme` / `cycleTheme`:

```ts
  setClockFace: (f: ClockFace) => void;
  setChromeFx: (fx: ChromeFx) => void;
```

- [ ] **Step 5: Seed initial state + implement setters**

In the `create<ZendayaState>((set) => ({ ... }))` initializer, add after `activeThemeId: "forge",` (around line 147):

```ts
  clockFace: readPref(FACE_KEY, CLOCK_FACES, "orbital"),
  chromeFx: readPref(FX_KEY, CHROME_FX, "aperture"),
```

And add the setters after the `cycleTheme` setter (just before the closing `}));`):

```ts
  setClockFace: (f) => {
    try { localStorage.setItem(FACE_KEY, f); } catch { /* ignore */ }
    set({ clockFace: f });
  },
  setChromeFx: (fx) => {
    try { localStorage.setItem(FX_KEY, fx); } catch { /* ignore */ }
    set({ chromeFx: fx });
  },
```

- [ ] **Step 6: Run the test to verify it passes + build**

Run: `npm --prefix zendaya-hud-react run test -- clockChromePrefs && npm --prefix zendaya-hud-react run build`
Expected: PASS, build succeeds.

- [ ] **Step 7: Commit**

```bash
git add zendaya-hud-react/src/store/zendayaStore.ts \
        zendaya-hud-react/src/__tests__/clockChromePrefs.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add persisted clockFace + chromeFx UI-pref store slices"
git status
```
Confirm no protected paths staged.

---

### Task 5: Chrome scene-change reaction (switchable)

**Files:**
- Create: `zendaya-hud-react/src/scenes/sceneRouting.ts`
- Modify: `zendaya-hud-react/src/scenes/SceneManager.tsx` (swap to `sceneRouting`, re-export `selectScene`)
- Modify: `zendaya-hud-react/src/__tests__/sceneManager.test.ts` (add weather/clock cases)
- Create: `zendaya-hud-react/src/components/chrome/chromeFx.ts`
- Create: `zendaya-hud-react/src/__tests__/chromeFx.test.ts`
- Modify: `zendaya-hud-react/src/components/chrome/RingChrome.tsx`
- Modify: `zendaya-hud-react/src/components/chrome/ApertureChrome.tsx`
- Create: `zendaya-hud-react/src/components/chrome/ChromeFxPicker.tsx`
- Modify: `zendaya-hud-react/src/components/chrome/ChromeFrame.tsx`
- Modify: `zendaya-hud-react/src/index.css` (picker styles)

- [ ] **Step 1: Extend the scene-routing test (red)**

Replace `zendaya-hud-react/src/__tests__/sceneManager.test.ts` entirely:

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
  it("returns weather when the weather module is active", () => {
    expect(selectScene({ scene: "main", activeModule: "weather" })).toBe("weather");
  });
  it("returns clock when the clock module is active", () => {
    expect(selectScene({ scene: "main", activeModule: "clock" })).toBe("clock");
  });
  it("returns idle for a non-scene module", () => {
    expect(selectScene({ scene: "main", activeModule: "calculator" })).toBe("idle");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- sceneManager`
Expected: FAIL — `selectScene` still returns `idle` for weather/clock modules.

- [ ] **Step 3: Create `sceneRouting.ts`**

Create `zendaya-hud-react/src/scenes/sceneRouting.ts`:

```ts
/**
 * Pure store-state → 3D stage scene mapping. Lives in its own module so chrome
 * (and other consumers) can route without importing the whole 3D scene graph.
 */
export type StageScene = "idle" | "globe" | "weather" | "clock";

export function selectScene(s: { scene: string; activeModule: string }): StageScene {
  if (s.scene === "map" || s.activeModule === "map") return "globe";
  if (s.activeModule === "weather") return "weather";
  if (s.activeModule === "clock") return "clock";
  return "idle";
}
```

- [ ] **Step 4: Point `SceneManager.tsx` at `sceneRouting` (interim)**

In `zendaya-hud-react/src/scenes/SceneManager.tsx`, delete the inline `export function selectScene(...) { ... }` block. Add this import after the existing `three` import:

```ts
import { selectScene } from "./sceneRouting";
```

And add this re-export immediately below the imports (so `../scenes/SceneManager` still exports `selectScene` for the test):

```ts
export { selectScene };
```

Leave the rest of the component body unchanged. (Clock/weather targets behave like the resting orb until Tasks 6–7 mount their scenes — this is an expected interim state, not a regression; tests stay green.)

- [ ] **Step 5: Run the scene-routing test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- sceneManager`
Expected: PASS (all six cases).

- [ ] **Step 6: Write the failing chromeFx test**

Create `zendaya-hud-react/src/__tests__/chromeFx.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { MORPH_MS, playChromeFx } from "../components/chrome/chromeFx";

function svg() {
  return document.createElementNS("http://www.w3.org/2000/svg", "svg") as SVGSVGElement;
}

describe("chromeFx", () => {
  it("MORPH_MS matches the 1.2s scene morph", () => {
    expect(MORPH_MS).toBe(1200);
  });

  for (const fx of ["aperture", "spin", "radar"] as const) {
    it(`${fx} timeline runs for the full morph window`, () => {
      const tl = playChromeFx(fx, svg());
      expect(tl.duration()).toBeCloseTo(1.2, 1);
      tl.kill();
    });
  }
});
```

- [ ] **Step 7: Run the chromeFx test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- chromeFx`
Expected: FAIL — module `../components/chrome/chromeFx` does not exist.

- [ ] **Step 8: Create `chromeFx.ts`**

Create `zendaya-hud-react/src/components/chrome/chromeFx.ts`:

```ts
import gsap from "gsap";
import { useEffect, useRef } from "react";
import type { RefObject } from "react";
import { useZendaya } from "../../store/zendayaStore";
import type { ChromeFx } from "../../store/zendayaStore";
import { selectScene } from "../../scenes/sceneRouting";

/** The chrome reaction runs over the same window as the 1.2 s scene morph. */
export const MORPH_MS = 1200;
const DUR = MORPH_MS / 1000;

/**
 * Build (and immediately play) the selected chrome reaction on an SVG frame.
 * Returns the GSAP timeline so callers can kill it on re-trigger / unmount.
 * Each timeline lasts exactly DUR seconds. Animates the whole <svg>; the inner
 * CSS-driven idle rotation continues underneath.
 */
export function playChromeFx(fx: ChromeFx, el: SVGSVGElement): gsap.core.Timeline {
  gsap.set(el, { transformOrigin: "center center" });
  const tl = gsap.timeline();
  switch (fx) {
    case "aperture":
      // Contract inward, then reopen — a camera-iris blink.
      tl.to(el, { scale: 0.82, duration: DUR * 0.42, ease: "power2.in" })
        .to(el, { scale: 1, duration: DUR * 0.58, ease: "power3.out" });
      break;
    case "spin":
      // Brief rotation kick + brightness flare, then settle.
      tl.to(el, { rotation: "+=26", filter: "brightness(1.9)", duration: DUR * 0.35, ease: "power1.in" })
        .to(el, { rotation: "+=0", filter: "brightness(1)", duration: DUR * 0.65, ease: "power2.out" });
      break;
    case "radar":
      // One full sweep + a brightness pulse that crests mid-sweep.
      tl.to(el, { rotation: "+=360", duration: DUR, ease: "none" }, 0)
        .to(el, { filter: "brightness(1.7)", duration: DUR * 0.5, ease: "power1.out" }, 0)
        .to(el, { filter: "brightness(1)", duration: DUR * 0.5, ease: "power1.in" }, DUR * 0.5);
      break;
  }
  return tl;
}

/**
 * Fires the active `chromeFx` on the given SVG ref whenever the 3D stage scene
 * changes. No reaction on first mount; a pure preference change does not refire.
 */
export function useChromeReaction(ref: RefObject<SVGSVGElement>) {
  const fx = useZendaya((s) => s.chromeFx);
  const scene = useZendaya((s) => s.scene);
  const activeModule = useZendaya((s) => s.activeModule);
  const stage = selectScene({ scene, activeModule });
  const prev = useRef<string>(stage);
  const tl = useRef<gsap.core.Timeline | null>(null);

  useEffect(() => {
    if (stage === prev.current) return;
    prev.current = stage;
    const el = ref.current;
    if (!el) return;
    tl.current?.kill();
    tl.current = playChromeFx(fx, el);
    return () => { tl.current?.kill(); };
  }, [stage, fx, ref]);
}
```

- [ ] **Step 9: Run the chromeFx test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- chromeFx`
Expected: PASS (MORPH_MS + three timeline-duration cases).

- [ ] **Step 10: Hook the reaction into `RingChrome.tsx`**

In `zendaya-hud-react/src/components/chrome/RingChrome.tsx`, change the imports + add the ref/hook + put the ref on the `<svg>`:

```tsx
import { useRef } from "react";
import type { CSSProperties } from "react";
import { useChromeReaction } from "./chromeFx";

const ORIGIN: CSSProperties = { transformOrigin: "200px 200px" };

export default function RingChrome() {
  const ref = useRef<SVGSVGElement>(null);
  useChromeReaction(ref);
  const ticks = Array.from({ length: 60 });
  return (
    <svg
      ref={ref}
      className="zen-ring-chrome"
      data-testid="ring-chrome"
      viewBox="0 0 400 400"
      aria-hidden
    >
```

(Leave the rest of the SVG body unchanged.)

- [ ] **Step 11: Hook the reaction into `ApertureChrome.tsx`**

In `zendaya-hud-react/src/components/chrome/ApertureChrome.tsx`, mirror the change:

```tsx
import { useRef } from "react";
import type { CSSProperties } from "react";
import { useChromeReaction } from "./chromeFx";

const ORIGIN: CSSProperties = { transformOrigin: "200px 200px" };

export default function ApertureChrome() {
  const ref = useRef<SVGSVGElement>(null);
  useChromeReaction(ref);
  const blades = Array.from({ length: 12 });
  return (
    <svg
      ref={ref}
      className="zen-aperture-chrome"
      data-testid="aperture-chrome"
      viewBox="0 0 400 400"
      aria-hidden
    >
```

(Leave the rest of the SVG body unchanged.)

- [ ] **Step 12: Create `ChromeFxPicker.tsx`**

Create `zendaya-hud-react/src/components/chrome/ChromeFxPicker.tsx`:

```tsx
import type { CSSProperties } from "react";
import { useZendaya, type ChromeFx } from "../../store/zendayaStore";

const FX: { id: ChromeFx; label: string }[] = [
  { id: "aperture", label: "IRIS" },
  { id: "spin", label: "SPIN" },
  { id: "radar", label: "SCAN" },
];

/** Picks the persisted chrome scene-change reaction. Always visible. */
export default function ChromeFxPicker() {
  const fx = useZendaya((s) => s.chromeFx);
  const setChromeFx = useZendaya((s) => s.setChromeFx);

  return (
    <div className="zen-chromefx-picker" role="group" aria-label="Chrome reaction picker">
      {FX.map((f) => (
        <button
          key={f.id}
          type="button"
          className={"zen-fx-dot" + (f.id === fx ? " active" : "")}
          aria-current={f.id === fx || undefined}
          title={f.label}
          onClick={() => setChromeFx(f.id)}
          style={{ "--dot": "var(--zen-primary)" } as CSSProperties}
        >
          <span className="zen-fx-lbl">{f.label}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 13: Mount the picker in `ChromeFrame.tsx`**

Replace `zendaya-hud-react/src/components/chrome/ChromeFrame.tsx` entirely:

```tsx
import { useZendaya } from "../../store/zendayaStore";
import { THEMES } from "../../themes/registry";
import RingChrome from "./RingChrome";
import ApertureChrome from "./ApertureChrome";
import ThemePicker from "./ThemePicker";
import ChromeFxPicker from "./ChromeFxPicker";

export default function ChromeFrame() {
  const id = useZendaya((s) => s.activeThemeId);
  const chrome = THEMES[id]?.chrome ?? "ring";

  return (
    <>
      <div className="zen-chrome-frame" aria-hidden>
        {chrome === "aperture" ? <ApertureChrome /> : <RingChrome />}
      </div>
      <ThemePicker />
      <ChromeFxPicker />
    </>
  );
}
```

- [ ] **Step 14: Add the picker styles to `index.css`**

Append to `zendaya-hud-react/src/index.css` (after the `.zen-theme-dot.active` block):

```css
/* ---------- Chrome reaction picker ---------- */
.zen-chromefx-picker {
  position: absolute;
  bottom: 24px;
  right: 24px;
  display: flex;
  gap: 8px;
  pointer-events: auto;
  z-index: 30;
}
.zen-fx-dot {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 22px;
  padding: 0 10px;
  border-radius: 11px;
  border: 1px solid color-mix(in srgb, var(--zen-primary) 30%, transparent);
  background: color-mix(in srgb, var(--zen-primary) 6%, transparent);
  color: var(--zen-text-glow);
  font-family: "Share Tech Mono", monospace;
  font-size: 8px;
  letter-spacing: 0.18em;
  opacity: 0.5;
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.2s, border-color 0.2s;
}
.zen-fx-dot:hover { opacity: 0.85; }
.zen-fx-dot.active {
  opacity: 1;
  border-color: var(--zen-primary);
  box-shadow: 0 0 12px color-mix(in srgb, var(--zen-primary) 50%, transparent);
}
.zen-fx-lbl { pointer-events: none; }
```

- [ ] **Step 15: Verify build + full suite**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: build succeeds, all tests PASS (including existing `ChromeFrame.test.tsx`, which still finds the ring/aperture testids).

- [ ] **Step 16: Commit**

```bash
git add zendaya-hud-react/src/scenes/sceneRouting.ts \
        zendaya-hud-react/src/scenes/SceneManager.tsx \
        zendaya-hud-react/src/__tests__/sceneManager.test.ts \
        zendaya-hud-react/src/components/chrome/chromeFx.ts \
        zendaya-hud-react/src/__tests__/chromeFx.test.ts \
        zendaya-hud-react/src/components/chrome/RingChrome.tsx \
        zendaya-hud-react/src/components/chrome/ApertureChrome.tsx \
        zendaya-hud-react/src/components/chrome/ChromeFxPicker.tsx \
        zendaya-hud-react/src/components/chrome/ChromeFrame.tsx \
        zendaya-hud-react/src/index.css
git -c commit.gpgsign=false commit -m "feat(hud): switchable chrome scene-change reaction (aperture/spin/radar)"
git status
```
Confirm no protected paths staged.

---

### Task 6: ClockScene (three faces + switcher + readout)

**Files:**
- Create: `zendaya-hud-react/src/scenes/clock/faceCommon.ts`
- Create: `zendaya-hud-react/src/scenes/clock/digitFont.ts`
- Create: `zendaya-hud-react/src/__tests__/clockFace.test.ts`
- Create: `zendaya-hud-react/src/scenes/clock/OrbitalFace.tsx`
- Create: `zendaya-hud-react/src/scenes/clock/DigitsFace.tsx`
- Create: `zendaya-hud-react/src/scenes/clock/AnalogFace.tsx`
- Create: `zendaya-hud-react/src/scenes/ClockScene.tsx`
- Create: `zendaya-hud-react/src/components/HUD/ClockReadout.tsx`
- Create: `zendaya-hud-react/src/components/HUD/ClockFacePicker.tsx`
- Modify: `zendaya-hud-react/src/scenes/SceneManager.tsx` (mount-managed scenes; conditional globe/clock mounts)
- Modify: `zendaya-hud-react/src/index.css` (clock readout + face-picker styles)
- Modify: `zendaya-hud-react/src/App.tsx` (mount `<ClockReadout/>` + `<ClockFacePicker/>`)

The two testable units here are pure: `presenceOf` (morph×fade gate) and `buildDigitPoints` (dot-matrix glyph point cloud). They live in plain `.ts` files (no R3F import) so happy-dom can test them. The faces themselves are WebGL and verified live in Task 8. **WeatherScene does not exist yet** — Task 6's `SceneManager` mounts only `globe` + `clock`; Task 7 adds the `weather` line.

- [ ] **Step 1: Write the failing pure-helper test**

Create `zendaya-hud-react/src/__tests__/clockFace.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { presenceOf } from "../scenes/clock/faceCommon";
import { buildDigitPoints } from "../scenes/clock/digitFont";

describe("presenceOf", () => {
  it("is 0 before the morph passes 0.15", () => {
    expect(presenceOf(0.0, 1)).toBe(0);
    expect(presenceOf(0.1, 1)).toBe(0);
  });
  it("is fully present at progress 1 with fade 1", () => {
    expect(presenceOf(1.0, 1)).toBeCloseTo(1, 5);
  });
  it("is gated (multiplied) by the crossfade value", () => {
    expect(presenceOf(1.0, 0)).toBe(0);
    expect(presenceOf(1.0, 0.5)).toBeCloseTo(0.5, 5);
  });
});

describe("buildDigitPoints", () => {
  it("returns a Float32Array whose length is a multiple of 3", () => {
    const pts = buildDigitPoints("13:47");
    expect(pts).toBeInstanceOf(Float32Array);
    expect(pts.length % 3).toBe(0);
    expect(pts.length).toBeGreaterThan(0);
  });
  it("produces only finite coordinates", () => {
    const pts = buildDigitPoints("00:00");
    expect(pts.every((v) => Number.isFinite(v))).toBe(true);
  });
  it("falls back to a zero glyph for unknown characters", () => {
    // 'X' is not in the font; it must not throw and must still emit points.
    expect(buildDigitPoints("X").length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- clockFace`
Expected: FAIL — modules `../scenes/clock/faceCommon` and `../scenes/clock/digitFont` do not exist.

- [ ] **Step 3: Create `faceCommon.ts`**

Create `zendaya-hud-react/src/scenes/clock/faceCommon.ts`:

```ts
import * as THREE from "three";

/** Shared props for every clock face. */
export interface FaceProps {
  progressRef: React.MutableRefObject<{ v: number }>;
  fadeRef: React.MutableRefObject<{ v: number }>;
}

/**
 * Combined 0..1 presence for a face: the shared orb→scene morph (gated so the
 * face only appears once the morph passes 0.15) multiplied by the per-face
 * crossfade value driven on face switches.
 */
export function presenceOf(progress: number, fade: number): number {
  return THREE.MathUtils.smoothstep(progress, 0.15, 1.0) * fade;
}
```

- [ ] **Step 4: Create `digitFont.ts`**

Create `zendaya-hud-react/src/scenes/clock/digitFont.ts`:

```ts
// 3×5 dot-matrix font for the DigitsFace clock. "1" = lit cell.
export const FONT: Record<string, string[]> = {
  "0": ["111", "101", "101", "101", "111"],
  "1": ["010", "110", "010", "010", "111"],
  "2": ["111", "001", "111", "100", "111"],
  "3": ["111", "001", "111", "001", "111"],
  "4": ["101", "101", "111", "001", "001"],
  "5": ["111", "100", "111", "001", "111"],
  "6": ["111", "100", "111", "101", "111"],
  "7": ["111", "001", "010", "010", "010"],
  "8": ["111", "101", "111", "101", "111"],
  "9": ["111", "101", "111", "001", "111"],
  ":": ["000", "010", "000", "010", "000"],
};

const CHAR_W = 3;
const CHAR_H = 5;
const GAP = 1; // empty columns between characters
const CELL = 0.14; // world units per matrix cell
const SUB = 2; // sub-particles per cell axis (SUB*SUB particles per lit cell)

/**
 * Build a particle point cloud (length = N*3) tracing `text` in the dot-matrix
 * font, centred on the origin in the XY plane with a small Z jitter for depth.
 * Unknown characters fall back to the "0" glyph so this never throws.
 */
export function buildDigitPoints(text: string): Float32Array {
  const totalCols = text.length * CHAR_W + Math.max(0, text.length - 1) * GAP;
  const pts: number[] = [];
  let cursor = 0;
  for (const ch of text) {
    const glyph = FONT[ch] ?? FONT["0"];
    for (let row = 0; row < CHAR_H; row++) {
      for (let col = 0; col < CHAR_W; col++) {
        if (glyph[row][col] !== "1") continue;
        for (let sx = 0; sx < SUB; sx++) {
          for (let sy = 0; sy < SUB; sy++) {
            const gx = cursor + col + (sx + 0.5) / SUB;
            const gy = row + (sy + 0.5) / SUB;
            const x = (gx - totalCols / 2) * CELL;
            const y = (CHAR_H / 2 - gy) * CELL;
            pts.push(x, y, (Math.random() - 0.5) * 0.04);
          }
        }
      }
    }
    cursor += CHAR_W + GAP;
  }
  return new Float32Array(pts);
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- clockFace`
Expected: PASS (presenceOf + buildDigitPoints cases).

- [ ] **Step 6: Create `OrbitalFace.tsx`**

Create `zendaya-hud-react/src/scenes/clock/OrbitalFace.tsx`:

```tsx
import { useCallback, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeColors } from "../../themes/useThemeColors";
import { presenceOf, type FaceProps } from "./faceCommon";

// Hours / minutes / seconds rings, each tilted differently for a 3D orbit look.
const RINGS = [
  { radius: 1.5, tilt: 0.0 },
  { radius: 1.1, tilt: 0.5 },
  { radius: 0.7, tilt: -0.5 },
];

/** Three tilted orbital rings with a node sweeping each to the current value. */
export default function OrbitalFace({ progressRef, fadeRef }: FaceProps) {
  const colors = useThemeColors();
  const group = useRef<THREE.Group>(null!);
  const nodes = useRef<THREE.Mesh[]>([]);
  const mats = useRef<THREE.MeshBasicMaterial[]>([]);

  const ringColor = useMemo(() => colors.primary.clone(), [colors]);
  const nodeColor = useMemo(() => colors.accent.clone(), [colors]);

  const registerNode = useCallback((el: THREE.Mesh | null) => {
    if (el && !nodes.current.includes(el)) nodes.current.push(el);
  }, []);
  const registerMat = useCallback((el: THREE.MeshBasicMaterial | null) => {
    if (el && !mats.current.includes(el)) mats.current.push(el);
  }, []);

  useFrame(() => {
    const presence = presenceOf(progressRef.current.v, fadeRef.current.v);
    if (group.current) group.current.visible = presence > 0.001;
    for (const m of mats.current) if (m) m.opacity = presence * 0.6;

    const now = new Date();
    const fracs = [
      (now.getHours() % 12) / 12,
      now.getMinutes() / 60,
      now.getSeconds() / 60,
    ];
    for (let i = 0; i < RINGS.length; i++) {
      const node = nodes.current[i];
      if (!node) continue;
      const ang = fracs[i] * Math.PI * 2 - Math.PI / 2; // start at 12 o'clock
      const r = RINGS[i].radius;
      node.position.set(Math.cos(ang) * r, Math.sin(ang) * r, 0);
    }
  });

  return (
    <group ref={group} rotation={[Math.PI * 0.18, 0, 0]}>
      {RINGS.map((ring, i) => (
        <group key={i} rotation={[ring.tilt, ring.tilt * 0.5, 0]}>
          <mesh>
            <torusGeometry args={[ring.radius, 0.012, 8, 120]} />
            <meshBasicMaterial
              ref={registerMat}
              color={ringColor}
              transparent
              opacity={0}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
          <mesh ref={registerNode}>
            <sphereGeometry args={[0.05, 16, 16]} />
            <meshBasicMaterial
              ref={registerMat}
              color={nodeColor}
              transparent
              opacity={0}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        </group>
      ))}
    </group>
  );
}
```

- [ ] **Step 7: Create `DigitsFace.tsx`**

Create `zendaya-hud-react/src/scenes/clock/DigitsFace.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeColors } from "../../themes/useThemeColors";
import { buildDigitPoints } from "./digitFont";
import { presenceOf, type FaceProps } from "./faceCommon";

function hhmmOf(d: Date): string {
  const h = String(d.getHours()).padStart(2, "0");
  const m = String(d.getMinutes()).padStart(2, "0");
  return `${h}:${m}`;
}

/** Particle HH:MM glyphs wrapped by a thin seconds ring with a sweeping node. */
export default function DigitsFace({ progressRef, fadeRef }: FaceProps) {
  const colors = useThemeColors();
  const [hhmm, setHhmm] = useState(() => hhmmOf(new Date()));
  const positions = useMemo(() => buildDigitPoints(hhmm), [hhmm]);

  const group = useRef<THREE.Group>(null!);
  const glyphMat = useRef<THREE.PointsMaterial>(null);
  const ringMat = useRef<THREE.MeshBasicMaterial>(null);
  const nodeMat = useRef<THREE.MeshBasicMaterial>(null);
  const node = useRef<THREE.Mesh>(null);

  const glyphColor = useMemo(() => colors.accent.clone(), [colors]);
  const ringColor = useMemo(() => colors.primary.clone(), [colors]);

  useEffect(() => {
    const id = window.setInterval(() => setHhmm(hhmmOf(new Date())), 1000);
    return () => window.clearInterval(id);
  }, []);

  useFrame(() => {
    const presence = presenceOf(progressRef.current.v, fadeRef.current.v);
    if (group.current) group.current.visible = presence > 0.001;
    if (glyphMat.current) glyphMat.current.opacity = presence;
    if (ringMat.current) ringMat.current.opacity = presence * 0.4;
    if (nodeMat.current) nodeMat.current.opacity = presence;

    const sec = new Date().getSeconds() / 60;
    const ang = sec * Math.PI * 2 - Math.PI / 2;
    if (node.current) node.current.position.set(Math.cos(ang) * 1.7, Math.sin(ang) * 1.7, 0);
  });

  return (
    <group ref={group} rotation={[Math.PI * 0.06, 0, 0]}>
      <points key={hhmm}>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        </bufferGeometry>
        <pointsMaterial
          ref={glyphMat}
          color={glyphColor}
          size={0.055}
          transparent
          opacity={0}
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </points>
      <mesh>
        <torusGeometry args={[1.7, 0.01, 8, 120]} />
        <meshBasicMaterial
          ref={ringMat}
          color={ringColor}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      <mesh ref={node}>
        <sphereGeometry args={[0.045, 16, 16]} />
        <meshBasicMaterial
          ref={nodeMat}
          color={glyphColor}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}
```

- [ ] **Step 8: Create `AnalogFace.tsx`**

Create `zendaya-hud-react/src/scenes/clock/AnalogFace.tsx`:

```tsx
import { useCallback, useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { useThemeColors } from "../../themes/useThemeColors";
import { presenceOf, type FaceProps } from "./faceCommon";

/** Tilted 3D dial: rim + 12 ticks + three box hands pivoting at the centre. */
export default function AnalogFace({ progressRef, fadeRef }: FaceProps) {
  const colors = useThemeColors();
  const group = useRef<THREE.Group>(null!);
  const hourHand = useRef<THREE.Group>(null!);
  const minHand = useRef<THREE.Group>(null!);
  const secHand = useRef<THREE.Group>(null!);
  const mats = useRef<THREE.MeshBasicMaterial[]>([]);

  const rimColor = useMemo(() => colors.primary.clone(), [colors]);
  const handColor = useMemo(() => colors.accent.clone(), [colors]);
  const ticks = useMemo(() => Array.from({ length: 12 }, (_, i) => i), []);

  const registerMat = useCallback((el: THREE.MeshBasicMaterial | null) => {
    if (el && !mats.current.includes(el)) mats.current.push(el);
  }, []);

  useFrame(() => {
    const presence = presenceOf(progressRef.current.v, fadeRef.current.v);
    if (group.current) group.current.visible = presence > 0.001;
    for (const m of mats.current) if (m) m.opacity = presence;

    const now = new Date();
    const sec = now.getSeconds() + now.getMilliseconds() / 1000;
    const min = now.getMinutes() + sec / 60;
    const hour = (now.getHours() % 12) + min / 60;
    if (secHand.current) secHand.current.rotation.z = -(sec / 60) * Math.PI * 2;
    if (minHand.current) minHand.current.rotation.z = -(min / 60) * Math.PI * 2;
    if (hourHand.current) hourHand.current.rotation.z = -(hour / 12) * Math.PI * 2;
  });

  return (
    <group ref={group} rotation={[Math.PI * 0.16, 0, 0]}>
      <mesh>
        <torusGeometry args={[1.5, 0.012, 8, 160]} />
        <meshBasicMaterial
          ref={registerMat}
          color={rimColor}
          transparent
          opacity={0}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
      {ticks.map((i) => {
        const ang = (i / 12) * Math.PI * 2;
        const r = 1.35;
        return (
          <mesh key={i} position={[Math.cos(ang) * r, Math.sin(ang) * r, 0]} rotation={[0, 0, ang]}>
            <boxGeometry args={[0.12, 0.02, 0.02]} />
            <meshBasicMaterial
              ref={registerMat}
              color={rimColor}
              transparent
              opacity={0}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </mesh>
        );
      })}
      {/* Each hand's box is offset +Y so its base sits at the group origin and
          it pivots about Z at the centre; rotation 0 points to 12 o'clock. */}
      <group ref={hourHand}>
        <mesh position={[0, 0.4, 0.02]}>
          <boxGeometry args={[0.03, 0.8, 0.02]} />
          <meshBasicMaterial
            ref={registerMat}
            color={handColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>
      <group ref={minHand}>
        <mesh position={[0, 0.6, 0.03]}>
          <boxGeometry args={[0.022, 1.2, 0.02]} />
          <meshBasicMaterial
            ref={registerMat}
            color={handColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>
      <group ref={secHand}>
        <mesh position={[0, 0.65, 0.04]}>
          <boxGeometry args={[0.01, 1.3, 0.01]} />
          <meshBasicMaterial
            ref={registerMat}
            color={rimColor}
            transparent
            opacity={0}
            blending={THREE.AdditiveBlending}
            depthWrite={false}
          />
        </mesh>
      </group>
    </group>
  );
}
```

- [ ] **Step 9: Create `ClockScene.tsx`**

Create `zendaya-hud-react/src/scenes/ClockScene.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { useZendaya, type ClockFace } from "../store/zendayaStore";
import OrbitalFace from "./clock/OrbitalFace";
import DigitsFace from "./clock/DigitsFace";
import AnalogFace from "./clock/AnalogFace";

export interface ClockSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
}

/**
 * Hosts the three clock faces. The selected face comes from the store; switching
 * crossfades a shared `fadeRef` (out → swap → in) instead of hard-cutting. Each
 * face multiplies its presence by `fadeRef.v`, so the tween dims/raises it.
 */
export default function ClockScene({ progressRef }: ClockSceneProps) {
  const clockFace = useZendaya((s) => s.clockFace);
  const fadeRef = useRef({ v: 1 });
  const [shownFace, setShownFace] = useState<ClockFace>(clockFace);

  useEffect(() => {
    if (clockFace === shownFace) return;
    const tl = gsap.timeline();
    tl.to(fadeRef.current, { v: 0, duration: 0.18, ease: "power2.in" });
    tl.add(() => setShownFace(clockFace));
    tl.to(fadeRef.current, { v: 1, duration: 0.22, ease: "power2.out" });
    return () => {
      tl.kill();
    };
  }, [clockFace, shownFace]);

  return (
    <group>
      {shownFace === "orbital" && <OrbitalFace progressRef={progressRef} fadeRef={fadeRef} />}
      {shownFace === "digits" && <DigitsFace progressRef={progressRef} fadeRef={fadeRef} />}
      {shownFace === "analog" && <AnalogFace progressRef={progressRef} fadeRef={fadeRef} />}
    </group>
  );
}
```

- [ ] **Step 10: Create `ClockReadout.tsx`**

Create `zendaya-hud-react/src/components/HUD/ClockReadout.tsx`:

```tsx
import { useEffect, useState } from "react";
import { useZendaya } from "../../store/zendayaStore";

/** Floating digital time + date line for the Orbital/Analog faces. */
export default function ClockReadout() {
  const activeModule = useZendaya((s) => s.activeModule);
  const clockFace = useZendaya((s) => s.clockFace);
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  // The Digits face renders its own large time, so it gets no readout.
  if (activeModule !== "clock" || clockFace === "digits") return null;

  const hh = String(now.getHours()).padStart(2, "0");
  const mm = String(now.getMinutes()).padStart(2, "0");
  const ss = String(now.getSeconds()).padStart(2, "0");
  const date = now.toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });

  return (
    <div className="zen-clock-readout">
      <div className="zen-clock-time">
        {hh}:{mm}
        <span className="zen-clock-sec">:{ss}</span>
      </div>
      <div className="zen-clock-date">{date}</div>
    </div>
  );
}
```

- [ ] **Step 11: Create `ClockFacePicker.tsx`**

Create `zendaya-hud-react/src/components/HUD/ClockFacePicker.tsx`:

```tsx
import { useZendaya, type ClockFace } from "../../store/zendayaStore";

const FACES: { id: ClockFace; label: string }[] = [
  { id: "orbital", label: "ORBITAL" },
  { id: "digits", label: "DIGITS" },
  { id: "analog", label: "ANALOG" },
];

/** Theme-picker-style dot row; visible only while the clock scene is active. */
export default function ClockFacePicker() {
  const activeModule = useZendaya((s) => s.activeModule);
  const clockFace = useZendaya((s) => s.clockFace);
  const setClockFace = useZendaya((s) => s.setClockFace);

  if (activeModule !== "clock") return null;

  return (
    <div className="zen-clock-face-picker">
      {FACES.map((f) => (
        <button
          key={f.id}
          type="button"
          className={`zen-face-dot${clockFace === f.id ? " active" : ""}`}
          onClick={() => setClockFace(f.id)}
        >
          <span className="zen-face-lbl">{f.label}</span>
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 12: Rewrite `SceneManager.tsx` with mount-managed scenes**

Replace the entire contents of `zendaya-hud-react/src/scenes/SceneManager.tsx` with:

```tsx
import { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";
import { selectScene, type StageScene } from "./sceneRouting";
import IdleOrbScene from "./IdleOrbScene";
import GlobeScene from "./GlobeScene";
import ClockScene from "./ClockScene";

// Keep the old import path working for tests/consumers that import the router.
export { selectScene };

/**
 * Owns the shared orb→scene morph progress (0 idle … 1 active scene), GSAP-tweened
 * on scene change, mounts the active heavy scene (and keeps it alive through the
 * exit morph), and corner-docks the whole stage for utility (idle) modules.
 */
export default function SceneManager() {
  const stage = useRef<THREE.Group>(null!);
  const progressRef = useRef({ v: 0 });

  const scene = useZendaya((s) => s.scene);
  const activeModule = useZendaya((s) => s.activeModule);
  const docked = useZendaya((s) => s.docked);
  const dockCorner = useZendaya((s) => s.dockCorner);

  const target = selectScene({ scene, activeModule });

  // Which heavy scene is mounted. Mount immediately on enter; defer unmount to
  // the end of the exit morph so the dissolve plays out before it disappears.
  const [mounted, setMounted] = useState<StageScene>(target);

  // Drive the morph progress.
  useEffect(() => {
    const tween = gsap.to(progressRef.current, {
      v: target === "idle" ? 0 : 1,
      duration: 1.2,
      ease: "power3.inOut",
    });
    return () => {
      tween.kill();
    };
  }, [target]);

  // Mount on enter; defer unmount until the exit morph finishes (~1.3 s).
  useEffect(() => {
    if (target !== "idle") {
      setMounted(target);
      return;
    }
    const id = window.setTimeout(() => setMounted("idle"), 1300);
    return () => window.clearTimeout(id);
  }, [target]);

  // Corner-dock the stage only for docked utility modules in the idle scene.
  useEffect(() => {
    const g = stage.current;
    if (!g) return;
    const dockToCorner = docked && target === "idle";
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
        {mounted === "globe" && <GlobeScene progressRef={progressRef} />}
        {mounted === "clock" && <ClockScene progressRef={progressRef} />}
      </group>
    </>
  );
}
```

> Note: the `weather` mount line is added in Task 7 (WeatherScene does not exist yet). `selectScene` already returns `"weather"` for the weather module, but until Task 7 nothing renders it — that path is not exercised by the clock work or the test suite.

- [ ] **Step 13: Add clock CSS to `index.css`**

Append to the end of `zendaya-hud-react/src/index.css`:

```css
/* ---------- Clock readout + face picker ---------- */
.zen-clock-readout {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  pointer-events: none;
  font-family: "Share Tech Mono", monospace;
  text-shadow: 0 0 18px color-mix(in srgb, var(--zen-primary) 70%, transparent);
  z-index: 20;
}
.zen-clock-time {
  font-size: 34px;
  letter-spacing: 0.14em;
  color: var(--zen-text-glow);
}
.zen-clock-sec {
  font-size: 20px;
  opacity: 0.6;
}
.zen-clock-date {
  margin-top: 6px;
  font-size: 11px;
  letter-spacing: 0.3em;
  opacity: 0.6;
  color: var(--zen-text-glow);
}
.zen-clock-face-picker {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 8px;
  pointer-events: auto;
  z-index: 30;
}
.zen-face-dot {
  height: 22px;
  padding: 0 10px;
  border-radius: 11px;
  border: 1px solid color-mix(in srgb, var(--zen-primary) 30%, transparent);
  background: color-mix(in srgb, var(--zen-primary) 6%, transparent);
  color: var(--zen-text-glow);
  font-family: "Share Tech Mono", monospace;
  font-size: 8px;
  letter-spacing: 0.18em;
  opacity: 0.5;
  cursor: pointer;
  transition: opacity 0.2s, box-shadow 0.2s, border-color 0.2s;
}
.zen-face-dot:hover {
  opacity: 0.85;
}
.zen-face-dot.active {
  opacity: 1;
  border-color: var(--zen-primary);
  box-shadow: 0 0 12px color-mix(in srgb, var(--zen-primary) 50%, transparent);
}
.zen-face-lbl {
  pointer-events: none;
}
```

- [ ] **Step 14: Mount the clock overlays in `App.tsx`**

In `zendaya-hud-react/src/App.tsx`, add these imports after the existing `ChromeFrame` import (line 8):

```tsx
import ClockReadout from "./components/HUD/ClockReadout";
import ClockFacePicker from "./components/HUD/ClockFacePicker";
```

Then, inside the overlay `motion.div`, add the two components after `<ModuleHost />`:

```tsx
              <Hud />
              <ChromeFrame />
              <ModuleHost />
              <ClockReadout />
              <ClockFacePicker />
```

- [ ] **Step 15: Verify build + full suite**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: build succeeds (tsc clean), all tests PASS including the new `clockFace` cases and the existing `sceneManager` cases (which still import `selectScene` from `../scenes/SceneManager`).

- [ ] **Step 16: Commit**

```bash
git add zendaya-hud-react/src/scenes/clock/faceCommon.ts \
        zendaya-hud-react/src/scenes/clock/digitFont.ts \
        zendaya-hud-react/src/__tests__/clockFace.test.ts \
        zendaya-hud-react/src/scenes/clock/OrbitalFace.tsx \
        zendaya-hud-react/src/scenes/clock/DigitsFace.tsx \
        zendaya-hud-react/src/scenes/clock/AnalogFace.tsx \
        zendaya-hud-react/src/scenes/ClockScene.tsx \
        zendaya-hud-react/src/components/HUD/ClockReadout.tsx \
        zendaya-hud-react/src/components/HUD/ClockFacePicker.tsx \
        zendaya-hud-react/src/scenes/SceneManager.tsx \
        zendaya-hud-react/src/index.css \
        zendaya-hud-react/src/App.tsx
git -c commit.gpgsign=false commit -m "feat(hud): ClockScene with orbital/digits/analog faces + switcher + readout"
git status
```
Confirm no protected paths staged.

---

### Task 7: WeatherScene (particle morph + readout) — signature finale

**Files:**
- Create: `zendaya-hud-react/src/scenes/weatherForms.ts`
- Create: `zendaya-hud-react/src/__tests__/weatherForms.test.ts`
- Modify: `zendaya-hud-react/src/scenes/DissolveField.tsx` (generalize: `targetPositions` + `plain` mode)
- Create: `zendaya-hud-react/src/hooks/useWeather.ts`
- Create: `zendaya-hud-react/src/scenes/WeatherScene.tsx`
- Create: `zendaya-hud-react/src/components/HUD/WeatherReadout.tsx`
- Modify: `zendaya-hud-react/src/scenes/SceneManager.tsx` (add the `weather` mount)
- Modify: `zendaya-hud-react/src/index.css` (weather readout styles)
- Modify: `zendaya-hud-react/src/App.tsx` (mount `<WeatherReadout/>`)

The pure unit here is `weatherForms.ts` (`wmoToForm` + `buildFormPoints`). Per the spec, **all particle color comes from the active theme** — the weather *form* changes the particle *geometry/behavior*, not its color. So `buildFormPoints` returns positions only; coloring stays in `DissolveField` via `useThemeColors()`.

- [ ] **Step 1: Write the failing weatherForms test**

Create `zendaya-hud-react/src/__tests__/weatherForms.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { wmoToForm, buildFormPoints } from "../scenes/weatherForms";

describe("wmoToForm", () => {
  it("maps clear codes", () => {
    expect(wmoToForm(0)).toBe("clear");
    expect(wmoToForm(1)).toBe("clear");
  });
  it("maps cloud codes", () => {
    expect(wmoToForm(2)).toBe("clouds");
    expect(wmoToForm(3)).toBe("clouds");
  });
  it("maps fog codes", () => {
    expect(wmoToForm(45)).toBe("fog");
    expect(wmoToForm(48)).toBe("fog");
  });
  it("maps rain codes (drizzle, rain, showers)", () => {
    expect(wmoToForm(51)).toBe("rain");
    expect(wmoToForm(63)).toBe("rain");
    expect(wmoToForm(80)).toBe("rain");
  });
  it("maps snow codes", () => {
    expect(wmoToForm(71)).toBe("snow");
    expect(wmoToForm(77)).toBe("snow");
    expect(wmoToForm(86)).toBe("snow");
  });
  it("maps thunderstorm codes", () => {
    expect(wmoToForm(95)).toBe("storm");
    expect(wmoToForm(99)).toBe("storm");
  });
  it("defaults unknown codes to clouds", () => {
    expect(wmoToForm(1234)).toBe("clouds");
    expect(wmoToForm(-1)).toBe("clouds");
  });
});

describe("buildFormPoints", () => {
  it("returns count*3 finite coordinates", () => {
    const pts = buildFormPoints("storm", 500);
    expect(pts).toBeInstanceOf(Float32Array);
    expect(pts.length).toBe(500 * 3);
    expect(pts.every((v) => Number.isFinite(v))).toBe(true);
  });
  it("differs between forms (geometry, not just color)", () => {
    const a = buildFormPoints("clear", 300);
    const b = buildFormPoints("storm", 300);
    let differing = 0;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) differing++;
    expect(differing).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm --prefix zendaya-hud-react run test -- weatherForms`
Expected: FAIL — module `../scenes/weatherForms` does not exist.

- [ ] **Step 3: Create `weatherForms.ts`**

Create `zendaya-hud-react/src/scenes/weatherForms.ts`:

```ts
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm --prefix zendaya-hud-react run test -- weatherForms`
Expected: PASS (all `wmoToForm` buckets + both `buildFormPoints` cases).

- [ ] **Step 5: Generalize `DissolveField.tsx`**

Make these edits to `zendaya-hud-react/src/scenes/DissolveField.tsx`.

**(a)** Extend the props interface (replace the existing `DissolveFieldProps` block):

```tsx
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
```

**(b)** Update the component signature and the geometry memo. Replace the function signature line and the geometry `useMemo` block with:

```tsx
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
```

**(c)** Add the two plain-mode uniforms. In the material `useMemo`'s `uniforms` object, the existing block ends with `uColorOcean`. Replace those three color lines with:

```tsx
          uColorOrb: { value: colors.scene.clone() },
          uColorLand: { value: colors.accent.clone() },
          uColorOcean: { value: colors.scene.clone() },
          uPlain: { value: plain ? 1 : 0 },
          uColorPlain: { value: colors.accent.clone() },
```

**(d)** Replace the fragment shader's uniform declarations block:

```glsl
          uniform float uOpacity;
          uniform float uProgress;
          uniform vec3 uColorOrb;
          uniform vec3 uColorLand;
          uniform vec3 uColorOcean;
          uniform float uPlain;
          uniform vec3 uColorPlain;
          varying float vLandness;
```

**(e)** Replace the fragment shader `main()` body:

```glsl
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
```

**(f)** Recolor plain mode on theme change. In the palette-melt `useEffect`, after the existing `uColorOcean` tween, add:

```tsx
    gsap.to(u.uColorPlain.value, {
      r: colors.accent.r, g: colors.accent.g, b: colors.accent.b,
      duration: 0.6, ease: "power2.inOut",
    });
```

- [ ] **Step 6: Verify the globe still builds + tests green**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: build succeeds; all tests PASS. (The globe DissolveField uses `plain=false` → `uPlain=0`, so `col = colGlobe` and `fade = oceanFade` — behavior is identical to Phase B.)

- [ ] **Step 7: Create `useWeather.ts`**

Create `zendaya-hud-react/src/hooks/useWeather.ts`:

```ts
import { useEffect, useState } from "react";
import { wmoToForm, type WeatherForm } from "../scenes/weatherForms";

export interface WeatherData {
  tempC: number | null;
  code: number | null;
  windKph: number | null;
  humidity: number | null;
  city: string;
  form: WeatherForm;
  loading: boolean;
  error: string | null;
}

type WeatherCore = Omit<WeatherData, "loading" | "error">;
interface CacheEntry {
  data: WeatherCore;
  at: number;
}

// Module-level cache shared by the scene and the readout; ~10-min TTL.
let _cache: CacheEntry | null = null;
const TTL = 10 * 60 * 1000;

async function fetchWeather(): Promise<WeatherCore> {
  const geo = await fetch("https://ipapi.co/json/").then((r) => r.json());
  const lat = geo.latitude;
  const lon = geo.longitude;
  const city = geo.city ?? "—";
  const url =
    `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}` +
    `&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m`;
  const wx = await fetch(url).then((r) => r.json());
  const c = wx.current ?? {};
  const code = c.weather_code ?? 0;
  return {
    tempC: c.temperature_2m ?? null,
    code,
    windKph: c.wind_speed_10m ?? null,
    humidity: c.relative_humidity_2m ?? null,
    city,
    form: wmoToForm(code),
  };
}

/** Geolocates via ipapi + fetches Open-Meteo current conditions; cached. */
export function useWeather(): WeatherData {
  const [state, setState] = useState<WeatherData>(() =>
    _cache
      ? { ..._cache.data, loading: false, error: null }
      : {
          tempC: null, code: null, windKph: null, humidity: null,
          city: "—", form: "clouds", loading: true, error: null,
        }
  );

  useEffect(() => {
    let alive = true;
    if (_cache && Date.now() - _cache.at < TTL) {
      setState({ ..._cache.data, loading: false, error: null });
      return;
    }
    setState((s) => ({ ...s, loading: true, error: null }));
    fetchWeather()
      .then((data) => {
        _cache = { data, at: Date.now() };
        if (alive) setState({ ...data, loading: false, error: null });
      })
      .catch((e) => {
        if (alive) setState((s) => ({ ...s, loading: false, error: String(e?.message ?? e) }));
      });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
```

- [ ] **Step 8: Create `WeatherScene.tsx`**

Create `zendaya-hud-react/src/scenes/WeatherScene.tsx`:

```tsx
import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import DissolveField from "./DissolveField";
import { buildFormPoints } from "./weatherForms";
import { useWeather } from "../hooks/useWeather";

export interface WeatherSceneProps {
  progressRef: React.MutableRefObject<{ v: number }>;
}

/**
 * Morphs the orb point-cloud into the current weather form and gently rotates.
 * Remounts the field (via `key={form}`) when the condition changes so the
 * geometry rebuilds to the new form. All color comes from the active theme.
 */
export default function WeatherScene({ progressRef }: WeatherSceneProps) {
  const { form } = useWeather();
  const spin = useRef<THREE.Group>(null!);
  const positions = useMemo(() => buildFormPoints(form, 9000, 1.4), [form]);

  useFrame((_, dt) => {
    if (spin.current) spin.current.rotation.y += dt * 0.08 * progressRef.current.v;
  });

  return (
    <group ref={spin}>
      <DissolveField
        key={form}
        progressRef={progressRef}
        count={9000}
        targetPositions={positions}
        plain
      />
    </group>
  );
}
```

- [ ] **Step 9: Create `WeatherReadout.tsx`**

Create `zendaya-hud-react/src/components/HUD/WeatherReadout.tsx`:

```tsx
import { useZendaya } from "../../store/zendayaStore";
import { useWeather } from "../../hooks/useWeather";
import type { WeatherForm } from "../../scenes/weatherForms";

const LABELS: Record<WeatherForm, string> = {
  clear: "Clear",
  clouds: "Cloudy",
  rain: "Rain",
  snow: "Snow",
  storm: "Storm",
  fog: "Fog",
};

/** Floating holographic temp/condition/city/wind/humidity; weather scene only. */
export default function WeatherReadout() {
  const activeModule = useZendaya((s) => s.activeModule);
  const wx = useWeather();

  if (activeModule !== "weather") return null;

  return (
    <div className="zen-weather-readout">
      {wx.loading && <div className="zen-wx-status">Locating…</div>}
      {!wx.loading && wx.error && <div className="zen-wx-status">Weather unavailable</div>}
      {!wx.loading && !wx.error && (
        <>
          <div className="zen-wx-temp">{wx.tempC != null ? Math.round(wx.tempC) : "--"}°</div>
          <div className="zen-wx-cond">{LABELS[wx.form]}</div>
          <div className="zen-wx-city">{wx.city}</div>
          <div className="zen-wx-meta">
            <span>wind {wx.windKph != null ? Math.round(wx.windKph) : "--"} km/h</span>
            <span>humidity {wx.humidity != null ? Math.round(wx.humidity) : "--"}%</span>
          </div>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 10: Add the weather mount to `SceneManager.tsx`**

In `zendaya-hud-react/src/scenes/SceneManager.tsx`, add the import after the `ClockScene` import:

```tsx
import ClockScene from "./ClockScene";
import WeatherScene from "./WeatherScene";
```

And add the weather conditional mount between the globe and clock mounts, inside the `<group ref={stage}>`:

```tsx
        {mounted === "globe" && <GlobeScene progressRef={progressRef} />}
        {mounted === "weather" && <WeatherScene progressRef={progressRef} />}
        {mounted === "clock" && <ClockScene progressRef={progressRef} />}
```

- [ ] **Step 11: Mount `WeatherReadout` in `App.tsx`**

In `zendaya-hud-react/src/App.tsx`, add the import after the `ClockFacePicker` import:

```tsx
import ClockFacePicker from "./components/HUD/ClockFacePicker";
import WeatherReadout from "./components/HUD/WeatherReadout";
```

And add it to the overlay after `<ClockFacePicker />`:

```tsx
              <ClockReadout />
              <ClockFacePicker />
              <WeatherReadout />
```

- [ ] **Step 12: Add weather CSS to `index.css`**

Append to the end of `zendaya-hud-react/src/index.css`:

```css
/* ---------- Weather readout ---------- */
.zen-weather-readout {
  position: absolute;
  left: 50%;
  top: 18%;
  transform: translateX(-50%);
  text-align: center;
  pointer-events: none;
  font-family: "Share Tech Mono", monospace;
  color: var(--zen-text-glow);
  text-shadow: 0 0 18px color-mix(in srgb, var(--zen-primary) 70%, transparent);
  z-index: 20;
}
.zen-wx-temp {
  font-size: 46px;
  letter-spacing: 0.04em;
  line-height: 1;
}
.zen-wx-cond {
  font-size: 14px;
  letter-spacing: 0.3em;
  text-transform: uppercase;
  opacity: 0.85;
  margin-top: 4px;
}
.zen-wx-city {
  font-size: 11px;
  letter-spacing: 0.3em;
  opacity: 0.6;
  margin-top: 8px;
}
.zen-wx-meta {
  display: flex;
  gap: 18px;
  justify-content: center;
  font-size: 10px;
  letter-spacing: 0.15em;
  opacity: 0.55;
  margin-top: 10px;
}
.zen-wx-status {
  font-size: 12px;
  letter-spacing: 0.2em;
  opacity: 0.7;
}
```

- [ ] **Step 13: Verify build + full suite**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: build succeeds (tsc clean), all tests PASS including the new `weatherForms` cases.

- [ ] **Step 14: Commit**

```bash
git add zendaya-hud-react/src/scenes/weatherForms.ts \
        zendaya-hud-react/src/__tests__/weatherForms.test.ts \
        zendaya-hud-react/src/scenes/DissolveField.tsx \
        zendaya-hud-react/src/hooks/useWeather.ts \
        zendaya-hud-react/src/scenes/WeatherScene.tsx \
        zendaya-hud-react/src/components/HUD/WeatherReadout.tsx \
        zendaya-hud-react/src/scenes/SceneManager.tsx \
        zendaya-hud-react/src/index.css \
        zendaya-hud-react/src/App.tsx
git -c commit.gpgsign=false commit -m "feat(hud): WeatherScene particle morph + floating readout (live ipapi/Open-Meteo)"
git status
```
Confirm no protected paths staged.

---

### Task 8: Final verification (build, live smoke, protected-path audit)

**Files:** none created/modified unless smoke testing surfaces a fix.

This task verifies the whole Phase C delivery. No commit unless a smoke-test fix is needed (if so, commit it with a focused message and re-run the checklist).

- [ ] **Step 1: Full clean build + test**

Run: `npm --prefix zendaya-hud-react run build && npm --prefix zendaya-hud-react run test`
Expected: `tsc --noEmit` clean, `vite build` succeeds, all Vitest suites PASS (`reskinGuard`, `clockChromePrefs`, `ambientParams`, `sceneManager`, `chromeFx`, `clockFace`, `weatherForms`, plus all pre-existing Phase A/B suites).

- [ ] **Step 2: Start the preview server**

Run: `npm --prefix zendaya-hud-react run dev` (Vite dev server, port 5191 per the project's preview setup). Use the preview MCP (or a browser) to load the HUD. happy-dom cannot run WebGL/Web-Audio, so the 3D scenes, chrome reaction, and ambient audio are verified here, live.

- [ ] **Step 3: Live smoke checklist**

Confirm each item visually:

1. **Idle orb** renders and breathes; wordmark visible at rest.
2. **Globe** — trigger the map module (or `scene: "map"`): orb dissolves into the spinning point-cloud globe; chrome plays the selected reaction; ambient unchanged.
3. **WeatherScene** — trigger the weather module: orb morphs into the weather form; `WeatherReadout` shows temp/condition/city/wind/humidity (or a graceful "Locating…" / "Weather unavailable"); returning to idle reverses the morph.
4. **ClockScene** — trigger the clock module: orbital face shows three sweeping rings; `ClockFacePicker` appears; switching to **digits** crossfades to particle `HH:MM` + seconds ring (no readout); switching to **analog** crossfades to the tilted dial; `ClockReadout` shows for orbital/analog only; reload the page and confirm the chosen face persisted.
5. **Chrome reaction** — switch `ChromeFxPicker` among aperture/spin/radar; trigger a scene change for each and confirm the frame reacts; reload and confirm the chosen fx persisted.
6. **Per-theme ambient** — switch theme (Forge ↔ Iris) and confirm the ambient timbre shifts smoothly (no clicks) and the palette melts.
7. **Panels** — open calculator + notes; confirm they render in theme tokens (no leftover purple/orange literals); the music player matches the theme.
8. **No console errors** during any of the above.

- [ ] **Step 4: Protected-path audit**

Run: `git status` and `git log --oneline -8`
Confirm:
- The working tree shows no staged/committed changes to any protected path (`backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`).
- The pre-existing uncommitted diff is still present and unstaged (it was never touched).
- `.superpowers/` is not staged.
- Phase C produced exactly the Task 1–7 commits, all under `zendaya-hud-react/src/` + this plan/spec doc.

- [ ] **Step 5: Report**

Summarize: which scenes/features shipped, test counts, any deferred follow-ups (e.g., direct scene-to-scene morph polish, weather forecast timeline — both explicitly out of scope this phase), and confirm the Phase C done-criteria from the spec are met.

---

## Self-Review

Checked against `docs/superpowers/specs/2026-06-02-hud-hologram-phase-c-design.md`:

- **Spec coverage:** prune (Task 1) ✓; panel/music reskin + guard (Task 2) ✓; per-theme ambient + crossfade (Task 3) ✓; persisted `clockFace`/`chromeFx` slices (Task 4) ✓; chrome scene-change reaction aperture/spin/radar (Task 5) ✓; ClockScene three faces + switcher + readout + routing (Task 6) ✓; WeatherScene particle morph + `useWeather` + `weatherForms` + readout + routing (Task 7) ✓; final verification (Task 8) ✓. Every spec §4–§9 unit maps to a task.
- **Type consistency:** `StageScene = "idle"|"globe"|"weather"|"clock"` (in `sceneRouting.ts`, distinct from the store's `SceneId="main"|"map"|"dashboard"`); `selectScene` re-exported from `SceneManager` for the existing test; `ClockFace`/`ChromeFx` + `readPref` imported from the store; `FaceProps`/`presenceOf` shared by all three faces; `WeatherForm` shared by `weatherForms`/`useWeather`/`WeatherReadout`; `buildFormPoints` returns `Float32Array` (positions only — color from theme) consistently in scene + test; `buildDigitPoints` returns `Float32Array` consistently in `DigitsFace` + test.
- **Placeholder scan:** no TBD / "add error handling" / "similar to Task N"; every code step is complete. New CSS uses only `var(--zen-primary)` / `var(--zen-text-glow)` / `color-mix(...)` — no banned color literals (the reskin guard only governs the four reskinned files, but the new files stay token-only anyway).
- **Build order:** prune → reskin → ambient → store-prefs → chrome → clock → weather → verify. Each task ends build-green and test-green; Task 6 deliberately omits the weather mount (added in Task 7) so it compiles standalone.
