# Zendaya HUD — Phase C: Scenes, Chrome Reactions & Polish

**Date:** 2026-06-02
**Status:** Approved (design) — ready for implementation planning
**Scope:** `zendaya-hud-react/src/` visual layer only. **No backend / Python / config changes.** Builds on the approved redesign spec `2026-06-01-hud-hologram-redesign-design.md` (Phases A + B shipped).

---

## 1. Goal

Complete the holographic HUD redesign by delivering the two remaining hero scenes (**WeatherScene**, **ClockScene**), making the SVG **chrome react to scene changes**, finishing the **theme-token polish** on the surviving 2D panels, giving each theme its **own ambient audio character**, and **pruning** the dead pre-redesign code.

Like Phases A/B this is a **re-skin, not a re-plumb**: WebSocket, Zustand store, intent routing, the audio engine, and the Python backend are kept and extended, never replaced. Both new scenes bind to **real data with zero backend edits** — weather via the existing client-side fetch (ipapi + Open-Meteo), clock via `new Date()`.

---

## 2. Design Decisions (locked during brainstorming)

| Decision | Choice |
| --- | --- |
| Phase C scope | **All six** backlog pieces, in **one** Phase C spec |
| Weather/Clock presentation | **Full cinematic morph** — the orb *becomes* the scene; the 2D Weather & Clock panels are **retired**; data shown as floating holographic readouts |
| WeatherScene rendering | **Particle morph** — the Phase B `DissolveField` particle engine retargets to a condition form |
| ClockScene rendering | **Three faces** — Orbital (default), Digits, Analog — user-switchable |
| Clock face switching | **Switcher dots** (theme-picker style), visible only while the clock scene is active; choice persisted |
| Chrome scene-change reaction | **Switcher** between three behaviors — Aperture pulse (default), Spin+flash, Radar sweep; persisted; independent of the theme's chrome *shape* |
| Ambient audio | **Per-theme synth variation** of the existing `AmbientEngine` — no audio files |
| Build order | Low-risk → high-risk: prune → reskins → audio → chrome → ClockScene → WeatherScene |

---

## 3. Architecture fit

Phase C adds no new layers — it fills in the existing three-layer Hologram stack:

- **Layer 2 · 3D Stage** gains `WeatherScene` and `ClockScene`, both driven by the same `SceneManager` + `progressRef` morph machinery that already powers `idle ↔ globe`.
- **Layer 3 · Chrome** gains a scene-change *reaction* (the frame animates when the stage morphs) plus the final token-color cleanup on the surviving DOM panels.
- **Theme Engine** gains an audio dimension: the active theme now also shapes the ambient synth.

**Scene routing extension** (`scenes/SceneManager.tsx`), from `"idle" | "globe"` to four ids:

```ts
export type SceneId = "idle" | "globe" | "weather" | "clock";

export function selectScene(s: { scene: string; activeModule: string }): SceneId {
  if (s.scene === "map" || s.activeModule === "map") return "globe";
  if (s.activeModule === "weather") return "weather";
  if (s.activeModule === "clock") return "clock";
  return "idle";
}
```

The backend already broadcasts `open_module` with `name: "weather" | "clock" | "map"` → `setActiveModule(...)`. No backend change is needed for routing; `selectScene` simply maps the existing store state to the new scene ids. Any non-`idle` scene hides the resting wordmark (same rule the globe already follows).

---

## 4. Component Units & File Structure

New / changed files under `zendaya-hud-react/src/`:

