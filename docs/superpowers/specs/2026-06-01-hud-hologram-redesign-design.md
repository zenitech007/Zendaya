# Zendaya HUD — Holographic Theme-Engine Redesign

**Date:** 2026-06-01
**Status:** Approved (design) — ready for implementation planning
**Scope:** `zendaya-hud-react/` visual layer only. Backend (`zendaya_state_server`, intents) is unchanged except optionally emitting a new `set_theme` action.

---

## 1. Goal

Replace the current single-look Zendaya HUD with a **themeable holographic interface** inspired by sci-fi movie HUDs (F.R.I.D.A.Y. / JARVIS). The HUD becomes a stack of layers driven by a **Theme Engine**: the user switches between named visual themes (by voice or an on-screen picker), and voice intents like *"show me the world map"* transform the 3D center stage into a 3D scene (a globe) with cinematic transitions.

This is a **re-skin, not a re-plumb**. All functional infrastructure — WebSocket, Zustand store, intent routing, audio engine, Python backend — is kept and extended, never replaced.

---

## 2. Design Decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| Teardown depth | Re-skin only — keep all plumbing, rebuild the visual layer |
| Aesthetic direction | F.R.I.D.A.Y.-style concentric-ring HUD chrome + 3D center stage |
| Architecture | **Layered Hologram** — true-3D center stage (R3F) + crisp SVG/CSS themeable chrome overlay |
| Theme switching | **Voice + on-screen picker** (both) |
| Theme depth | **Full skin** — palette + chrome style + background + ambient mood; 3D scenes inherit theme colors but keep structure |
| v1 theme count | **Two** contrasting themes (Forge + Iris); others drop in later |
| Hero scenes | Idle orb, World map/globe, Weather, Clock (plus remaining modules reskinned) |

---

## 3. Architecture — "Layered Hologram"

Three stacked layers, all fed by one Theme Engine:

```
┌─────────────────────────────────────────────┐
│ Layer 3 · CHROME        (DOM / SVG)          │  rings · gauges · radar · aperture
│                                              │  telemetry · perception · music · picker
├─────────────────────────────────────────────┤
│ Layer 2 · 3D STAGE      (Three.js / R3F)     │  orb → globe → weather → clock
│                                              │  cinematic transitions · bloom
├─────────────────────────────────────────────┤
│ Layer 1 · ATMOSPHERE    (CSS / shader)       │  bg gradient · grain · scanlines · vignette
└─────────────────────────────────────────────┘
                 ▲ tokens feed all three ▲
        ┌──────────────────────────────────────┐
        │ THEME ENGINE                          │
        │  primary · accent · bg · chrome style │
        │  scene tint · bloom · ambient · grain │
        └──────────────────────────────────────┘
          ▲ Voice "switch to Iris"  +  on-screen picker
        ┌──────────────────────────────────────┐
        │ KEPT UNTOUCHED (plumbing)             │
        │  WebSocket · store · intents · audio  │
        │  · Python backend                     │
        └──────────────────────────────────────┘
```

**Token flow on a theme switch:**
1. `setTheme(id)` / `cycleTheme()` updates `activeThemeId` in the store.
2. `<ThemeRoot>` writes the active theme's tokens to **CSS custom properties** → the Chrome + Atmosphere layers re-skin instantly (with a short CSS transition for a smooth cross-fade).
3. `useThemeColors()` hands `THREE.Color`s to the 3D stage; on change the scene materials' color uniforms are **GSAP-tweened** so the 3D melts from one palette to the next.

---

## 4. Component Units & File Structure

New / changed files under `zendaya-hud-react/src/`:

