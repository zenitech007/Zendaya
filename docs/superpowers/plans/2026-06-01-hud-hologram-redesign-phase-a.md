# Holographic HUD Redesign — Phase A (Theme Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the theme engine for the Zendaya HUD — a registry of named themes (Forge, Iris) plus the machinery to switch between them by voice and an on-screen picker, re-skinning the HUD chrome and background via design tokens — without touching any backend/store/websocket plumbing beyond additive extensions.

**Architecture:** "Layered Hologram." A `ThemeRoot` resolves the active theme's tokens into CSS custom properties that cascade to a DOM/SVG chrome layer (`ChromeFrame` → `RingChrome`/`ApertureChrome`) and the background. The active theme lives in the existing Zustand store; it is set by a `ThemePicker` control or a new `set_theme` WebSocket action. The 3D stage is untouched in this phase (it stays the current orb); themed 3D scenes arrive in Phase B.

**Tech Stack:** React 18 + TypeScript, Zustand 4, Vite 5, Vitest 2 + happy-dom + @testing-library/react, plain CSS (Tailwind v3 present), SVG for chrome.

---

## Working Constraints (read before starting)

- **Frontend lives in `zendaya-hud-react/`.** All `npm`/`npx` commands run from that directory. Git commands run from the repo root `C:\Users\IKA\Zendaya` with repo-relative paths.
- **Git safety (hard rules):**
  - Sign-off is disabled in this environment — commit with `git -c commit.gpgsign=false commit ...`.
  - **Never** `git add -A` / `git add .`. Stage only the exact files named in each task.
  - **Never** modify or stage these pre-existing working-tree files: `.gitignore`, `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `zendaya_logs/assistant_history.json`. They carry unrelated WIP and must stay modified-but-unstaged.
  - LF→CRLF warnings from git on Windows are harmless.
- **TDD:** for every task with logic, write the failing test first, watch it fail, implement, watch it pass, commit. Pure-visual SVG components get a render/"smoke" test only.
- **Run a single test file:** `npx vitest run src/__tests__/<file>` (from `zendaya-hud-react/`).
- **Run the whole suite:** `npm test` (from `zendaya-hud-react/`).

---

## File Structure (Phase A)

| File | Responsibility |
| --- | --- |
| `zendaya-hud-react/src/themes/types.ts` | `ThemeTokens` interface + `ChromeStyle` union. |
| `zendaya-hud-react/src/themes/registry.ts` | `THEMES` record (forge, iris) + `THEME_ORDER`. Single source of truth for themes. |
| `zendaya-hud-react/src/themes/ThemeRoot.tsx` | Reads active theme, writes tokens → CSS variables on a wrapper; exports `themeCssVars`. |
| `zendaya-hud-react/src/components/chrome/RingChrome.tsx` | Forge SVG chrome (segmented rings + ticks + accent sweep). |
| `zendaya-hud-react/src/components/chrome/ApertureChrome.tsx` | Iris SVG chrome (aperture/eye rings). |
| `zendaya-hud-react/src/components/chrome/ChromeFrame.tsx` | Picks chrome by active theme's `chrome`; mounts chrome + `ThemePicker`. |
| `zendaya-hud-react/src/components/chrome/ThemePicker.tsx` | On-screen theme dots; click → `setTheme`. |
| `zendaya-hud-react/src/store/zendayaStore.ts` *(modify)* | Add `activeThemeId`, `setTheme`, `cycleTheme`. |
| `zendaya-hud-react/src/hooks/useWebSocket.ts` *(modify)* | Add `set_theme` action to `dispatchAction`. |
| `zendaya-hud-react/src/App.tsx` *(modify)* | Wrap in `ThemeRoot`; mount `ChromeFrame`. |
| `zendaya-hud-react/src/index.css` *(modify)* | Default theme vars in `:root`; reskin wordmark/player/background to vars; chrome + picker CSS. |
| `zendaya-hud-react/src/__tests__/themeRegistry.test.ts` | Registry integrity. |
| `zendaya-hud-react/src/__tests__/themeStore.test.ts` | Store slice logic. |
| `zendaya-hud-react/src/__tests__/ThemeRoot.test.tsx` | Token → CSS var resolution. |
| `zendaya-hud-react/src/__tests__/ThemePicker.test.tsx` | Picker behavior. |
| `zendaya-hud-react/src/__tests__/ChromeFrame.test.tsx` | Chrome selection by theme. |
| `zendaya-hud-react/src/__tests__/useWebSocket.test.ts` *(extend)* | `set_theme` routing. |

**Out of Phase A (separate plans):** the 3D scene engine, `IdleOrbScene`/`GlobeScene`, the orb→globe particle dissolve, `Atmosphere` grain/scanlines, `WeatherScene`/`ClockScene`, `GaugeChrome`/`RadarChrome` (Chronos/Recon), `useThemeColors` (3D color hook — built in Phase B where the 3D first consumes theme colors), and reskinning the inline-styled `TelemetryWidget`/`PerceptionIndicator`.

---

### Task 1: Theme token types + registry

**Files:**
- Create: `zendaya-hud-react/src/themes/types.ts`
- Create: `zendaya-hud-react/src/themes/registry.ts`
- Test: `zendaya-hud-react/src/__tests__/themeRegistry.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/themeRegistry.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { THEMES, THEME_ORDER } from "../themes/registry";
import type { ChromeStyle } from "../themes/types";