| Unit | Status | Responsibility |
| --- | --- | --- |
| `scenes/SceneManager.tsx` | extend | `selectScene` → 4 ids; mount `WeatherScene` / `ClockScene`; drive their enter/exit via the existing `progressRef` morph (0↔1, 1.2 s, power3.inOut). |
| `scenes/WeatherScene.tsx` | new | Particle scene; morphs the orb cloud into the active condition form; reads `useWeather()` + `useThemeColors()`. |
| `scenes/weatherForms.ts` | new | Point-cloud generators per condition form (clear / clouds / rain / snow / storm / fog), built on the Phase B point-cloud math module. |
| `hooks/useWeather.ts` | new | Lifts the fetch out of `Weather.tsx` (ipapi geo + Open-Meteo current). Returns `{ tempC, code, windKph, humidity, city, form, loading, error }`; cached, ~10-min refresh, shared by scene + readout. |
| `components/HUD/WeatherReadout.tsx` | new | Floating holographic readout (temp / condition / city / wind / humidity), theme-tinted, no boxed panel. Shown only on the weather scene. |
| `scenes/ClockScene.tsx` | new | Hosts the three faces; reads `clockFace` from store, live `Date` (1 s tick), `useThemeColors()`; crossfades on face switch. |
| `scenes/clock/OrbitalFace.tsx` | new | Three tilted orbital rings (H/M/S) with sweeping nodes, particle-traced; time at centre. |
| `scenes/clock/DigitsFace.tsx` | new | Particle `HH:MM` glyphs + sweeping seconds arc. |
| `scenes/clock/AnalogFace.tsx` | new | Tilted 3D dial with beam hands (line geometry). |
| `components/HUD/ClockReadout.tsx` | new | Small digital time + date line for the Orbital/Analog faces (Digits face shows its own). |
| `components/HUD/ClockFacePicker.tsx` | new | Theme-picker-style dot row (Orbital / Digits / Analog); visible only when the clock scene is active; calls `setClockFace`. |
| `components/chrome/ChromeFxPicker.tsx` | new | Small dot/icon cluster beside the `ThemePicker`; picks the chrome reaction (`aperture` / `spin` / `radar`); calls `setChromeFx`. |
| `components/chrome/chromeFx.ts` | new | The three reaction animations as progress-/GSAP-driven functions, shared by `RingChrome` + `ApertureChrome`. Exposes `MORPH_MS = 1200`. |
| `components/chrome/RingChrome.tsx` | extend | Plays the selected `chromeFx` on scene-id change; otherwise unchanged. |
| `components/chrome/ApertureChrome.tsx` | extend | Same reaction hookup. |
| `store/zendayaStore.ts` | extend | Add `clockFace` + `setClockFace`, `chromeFx` + `setChromeFx`; both seeded from and written to `localStorage`. |
| `systems/` audio (`AmbientEngine`) + `hooks/useAudioEngine.ts` | extend | Accept the active theme and shape the synth (base freq / harmonic mix / filter) per theme, crossfading on change. Driven by `themes/registry` tokens. |
| `themes/registry.ts` / `types.ts` | extend (small) | Add per-theme ambient synth params if the existing `ambient` id isn't enough to express timbre. |
| `components/Modules/ModulePanel.tsx` | reskin | Replace hard-coded Forge oranges with `var(--zen-primary)` / `var(--zen-accent)`. |
| `components/Modules/Notes.tsx` | reskin | Same token migration. |
| `components/HUD/MusicPlayer.tsx` | reskin | Replace the hard-coded pink/purple gradient + fallbacks with theme vars. |
| `src/index.css` | reskin | `.zen-player-card`, `.zen-player-btn(:hover/.primary)` purple literals → `var(--zen-*)`. |
| `components/Modules/ModuleHost.tsx` | edit | Stop routing `weather` / `clock` to 2D panels (scenes own them now); keep `notes` / `calculator`. |
| `components/Modules/Weather.tsx` | **delete** | Retired (scene replaces it; fetch lifted to `useWeather`). |
| `components/Modules/Clock.tsx` | **delete** | Retired (scene replaces it). |
| `src/animations/` (`easing.ts`, `transitions.ts`, `timelines.ts`, `index.ts`) | **delete** | Confirmed dead — nothing imports it. |

**Kept untouched:** `IdleOrbScene`, `GlobeScene`, `DissolveField` (reused), `Atmosphere`, `ThemeRoot`, `ThemePicker`, `useThemeColors`, `useWebSocket`, `useAdaptiveQuality`, `useBodyAction`, `normaliseVisemes`, the Calculator/Notes module logic, the Python backend.

---

## 5. Store extensions