| Unit | Responsibility |
| --- | --- |
| `themes/types.ts` | `ThemeTokens` interface + the `ChromeStyle` union. |
| `themes/registry.ts` | `THEMES: Record<string, ThemeTokens>` + `THEME_ORDER: string[]`. Adding a theme = adding one object. |
| `themes/ThemeRoot.tsx` | Reads `activeThemeId`, writes tokens → CSS variables on a wrapper element; sets up the cross-fade transition. |
| `themes/useThemeColors.ts` | Hook returning memoized `THREE.Color`s for the active theme, for 3D materials. |
| `store/zendayaStore.ts` *(extend)* | Add `activeThemeId`, `setTheme(id)`, `cycleTheme()`; default `"forge"`. |
| `hooks/useWebSocket.ts` *(extend)* | Add `set_theme` action → `setTheme(payload.name)` guarded by registry membership. |
| `components/chrome/ChromeFrame.tsx` | Picks the chrome component by `tokens.chrome`. |
| `components/chrome/RingChrome.tsx` | Forge: concentric segmented rings + ticks + accent sweep (SVG). |
| `components/chrome/ApertureChrome.tsx` | Iris: aperture/eye rings + circuit grain (SVG). |
| `components/chrome/GaugeChrome.tsx` / `RadarChrome.tsx` | Stubs for Chronos / Recon (later phase). |
| `components/chrome/ThemePicker.tsx` | Dock control: theme dots, click to switch; voice-compatible. |
| `components/Atmosphere/Atmosphere.tsx` | Background gradient + grain + scanlines + vignette from tokens. |
| `scenes/SceneManager.tsx` | Replaces `MainScene`; mounts the active 3D scene with enter/exit transitions. |
| `scenes/IdleOrbScene.tsx` | Themed resting orb (replaces `Orb/Orb.tsx`). |
| `scenes/GlobeScene.tsx` | Themed 3D globe (replaces `MapModule/MapModule.tsx`; fixes the latent `opacity`→`uOpacity` shader bug). |
| `scenes/WeatherScene.tsx` / `ClockScene.tsx` | Themed weather + clock scenes (later phase). |
| `scenes/DissolveField.tsx` | Reusable particle field that morphs orb↔globe point clouds on a GSAP progress uniform. |
| `App.tsx` *(rewrite composition)* | `<ThemeRoot>` wraps: `<Atmosphere/>`, the R3F `<Canvas>` with `<SceneManager/>` + Bloom, and the `<ChromeFrame/>` + HUD + `<ThemePicker/>` overlay. |

**Reskinned (logic unchanged, read theme CSS vars):** `components/HUD/TelemetryWidget.tsx`, `PerceptionIndicator.tsx`, `MusicPlayer.tsx`, `Hud.tsx`.

**Kept untouched:** all of `systems/` (audio), `hooks/useBodyAction.ts`, `hooks/useAdaptiveQuality.ts`, `hooks/useAudioEngine.ts`, `store/normaliseVisemes.ts`, Python backend.

---

## 5. Theme Token Schema

```ts
// themes/types.ts
export type ChromeStyle = "ring" | "aperture" | "gauge" | "radar";

export interface ThemeTokens {
  id: string;            // "iris"
  name: string;          // "Iris"
  // palette
  primary: string;       // main chrome + glow color (hex)
  accent: string;        // accent sweep / highlight (hex)
  bg: [string, string];  // radial background stops [inner, outer]
  textGlow: string;      // wordmark/caption glow color
  // 3D stage
  sceneColor: string;    // tint for orb/globe/scenes (often == primary)
  bloom: number;         // bloom intensity multiplier (e.g. 0.8–1.6)
  // chrome + atmosphere
  chrome: ChromeStyle;   // which chrome component renders
  ambient: string;       // ambient audio pad id
  grain: number;         // 0–1 background grain/scanline amount
}
```

### v1 themes (`themes/registry.ts`)

```ts
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
export const THEME_ORDER = ["forge", "iris"];
```