const REQUIRED_KEYS = [
  "id", "name", "primary", "accent", "bg", "textGlow",
  "sceneColor", "bloom", "chrome", "ambient", "grain",
] as const;
const VALID_CHROME: ChromeStyle[] = ["ring", "aperture", "gauge", "radar"];

describe("theme registry", () => {
  it("every theme has all required token fields", () => {
    for (const [key, t] of Object.entries(THEMES)) {
      for (const k of REQUIRED_KEYS) {
        expect(t, `${key}.${k} missing`).toHaveProperty(k);
      }
    }
  });

  it("theme.id matches its registry key", () => {
    for (const [key, t] of Object.entries(THEMES)) expect(t.id).toBe(key);
  });

  it("chrome is a valid style", () => {
    for (const t of Object.values(THEMES)) expect(VALID_CHROME).toContain(t.chrome);
  });

  it("bg is a 2-tuple", () => {
    for (const t of Object.values(THEMES)) {
      expect(Array.isArray(t.bg)).toBe(true);
      expect(t.bg).toHaveLength(2);
    }
  });

  it("THEME_ORDER ids all exist in THEMES", () => {
    for (const id of THEME_ORDER) expect(THEMES[id]).toBeDefined();
  });

  it("ships forge and iris", () => {
    expect(THEMES.forge).toBeDefined();
    expect(THEMES.iris).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/themeRegistry.test.ts`
Expected: FAIL — cannot resolve import `../themes/registry`.

- [ ] **Step 3: Create the types file**

Create `zendaya-hud-react/src/themes/types.ts`:

```ts
export type ChromeStyle = "ring" | "aperture" | "gauge" | "radar";

export interface ThemeTokens {
  id: string;            // "iris"
  name: string;          // "Iris"
  // palette
  primary: string;       // main chrome + glow color (hex)
  accent: string;        // accent sweep / highlight (hex)
  bg: [string, string];  // radial background stops [inner, outer]
  textGlow: string;      // wordmark/caption glow color
  // 3D stage (consumed in Phase B)
  sceneColor: string;    // tint for orb/globe/scenes
  bloom: number;         // bloom intensity multiplier
  // chrome + atmosphere
  chrome: ChromeStyle;   // which chrome component renders
  ambient: string;       // ambient audio pad id
  grain: number;         // 0..1 background grain/scanline amount
}
```

- [ ] **Step 4: Create the registry file**

Create `zendaya-hud-react/src/themes/registry.ts`:

```ts
import type { ThemeTokens } from "./types";

export const THEMES: Record<string, ThemeTokens> = {
  forge: {
    id: "forge", name: "Forge",
    primary: "#ff8a1e", accent: "#19d3a0", bg: ["#1a0d05", "#070302"],
    textGlow: "#ffb060", sceneColor: "#ff8a3c", bloom: 1.3,
    chrome: "ring", ambient: "warm-pad", grain: 0.18,
  },
  iris: {
    id: "iris", name: "Iris",
    primary: "#2fd6ff", accent: "#ff4d4d", bg: ["#06182a", "#02060c"],
    textGlow: "#9fe9ff", sceneColor: "#2fd6ff", bloom: 1.1,
    chrome: "aperture", ambient: "airy-pad", grain: 0.30,
  },
};

export const THEME_ORDER: string[] = ["forge", "iris"];
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/__tests__/themeRegistry.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/themes/types.ts zendaya-hud-react/src/themes/registry.ts zendaya-hud-react/src/__tests__/themeRegistry.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): theme token schema + registry (Forge, Iris)"
```

---

### Task 2: Store theme slice

**Files:**
- Modify: `zendaya-hud-react/src/store/zendayaStore.ts`
- Test: `zendaya-hud-react/src/__tests__/themeStore.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/themeStore.test.ts`:

```ts
import { beforeEach, describe, expect, it } from "vitest";
import { useZendaya } from "../store/zendayaStore";

beforeEach(() => {
  useZendaya.setState({ activeThemeId: "forge" });
});

describe("theme store slice", () => {
  it("default activeThemeId is forge", () => {
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });

  it("setTheme switches to a known theme", () => {
    useZendaya.getState().setTheme("iris");
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });

  it("setTheme ignores unknown ids", () => {
    useZendaya.getState().setTheme("nope");
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });

  it("cycleTheme advances and wraps", () => {
    useZendaya.setState({ activeThemeId: "forge" });
    useZendaya.getState().cycleTheme();
    expect(useZendaya.getState().activeThemeId).toBe("iris");
    useZendaya.getState().cycleTheme();
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/themeStore.test.ts`
Expected: FAIL — `setTheme is not a function` / `activeThemeId` undefined.

- [ ] **Step 3: Add the import at the top of the store**

In `zendaya-hud-react/src/store/zendayaStore.ts`, just below the existing `import { create } from "zustand";` line (line 1), add:

```ts
import { THEMES, THEME_ORDER } from "../themes/registry";
```

- [ ] **Step 4: Extend the `ZendayaState` interface**

In `zendaya-hud-react/src/store/zendayaStore.ts`, inside `interface ZendayaState`, add these fields immediately after the `fps: number;` line (line 84):

```ts
  // Theme engine
  activeThemeId: string;
```

And add these setter signatures immediately after the `setFps: (n: number) => void;` line (line 110):

```ts
  setTheme: (id: string) => void;
  cycleTheme: () => void;
```

- [ ] **Step 5: Add the initial state + actions to the store body**

In the `create<ZendayaState>((set) => ({ ... }))` object, add the initial value immediately after `fps: 60,` (line 140):

```ts
  activeThemeId: "forge",
```

And add the actions immediately after the `setFps: (n) => set({ fps: n }),` line (line 179):

```ts
  setTheme: (id) =>
    set(() => (THEMES[id] ? { activeThemeId: id } : {})),
  cycleTheme: () =>
    set((s) => {
      const i = THEME_ORDER.indexOf(s.activeThemeId);
      const next = THEME_ORDER[(i + 1) % THEME_ORDER.length];
      return { activeThemeId: next };
    }),
```

- [ ] **Step 6: Run test to verify it passes**

Run: `npx vitest run src/__tests__/themeStore.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/store/zendayaStore.ts zendaya-hud-react/src/__tests__/themeStore.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): store theme slice — activeThemeId + setTheme + cycleTheme"
```

---

### Task 3: `set_theme` WebSocket action

**Files:**
- Modify: `zendaya-hud-react/src/hooks/useWebSocket.ts`
- Test: `zendaya-hud-react/src/__tests__/useWebSocket.test.ts` (extend)

- [ ] **Step 1: Write the failing test**

In `zendaya-hud-react/src/__tests__/useWebSocket.test.ts`, add `activeThemeId: "forge",` to the `useZendaya.setState({ ... })` object inside the existing top-level `beforeEach` (so each test starts on Forge). Then append this new describe block at the end of the file:

```ts
describe("useWebSocket — set_theme action", () => {
  it("set_theme switches to a known theme", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "set_theme", payload: { name: "iris" } });
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });

  it("set_theme ignores an unknown theme name", async () => {
    const { ws } = await freshHook();
    ws.fireMessage({ action: "set_theme", payload: { name: "bogus" } });
    expect(useZendaya.getState().activeThemeId).toBe("forge");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/useWebSocket.test.ts`
Expected: FAIL — `activeThemeId` stays `"forge"` after the valid `set_theme` (the action is unhandled, so the first new test fails).

- [ ] **Step 3: Add the `set_theme` case**

In `zendaya-hud-react/src/hooks/useWebSocket.ts`, inside the `dispatchAction` switch, add a new case immediately before the `default:` case (around line 200):

```ts
    case "set_theme": {
      const name = typeof payload.name === "string" ? payload.name : "";
      z.setTheme(name); // setTheme ignores unknown ids
      break;
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/__tests__/useWebSocket.test.ts`
Expected: PASS (all existing tests + 2 new).

- [ ] **Step 5: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/hooks/useWebSocket.ts zendaya-hud-react/src/__tests__/useWebSocket.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): set_theme websocket action routes to store.setTheme"
```

---

### Task 4: `ThemeRoot` — CSS variable delivery

**Files:**
- Create: `zendaya-hud-react/src/themes/ThemeRoot.tsx`
- Test: `zendaya-hud-react/src/__tests__/ThemeRoot.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/ThemeRoot.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ThemeRoot, { themeCssVars } from "../themes/ThemeRoot";
import { THEMES } from "../themes/registry";

describe("themeCssVars", () => {
  it("maps tokens to css custom properties", () => {
    const vars = themeCssVars(THEMES.iris);
    expect(vars["--zen-primary"]).toBe(THEMES.iris.primary);
    expect(vars["--zen-accent"]).toBe(THEMES.iris.accent);
    expect(vars["--zen-bg-0"]).toBe(THEMES.iris.bg[0]);
    expect(vars["--zen-bg-1"]).toBe(THEMES.iris.bg[1]);
    expect(vars["--zen-text-glow"]).toBe(THEMES.iris.textGlow);
    expect(vars["--zen-grain"]).toBe(String(THEMES.iris.grain));
  });
});

describe("ThemeRoot", () => {
  it("renders a wrapper carrying the active theme's css vars", () => {
    useZendaya.setState({ activeThemeId: "forge" });
    const { container } = render(
      <ThemeRoot><div>child</div></ThemeRoot>
    );
    const root = container.querySelector(".zen-theme-root") as HTMLElement;
    expect(root).toBeTruthy();
    expect(root.getAttribute("data-theme")).toBe("forge");
    expect(root.style.getPropertyValue("--zen-primary")).toBe(THEMES.forge.primary);
  });

  it("reflects a theme switch", () => {
    useZendaya.setState({ activeThemeId: "iris" });
    const { container } = render(
      <ThemeRoot><div>child</div></ThemeRoot>
    );
    const root = container.querySelector(".zen-theme-root") as HTMLElement;
    expect(root.getAttribute("data-theme")).toBe("iris");
    expect(root.style.getPropertyValue("--zen-primary")).toBe(THEMES.iris.primary);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/ThemeRoot.test.tsx`
Expected: FAIL — cannot resolve import `../themes/ThemeRoot`.

- [ ] **Step 3: Implement `ThemeRoot`**

Create `zendaya-hud-react/src/themes/ThemeRoot.tsx`:

```tsx
import type { CSSProperties, ReactNode } from "react";
import { useZendaya } from "../store/zendayaStore";
import { THEMES } from "./registry";
import type { ThemeTokens } from "./types";

export function themeCssVars(t: ThemeTokens): Record<string, string> {
  return {
    "--zen-primary": t.primary,
    "--zen-accent": t.accent,
    "--zen-bg-0": t.bg[0],
    "--zen-bg-1": t.bg[1],
    "--zen-text-glow": t.textGlow,
    "--zen-grain": String(t.grain),
  };
}

export default function ThemeRoot({ children }: { children: ReactNode }) {
  const id = useZendaya((s) => s.activeThemeId);
  const tokens = THEMES[id] ?? THEMES.forge;
  return (
    <div
      className="zen-theme-root"
      data-theme={tokens.id}
      style={themeCssVars(tokens) as CSSProperties}
    >
      {children}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/__tests__/ThemeRoot.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/themes/ThemeRoot.tsx zendaya-hud-react/src/__tests__/ThemeRoot.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): ThemeRoot resolves theme tokens to cascading CSS variables"
```

---

### Task 5: `ThemePicker` control

**Files:**
- Create: `zendaya-hud-react/src/components/chrome/ThemePicker.tsx`
- Test: `zendaya-hud-react/src/__tests__/ThemePicker.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/ThemePicker.test.tsx`:

```tsx
import { beforeEach, describe, it, expect } from "vitest";
import { render, fireEvent } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ThemePicker from "../components/chrome/ThemePicker";
import { THEME_ORDER, THEMES } from "../themes/registry";

beforeEach(() => useZendaya.setState({ activeThemeId: "forge" }));

describe("ThemePicker", () => {
  it("renders one dot per theme", () => {
    const { getAllByRole } = render(<ThemePicker />);
    expect(getAllByRole("button")).toHaveLength(THEME_ORDER.length);
  });

  it("clicking a theme dot switches the active theme", () => {
    const { getByLabelText } = render(<ThemePicker />);
    fireEvent.click(getByLabelText(THEMES.iris.name));
    expect(useZendaya.getState().activeThemeId).toBe("iris");
  });

  it("marks the active theme with aria-current", () => {
    const { getByLabelText } = render(<ThemePicker />);
    expect(getByLabelText(THEMES.forge.name).getAttribute("aria-current")).toBe("true");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/ThemePicker.test.tsx`
Expected: FAIL — cannot resolve import `../components/chrome/ThemePicker`.

- [ ] **Step 3: Implement `ThemePicker`**

Create `zendaya-hud-react/src/components/chrome/ThemePicker.tsx`:

```tsx
import type { CSSProperties } from "react";
import { useZendaya } from "../../store/zendayaStore";
import { THEME_ORDER, THEMES } from "../../themes/registry";

export default function ThemePicker() {
  const active = useZendaya((s) => s.activeThemeId);
  const setTheme = useZendaya((s) => s.setTheme);

  return (
    <div className="zen-theme-picker" role="group" aria-label="Theme picker">
      {THEME_ORDER.map((id) => {
        const t = THEMES[id];
        const isActive = id === active;
        return (
          <button
            key={id}
            type="button"
            className={"zen-theme-dot" + (isActive ? " active" : "")}
            aria-label={t.name}
            aria-current={isActive}
            title={t.name}
            style={{ "--dot": t.primary } as CSSProperties}
            onClick={() => setTheme(id)}
          />
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/__tests__/ThemePicker.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/components/chrome/ThemePicker.tsx zendaya-hud-react/src/__tests__/ThemePicker.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): ThemePicker — on-screen theme switcher dots"
```

---

### Task 6: `RingChrome` (Forge) SVG

**Files:**
- Create: `zendaya-hud-react/src/components/chrome/RingChrome.tsx`
- Test: covered by `ChromeFrame.test.tsx` in Task 8 (renders `data-testid="ring-chrome"`). No standalone test — this is a pure-visual component; its contract is "renders an SVG tagged `ring-chrome` using theme CSS vars".

- [ ] **Step 1: Implement `RingChrome`**

Create `zendaya-hud-react/src/components/chrome/RingChrome.tsx`:

```tsx
import type { CSSProperties } from "react";

const ORIGIN: CSSProperties = { transformOrigin: "200px 200px" };

export default function RingChrome() {
  const ticks = Array.from({ length: 60 });
  return (
    <svg
      className="zen-ring-chrome"
      data-testid="ring-chrome"
      viewBox="0 0 400 400"
      aria-hidden
    >
      {/* outer tick ring */}
      <g className="zen-rot" style={ORIGIN}>
        {ticks.map((_, i) => {
          const a = (i / ticks.length) * Math.PI * 2;
          const major = i % 5 === 0;
          const r1 = 186;
          const r2 = major ? 168 : 176;
          return (
            <line
              key={i}
              x1={200 + Math.cos(a) * r1}
              y1={200 + Math.sin(a) * r1}
              x2={200 + Math.cos(a) * r2}
              y2={200 + Math.sin(a) * r2}
              stroke="var(--zen-primary)"
              strokeWidth={major ? 2 : 1}
              opacity={0.5}
            />
          );
        })}
      </g>

      {/* thick segmented arc ring */}
      <circle
        className="zen-rot-slow"
        cx="200" cy="200" r="150" fill="none"
        stroke="var(--zen-primary)" strokeWidth="10"
        strokeDasharray="180 38 300 38 220 38"
        opacity="0.9"
        style={{ ...ORIGIN, filter: "drop-shadow(0 0 6px var(--zen-primary))" }}
      />

      {/* thinner inner arc ring */}
      <circle
        className="zen-rot-rev"
        cx="200" cy="200" r="120" fill="none"
        stroke="var(--zen-primary)" strokeWidth="4"
        strokeDasharray="300 60"
        opacity="0.7"
        style={ORIGIN}
      />

      {/* accent sweep */}
      <circle
        className="zen-rot"
        cx="200" cy="200" r="132" fill="none"
        stroke="var(--zen-accent)" strokeWidth="5"
        strokeDasharray="120 760"
        opacity="0.95"
        style={{ ...ORIGIN, filter: "drop-shadow(0 0 6px var(--zen-accent))" }}
      />
    </svg>
  );
}
```

- [ ] **Step 2: Type-check it compiles**

Run: `cd zendaya-hud-react && npx tsc --noEmit`
Expected: PASS (no type errors).

- [ ] **Step 3: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/components/chrome/RingChrome.tsx
git -c commit.gpgsign=false commit -m "feat(hud): RingChrome — Forge segmented-ring SVG chrome"
```

---

### Task 7: `ApertureChrome` (Iris) SVG

**Files:**
- Create: `zendaya-hud-react/src/components/chrome/ApertureChrome.tsx`
- Test: covered by `ChromeFrame.test.tsx` in Task 8 (renders `data-testid="aperture-chrome"`).

- [ ] **Step 1: Implement `ApertureChrome`**

Create `zendaya-hud-react/src/components/chrome/ApertureChrome.tsx`:

```tsx
import type { CSSProperties } from "react";

const ORIGIN: CSSProperties = { transformOrigin: "200px 200px" };

export default function ApertureChrome() {
  const blades = Array.from({ length: 12 });
  return (
    <svg
      className="zen-aperture-chrome"
      data-testid="aperture-chrome"
      viewBox="0 0 400 400"
      aria-hidden
    >
      {/* outer rim */}
      <circle
        cx="200" cy="200" r="160" fill="none"
        stroke="var(--zen-primary)" strokeWidth="2"
        opacity="0.85"
        style={{ filter: "drop-shadow(0 0 10px var(--zen-primary))" }}
      />

      {/* aperture blades */}
      <g className="zen-rot-slow" style={ORIGIN}>
        {blades.map((_, i) => {
          const a = (i / blades.length) * Math.PI * 2;
          const inner = 62;
          const outer = 150;
          return (
            <line
              key={i}
              x1={200 + Math.cos(a) * inner}
              y1={200 + Math.sin(a) * inner}
              x2={200 + Math.cos(a + 0.5) * outer}
              y2={200 + Math.sin(a + 0.5) * outer}
              stroke="var(--zen-primary)"
              strokeWidth="2"
              opacity="0.45"
            />
          );
        })}
      </g>

      {/* dashed rotating ring */}
      <circle
        className="zen-rot-rev"
        cx="200" cy="200" r="120" fill="none"
        stroke="var(--zen-primary)" strokeWidth="2"
        strokeDasharray="6 12"
        opacity="0.6"
        style={ORIGIN}
      />

      {/* pupil + glow */}
      <circle cx="200" cy="200" r="54" fill="none"
        stroke="var(--zen-primary)" strokeWidth="3"
        opacity="0.95"
        style={{ filter: "drop-shadow(0 0 12px var(--zen-primary))" }}
      />
      <circle cx="200" cy="200" r="6" fill="var(--zen-accent)"
        style={{ filter: "drop-shadow(0 0 8px var(--zen-accent))" }}
      />
    </svg>
  );
}
```

- [ ] **Step 2: Type-check it compiles**

Run: `cd zendaya-hud-react && npx tsc --noEmit`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/components/chrome/ApertureChrome.tsx
git -c commit.gpgsign=false commit -m "feat(hud): ApertureChrome — Iris aperture-eye SVG chrome"
```

---

### Task 8: `ChromeFrame` selector

**Files:**
- Create: `zendaya-hud-react/src/components/chrome/ChromeFrame.tsx`
- Test: `zendaya-hud-react/src/__tests__/ChromeFrame.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/ChromeFrame.test.tsx`:

```tsx
import { beforeEach, describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { useZendaya } from "../store/zendayaStore";
import ChromeFrame from "../components/chrome/ChromeFrame";

beforeEach(() => useZendaya.setState({ activeThemeId: "forge" }));

describe("ChromeFrame", () => {
  it("renders ring chrome for forge", () => {
    useZendaya.setState({ activeThemeId: "forge" });
    const { queryByTestId } = render(<ChromeFrame />);
    expect(queryByTestId("ring-chrome")).toBeTruthy();
    expect(queryByTestId("aperture-chrome")).toBeNull();
  });

  it("renders aperture chrome for iris", () => {
    useZendaya.setState({ activeThemeId: "iris" });
    const { queryByTestId } = render(<ChromeFrame />);
    expect(queryByTestId("aperture-chrome")).toBeTruthy();
    expect(queryByTestId("ring-chrome")).toBeNull();
  });

  it("always renders the theme picker", () => {
    const { getByLabelText } = render(<ChromeFrame />);
    expect(getByLabelText("Theme picker")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/__tests__/ChromeFrame.test.tsx`
Expected: FAIL — cannot resolve import `../components/chrome/ChromeFrame`.

- [ ] **Step 3: Implement `ChromeFrame`**

Create `zendaya-hud-react/src/components/chrome/ChromeFrame.tsx`:

```tsx
import { useZendaya } from "../../store/zendayaStore";
import { THEMES } from "../../themes/registry";
import RingChrome from "./RingChrome";
import ApertureChrome from "./ApertureChrome";
import ThemePicker from "./ThemePicker";

export default function ChromeFrame() {
  const id = useZendaya((s) => s.activeThemeId);
  const chrome = THEMES[id]?.chrome ?? "ring";

  return (
    <>
      <div className="zen-chrome-frame" aria-hidden>
        {chrome === "aperture" ? <ApertureChrome /> : <RingChrome />}
      </div>
      <ThemePicker />
    </>
  );
}
```

Note: only `ring` and `aperture` exist in Phase A; `gauge`/`radar` (Chronos/Recon) fall through to `RingChrome` until their components land in a later phase.

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/__tests__/ChromeFrame.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/components/chrome/ChromeFrame.tsx zendaya-hud-react/src/__tests__/ChromeFrame.test.tsx
git -c commit.gpgsign=false commit -m "feat(hud): ChromeFrame selects chrome by active theme + mounts picker"
```

---

### Task 9: App integration + CSS theming

**Files:**
- Modify: `zendaya-hud-react/src/App.tsx`
- Modify: `zendaya-hud-react/src/index.css`

- [ ] **Step 1: Add default theme vars + reskin existing chrome in `index.css`**

In `zendaya-hud-react/src/index.css`, replace the `:root { ... }` block (lines 7–15) with:

```css
:root {
  /* Theme defaults (Forge) — overridden at runtime by ThemeRoot inline vars */
  --zen-primary: #ff8a1e;
  --zen-accent: #19d3a0;
  --zen-bg-0: #1a0d05;
  --zen-bg-1: #070302;
  --zen-text-glow: #ffb060;
  --zen-grain: 0.18;

  --zen-bg: var(--zen-bg-1);
  --zen-text: rgba(255, 255, 255, 0.92);
  --zen-dim: rgba(255, 255, 255, 0.55);
  --zen-faint: rgba(255, 255, 255, 0.3);
}
```

Replace the `body::before` background (lines 36–48 area) gradient with a theme-driven one:

```css
body::before {
  content: "";
  position: fixed;
  inset: 0;
  background: radial-gradient(
    ellipse at center,
    color-mix(in srgb, var(--zen-primary) 10%, transparent) 0%,
    rgba(0, 0, 0, 0) 55%,
    rgba(0, 0, 0, 0.6) 100%
  );
  pointer-events: none;
  z-index: 0;
  transition: background 0.6s ease;
}
```

Replace the `.zen-wordmark` `text-shadow` (lines 60–63) with:

```css
  text-shadow:
    0 0 16px var(--zen-text-glow),
    0 0 38px color-mix(in srgb, var(--zen-primary) 60%, transparent),
    0 0 80px color-mix(in srgb, var(--zen-primary) 30%, transparent);
```

Replace `.zen-player-progress-fill` background (line 102) with:

```css
  background: linear-gradient(90deg, var(--zen-accent), var(--zen-primary));
```

Replace `.zen-player-btn.primary` background + box-shadow (lines 127, 130) with:

```css
  background: linear-gradient(135deg, var(--zen-accent), var(--zen-primary));
```
```css
  box-shadow: 0 8px 24px color-mix(in srgb, var(--zen-primary) 40%, transparent);
```

- [ ] **Step 2: Append chrome + picker CSS to `index.css`**

Append to the end of `zendaya-hud-react/src/index.css`:

```css
/* ---------- Theme engine layers ---------- */
.zen-theme-root {
  position: absolute;
  inset: 0;
}

.zen-chrome-frame {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
  z-index: 15;
}
.zen-ring-chrome,
.zen-aperture-chrome {
  width: min(78vh, 78vw);
  height: min(78vh, 78vw);
  opacity: 0.9;
}

@keyframes zen-rot { to { transform: rotate(360deg); } }
.zen-rot      { animation: zen-rot 26s linear infinite; }
.zen-rot-slow { animation: zen-rot 60s linear infinite; }
.zen-rot-rev  { animation: zen-rot 18s linear infinite reverse; }

.zen-theme-picker {
  position: absolute;
  bottom: 26px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 12px;
  pointer-events: auto;
  z-index: 30;
}
.zen-theme-dot {
  width: 16px;
  height: 16px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid rgba(255, 255, 255, 0.25);
  background: var(--dot);
  opacity: 0.55;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.2s;
  box-shadow: 0 0 8px var(--dot);
}
.zen-theme-dot:hover { opacity: 0.85; transform: scale(1.15); }
.zen-theme-dot.active {
  opacity: 1;
  transform: scale(1.25);
  outline: 2px solid rgba(255, 255, 255, 0.5);
  outline-offset: 2px;
}
```

- [ ] **Step 3: Wire `ThemeRoot` + `ChromeFrame` into `App.tsx`**

In `zendaya-hud-react/src/App.tsx`, add these imports after the existing component imports (after line 6 `import ModuleHost ...`):

```tsx
import ThemeRoot from "./themes/ThemeRoot";
import ChromeFrame from "./components/chrome/ChromeFrame";
```

Wrap the returned tree in `<ThemeRoot>`: change the opening `return (` block so the outermost element is `ThemeRoot`. Replace the existing `return ( <div className="relative w-full h-full bg-black"> ... </div> );` so it reads:

```tsx
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
            <MainScene />
            <EffectComposer enableNormalPass={false}>
              <Bloom
                intensity={0.55}
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
      </div>
    </ThemeRoot>
  );
```

- [ ] **Step 4: Type-check + full suite**

Run: `cd zendaya-hud-react && npx tsc --noEmit && npm test`
Expected: PASS — tsc clean; all test files green (existing suite + the new theme tests).

- [ ] **Step 5: Manual visual check**

Run: `cd zendaya-hud-react && npm run dev`, open the served URL. Expected:
- The Forge ring chrome is visible around the orb, glowing amber, slowly rotating.
- Two theme dots (amber, cyan) sit bottom-center.
- Clicking the cyan dot switches the whole HUD to Iris: chrome becomes the aperture eye, background/wordmark/player glow shift to cyan, accent to red. Clicking amber switches back. The transition is a smooth cross-fade.

- [ ] **Step 6: Commit**

```bash
git -c commit.gpgsign=false add zendaya-hud-react/src/App.tsx zendaya-hud-react/src/index.css
git -c commit.gpgsign=false commit -m "feat(hud): mount ThemeRoot + ChromeFrame; theme HUD chrome via CSS vars"
```

---

### Task 10: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full type-check + build**

Run: `cd zendaya-hud-react && npm run build`
Expected: `tsc --noEmit` clean, `vite build` succeeds with no errors.

- [ ] **Step 2: Full test suite**

Run: `cd zendaya-hud-react && npm test`
Expected: every test file passes — the pre-existing suite plus the 5 new files (`themeRegistry`, `themeStore`, `ThemeRoot`, `ThemePicker`, `ChromeFrame`) and the extended `useWebSocket` tests. No failures, no unhandled errors.

- [ ] **Step 3: Confirm protected files untouched**

Run: `git status --short`
Expected: the five protected files (`.gitignore`, `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `zendaya_logs/assistant_history.json`) still show as ` M` (modified, unstaged). No `backend/` or root-config file appears staged in any Phase-A commit.

- [ ] **Step 4: Confirm the deliverable**

Phase A is complete when: the HUD shows themed SVG chrome around the (unchanged) orb; the theme picker switches Forge⇄Iris live; a WebSocket `{action:"set_theme", payload:{name:"iris"}}` message also switches the theme; and the whole HUD's palette (chrome, background, wordmark, music player) follows the active theme. The 3D stage is still the current orb — themed 3D scenes arrive in Phase B.

---

## Self-Review

**1. Spec coverage (against `docs/superpowers/specs/2026-06-01-hud-hologram-redesign-design.md`):**
- §2 decisions → reflected (voice + picker switching via Tasks 3+5; full-skin tokens via Task 1).
- §4 `themes/types.ts`, `registry.ts`, `ThemeRoot.tsx` → Tasks 1, 4. `chrome/ChromeFrame/RingChrome/ApertureChrome/ThemePicker` → Tasks 5–8. Store + websocket extensions → Tasks 2, 3. `App.tsx` + `index.css` → Task 9.
- §5 token schema + Forge/Iris bundles → Task 1 (verbatim).
- §6 store extensions → Task 2. §7 switching → Tasks 3, 5. §8 chrome → Tasks 6–8. §12 testing items (registry integrity, store logic, action routing, token→CSS-var) → Tasks 1–5, 8.
- **Deliberately deferred to later-phase plans (noted in File Structure):** `useThemeColors` (Phase B, §3), scene system/`SceneManager`/scenes/`DissolveField` (Phase B, §9), `Atmosphere` grain/scanlines (Phase B, §10), `GaugeChrome`/`RadarChrome` (Phase C), inline-styled `TelemetryWidget`/`PerceptionIndicator` reskin (Phase C). §12 "scene routing" test belongs to Phase B with `SceneManager`. No Phase-A spec requirement is left unimplemented.

**2. Placeholder scan:** none — every code step contains complete, runnable code; every command has an expected result.

**3. Type/name consistency:** `ThemeTokens`/`ChromeStyle` (Task 1) are used identically in `registry.ts`, `ThemeRoot.tsx`, and tests. CSS var names (`--zen-primary`, `--zen-accent`, `--zen-bg-0`, `--zen-bg-1`, `--zen-text-glow`, `--zen-grain`) match across `themeCssVars` (Task 4), `index.css` (Task 9), and the chrome SVGs (Tasks 6–7). Store members `activeThemeId`/`setTheme`/`cycleTheme` match across Tasks 2, 3, 5 and all tests. `data-testid` values `ring-chrome`/`aperture-chrome` match between Tasks 6/7 and the ChromeFrame test (Task 8). `THEME_ORDER = ["forge","iris"]` is consistent with the `cycleTheme` wrap test.

---

## Execution Handoff

After this plan is saved, execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task with two-stage review (spec compliance then code quality) between tasks.
2. **Inline Execution** — execute tasks in this session with checkpoints.

Phase B (scene engine + orb→globe cinematic transform + Atmosphere) and Phase C (weather/clock scenes + chrome polish + widget reskin + per-theme ambient) will each get their own plan after Phase A lands.