```ts
// added to ZendayaState
clockFace: "orbital" | "digits" | "analog";   // default from localStorage ?? "orbital"
setClockFace: (f: ClockFace) => void;          // sets + persists to localStorage

chromeFx: "aperture" | "spin" | "radar";       // default from localStorage ?? "aperture"
setChromeFx: (fx: ChromeFx) => void;           // sets + persists to localStorage
```

Both are pure UI preferences, seeded from `localStorage` at store creation and written back on set. They never come from the backend.

---

## 6. WeatherScene (particle morph)

**Data** — `useWeather()` reuses the exact pipeline from the retired panel: `ipapi.co/json` for lat/lon/city, then Open-Meteo `current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m`. The WMO `weather_code` is mapped to a **form** by `wmoToForm(code)`:

| Form | WMO codes | Particle behavior |
| --- | --- | --- |
| `clear` | 0, 1 | Radiant sun-disc + slow ray shimmer |
| `clouds` | 2, 3 | Drifting cloud volume (turbulent noise) |
| `fog` | 45, 48 | Diffuse low-contrast haze |
| `rain` | 51, 61, 63, 65, 80 | Cloud volume + downward particle streaks |
| `snow` | 71 | Slow drifting flakes |
| `storm` | 95 | Turbulent cloud + periodic bloom flash |

**Render** — WeatherScene is a `DissolveField`-style particle system: on enter, `progressRef` morphs the **orb point cloud → the active form's point cloud** (generated in `weatherForms.ts` from the Phase B point-cloud math). While the scene stays active and the condition changes, it retargets to the new form. On exit it reverses to the orb. All particle color comes from `useThemeColors()`. The **`WeatherReadout`** overlay shows temp/condition/city/wind/humidity as free-floating glowing text (theme-tinted), with loading/error states.

---

## 7. ClockScene (three faces + switcher)

ClockScene reads the live `Date` (1 s interval), `useThemeColors()`, and `clockFace` from the store, and renders one of three faces:

- **OrbitalFace** (default) — three tilted orbital rings (hours/minutes/seconds); a glowing node sweeps each ring to the current value; live time glows upright at the centre; rings are particle-traced (shared DNA with the weather morph).
- **DigitsFace** — large particle `HH:MM` glyphs wrapped by a thin seconds arc that sweeps once a minute.
- **AnalogFace** — the current analog dial lifted into tilted 3D with beam-like hands (line geometry).

`ClockFacePicker` (a theme-picker-style dot row, **only visible while the clock scene is active**) calls `setClockFace`, persisted to `localStorage`. Switching faces crossfades (short opacity/scale tween) rather than hard-cutting. `ClockReadout` provides the digital time + date line under the Orbital/Analog faces.

---

## 8. Chrome reaction (switchable)

The chrome frame reacts when the 3D stage morphs to a new scene. Three behaviors live in `chromeFx.ts`, selected by the store's `chromeFx` and persisted:

- **`aperture`** (default) — rings contract inward, then reopen, timed to `MORPH_MS` (1200 ms).
- **`spin`** — rings briefly accelerate rotation and flare brighter, then settle.
- **`radar`** — a bright arc sweeps once around the frame, lighting ticks as it passes.

This is **orthogonal to the theme's chrome shape**: it applies to both `RingChrome` (Forge) and `ApertureChrome` (Iris). Mechanism: `ChromeFrame`/the active chrome component derives the current scene id via `selectScene(store)`; on a change it runs the selected `chromeFx` over `MORPH_MS`. No new backend signal and no React re-mount — the existing idle rotation continues underneath.

---

## 9. Per-theme ambient audio

`AmbientEngine` is fully synthetic (Web Audio oscillators) and currently theme-agnostic. Phase C feeds it the active theme so each theme has a distinct timbre:

- **Forge** → warmer/lower (lower base frequency, heavier low harmonic, gentler filter) to match the warm orange palette.
- **Iris** → airier/higher (higher partials, more shimmer, brighter filter) to match the cool cyan palette.