`registry.ts` is the single source of truth. Future themes (Chronos, Recon, the user's other ideas) are added here plus a matching chrome component if they introduce a new `chrome` style.

---

## 6. Store Extensions

```ts
// added to ZendayaState
activeThemeId: string;            // default "forge"
setTheme: (id: string) => void;   // no-op if id ∉ THEMES
cycleTheme: () => void;           // advances through THEME_ORDER, wraps
```

`setTheme` validates membership against `THEMES` before committing (ignore unknown ids). `cycleTheme` finds the current index in `THEME_ORDER` and advances modulo length.

---

## 7. Theme Switching

**Voice:** `hooks/useWebSocket.ts` `dispatchAction` gains a case:
```ts
case "set_theme": {
  const name = typeof payload.name === "string" ? payload.name : "";
  z.setTheme(name);     // setTheme guards against unknown ids
  break;
}
```
The backend can map an intent ("switch to iris" / "change theme to forge") to `{action:"set_theme", payload:{name:"iris"}}`. (Backend intent wiring is out of scope for this spec but the channel is ready.)

**On-screen:** `ThemePicker.tsx` renders one dot per `THEME_ORDER` entry (colored by each theme's `primary`), highlights `activeThemeId`, and calls `setTheme(id)` on click. A cycle affordance calls `cycleTheme()`.

---

## 8. Chrome Layer

SVG-based for crisp arcs/ticks/text at any DPI. All colors come from CSS variables set by `ThemeRoot` (`var(--zen-primary)`, `var(--zen-accent)`, etc.), so a theme switch reskins chrome with a CSS transition and **no React re-mount**.

- `ChromeFrame.tsx` selects the component from `tokens.chrome`:
  - `"ring"` → `RingChrome` (Forge): outer tick ring, segmented rotating arcs, accent sweep, glowing center wordmark — the F.R.I.D.A.Y. look.
  - `"aperture"` → `ApertureChrome` (Iris): concentric aperture "eye" rings, dashed rotating ring, circuit-grain frame.
  - `"gauge"` / `"radar"` → stubs returning a minimal frame (filled in a later phase).
- `TelemetryWidget`, `PerceptionIndicator`, `MusicPlayer`, `Hud` change only their hard-coded colors to `var(--zen-*)`; behavior, data flow, and tests stay intact.

---

## 9. Scene System & Transitions (3D Stage)

- `SceneManager.tsx` replaces `MainScene`. It maps store state → an active scene id:
  - default / no module → `idle`
  - `scene === "map"` or `activeModule === "map"` → `globe`
  - weather intent → `weather`; clock intent → `clock`
- It mounts the active scene and runs an **enter/exit transition** between the outgoing and incoming scene.
- Each scene (`IdleOrbScene`, `GlobeScene`, `WeatherScene`, `ClockScene`) is an R3F component that reads colors from `useThemeColors()`.

**The cinematic transform (orb → globe):**
- `DissolveField.tsx` holds a particle system with two target point clouds — the orb surface and the globe surface — and a `uProgress` uniform (0 = orb, 1 = globe).
- A GSAP timeline drives `uProgress` 0→1: the orb scatters into particles that reform as the rotating 3D globe; a bloom flash punctuates the midpoint; the chrome rings sweep open (CSS class toggled via store).
- Reverse (globe → orb) runs the timeline 1→0.

---

## 10. Atmosphere Layer

`Atmosphere.tsx` renders a full-viewport background behind the Canvas:
- radial gradient from `var(--zen-bg-0)` → `var(--zen-bg-1)`,
- a grain/scanline overlay whose opacity = `var(--zen-grain)`,
- a vignette.

The existing mood→`bgDim` effect (in `Hud.tsx`) continues to modulate overall dimness on top of the theme background.

---

## 11. Keep vs. Replace (summary)

**Keep / extend:** `store/zendayaStore.ts` (+theme slice), `hooks/useWebSocket.ts` (+`set_theme`), `systems/*` (audio), `useBodyAction`, `useAdaptiveQuality`, `useAudioEngine`, `normaliseVisemes`, backend.

**Replace / rewrite:** `Orb/Orb.tsx` → `IdleOrbScene`; `MapModule/MapModule.tsx` → `GlobeScene` (fix `opacity`→`uOpacity`); `scenes/MainScene.tsx` → `SceneManager`; module visuals reskinned; `App.tsx` composition; HUD components reskinned to tokens; shader files refactored under the themed system.

---

## 12. Testing (Vitest + happy-dom)

- **Registry integrity:** every theme in `THEMES` has all required token fields and a valid `chrome` value; `THEME_ORDER` ids all exist in `THEMES`.
- **Store logic:** `setTheme("iris")` sets `activeThemeId`; `setTheme("nope")` is a no-op; `cycleTheme()` advances and wraps across `THEME_ORDER`.
- **Action routing:** a `{action:"set_theme", payload:{name:"iris"}}` WS message results in `activeThemeId === "iris"`; unknown name leaves it unchanged.
- **Scene routing:** given store state, `SceneManager`'s scene-selection function returns the expected scene id (`idle` / `globe` / `weather` / `clock`).
- **Token resolution:** `ThemeRoot` sets the expected CSS variables for the active theme.
- R3F visuals (particle dissolve, bloom, globe) are smoke-tested manually.

---

## 13. Phasing

**Phase A — Theme foundation.** `themes/types.ts` + `registry.ts` (Forge + Iris) + store slice + `ThemeRoot` CSS vars + `set_theme` action + `ThemePicker` + reskin existing DOM HUD (Telemetry/Perception/Music/Hud) to tokens. *Deliverable: a switchable, themed HUD over the current orb.*

**Phase B — Scene engine + hero transition.** `SceneManager` + themed `IdleOrbScene` + `GlobeScene` + `DissolveField` orb→globe particle dissolve + `Atmosphere`. *Deliverable: the flagship "show me the world map" cinematic transform.*

**Phase C — More scenes + chrome.** `WeatherScene`, `ClockScene`, full `RingChrome` + `ApertureChrome` polish, remaining modules reskinned, per-theme ambient audio wiring. *Deliverable: full hero-scene coverage and chrome fidelity.*

Each phase produces a working, testable HUD on its own.

---

## 14. Out of Scope (v1)

- Chronos / Recon chrome styles (stubs only; design proven so they drop in later).
- Backend intent → `set_theme` mapping (the frontend channel is ready; backend wiring is a separate change).
- Fully volumetric (in-WebGL) chrome — possible future upgrade from approach ②.
- New audio engine work beyond wiring existing ambient pads to themes.