On theme change the synth parameters **crossfade** (no clicks). The per-theme values come from the theme tokens (extending `ThemeTokens` with optional ambient-synth params if the existing `ambient` string id is insufficient). **No audio files are introduced** — this stays within the existing engine, honoring the redesign spec's "no new audio engine work beyond wiring ambient to themes."

---

## 10. Module reskins

Migrate the remaining hard-coded colors to theme CSS variables so the surviving panels recolor with Forge/Iris:

- `components/Modules/ModulePanel.tsx` — border `rgba(255,138,60,.35)`, title `#ff8a3c`, close button → `var(--zen-primary)` / `var(--zen-accent)`.
- `components/Modules/Notes.tsx` — `rgba(255,138,60,.55)` → `var(--zen-primary)`.
- `components/HUD/MusicPlayer.tsx` — hard-coded `linear-gradient(135deg, #ec4899, #a855f7)` and fallbacks → theme gradient (`var(--zen-accent)` → `var(--zen-primary)`).
- `src/index.css` — `.zen-player-card` purple border/glow, `.zen-player-btn:hover` and `.primary` purple → `var(--zen-*)`.

Weather/Clock are **not** reskinned — they're deleted. Calculator/Notes keep their logic; only colors change.

---

## 11. Prune dead code

- Delete `src/animations/` (`easing.ts`, `transitions.ts`, `timelines.ts`, `index.ts`) — verified unimported anywhere in `src/`.
- Delete `components/Modules/Weather.tsx` and `components/Modules/Clock.tsx` and remove their entries from `ModuleHost`.
- Sweep for any other orphans surfaced while implementing (only delete files with zero importers).

---

## 12. Testing (Vitest + happy-dom)

- **Scene routing:** `selectScene` returns `idle` / `globe` / `weather` / `clock` for the matching store states (extends the existing Phase B test).
- **Weather mapping:** `wmoToForm(code)` returns the correct form for representative codes in every bucket (clear/clouds/fog/rain/snow/storm), with a sane default for unknown codes.
- **Store prefs:** `setClockFace` / `setChromeFx` update state and write `localStorage`; store seeds from `localStorage` on init; invalid stored values fall back to defaults.
- **Ambient mapping:** the theme→synth-param mapping returns distinct, in-range params for Forge vs Iris.
- **Reskin guard (optional):** assert the migrated components/CSS no longer contain the retired purple literal `168, 85, 247`.
- **3D visuals** (particle morphs, faces, chrome reactions, audio timbre) are **smoke-tested live** via the preview-MCP store-injection harness, scene by scene.

---

## 13. Phase C build order

Each step lands a working, tested HUD:

1. **Prune** — delete `animations/` + retired panels; confirm build + tests green. *(Lowest risk; clears the deck.)*
2. **Reskins** — migrate panel/CSS colors to tokens; verify both themes recolor cleanly.
3. **Ambient audio** — per-theme synth shaping + crossfade.
4. **Chrome reaction** — `chromeFx.ts` + `ChromeFxPicker` + store slice; wire into both chrome components.
5. **ClockScene** — three faces + `ClockFacePicker` + readout + routing.
6. **WeatherScene** — `useWeather` + `weatherForms` + particle scene + readout + routing. *(Signature finale.)*

---

## 14. Working constraints (carried from Phases A/B)

- All work lives under `zendaya-hud-react/src/` (+ this `docs/` spec). **No** edits to `backend/`, Python, `pyproject.toml`, `.gitignore`, or other config.
- Never touch/stage/commit the protected paths: `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`.
- Leave the pre-existing uncommitted working-tree diff alone; never `git add -A` / `.` / `-u`. Stage only the files named in each task.
- All commits disable signing: `git -c commit.gpgsign=false commit ...`. After each commit, run `git status` and confirm no protected paths were swept in.

---

## 15. Out of scope (Phase C)

- New themes beyond Forge + Iris (registry is ready for them).
- Backend intent → scene/`set_theme` wiring (frontend channel already exists).
- Fully volumetric (in-WebGL) chrome.
- File-based / sampled ambient audio (synth-only this phase).
- A weather *forecast* timeline (current conditions only).
