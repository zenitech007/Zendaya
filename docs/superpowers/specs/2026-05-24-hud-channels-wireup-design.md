# HUD Channels Wire-up — Design

**Date:** 2026-05-24
**Status:** Approved (pending spec review)
**Author:** Claude Opus 4.7 (with zenitech007)
**Successor to:** [2026-05-24-voice-listener-upgrade-design.md](2026-05-24-voice-listener-upgrade-design.md)

## Goal

Make the `zendaya-hud-react` HUD actually reflect the rich state the Python backend already produces. Today the React HUD consumes only `state`, `text`, `panel`, `action`, and `now_playing`; the backend produces (but never reaches the HUD) amplitude, visemes, telemetry, perception, and body actions. This spec wires them end-to-end while fixing three existing bugs found during reconnaissance.

## Non-goals

- Rebuilding the orb mesh, or swapping to a humanoid VRM avatar (separate product directions; user chose Path A — keep procedural orb, reinterpret channels).
- Adding a new module (calculator, journal, etc.) — that's a follow-up spec.
- Visual polish pass (shader palette, post-processing) — separate follow-up.
- Touching the Tauri shell config, window decorations, or the always-on-top behavior.
- Touching `zendaya-pet/` or `zendaya-hud-template/`.
- Body-action poses on a humanoid avatar (we're on a procedural orb — body actions become emotive keyframes).
- Touching the user's large pre-existing uncommitted diff in `backend/zendaya.py` / `pyproject.toml` etc.

## Context

### Backend `zendaya_state_server.py`

FastAPI on `127.0.0.1:7475` with both HTTP and `/ws` WebSocket. Public setters:
`set_state`, `set_panel`, `set_now_playing`, `set_action`, `set_amplitude`, `set_visemes`, `set_body_action`, `set_telemetry_provider`, `set_perception_providers`.

Today's WS broadcasts: `set_state`, `set_panel`, `set_now_playing`, `set_action`. Everything else is HTTP-only — visemes, body action, telemetry, perception, **and `set_amplitude`** are written to module-level shared dicts and exposed via HTTP endpoints, but never broadcast. This is why the orb's voice-reactive scaling is dead in production: the frontend hook handles an `audio_level` WS field that no message ever delivers.

### Frontend `zendaya-hud-react`

Vite + React 18 + Three.js (R3F) + GSAP + Zustand + Tauri 2. Has a shipped `dist/`. `useWebSocket` connects to `ws://127.0.0.1:7475/ws` with exponential reconnect (800ms→8000ms). Zustand store (`src/store/zendayaStore.ts`) has slices for `ai`, `text`, `audioLevel`, `connected`, `scene`, `panel`, `activeModule`, etc.

The orb (`src/components/Orb/Orb.tsx`) is a **procedural sphere**: two nested `sphereGeometry` with a custom fresnel glow `ShaderMaterial`. No mesh, no rig, no mouth, no body. This shapes everything that follows.

### Bugs found during reconnaissance (all bundled into this spec)

1. **Orb voice-reactivity is dead** — backend's `set_amplitude()` writes a shared dict but never broadcasts on WS. The frontend hook handles `audio_level` but no message ever delivers it.
2. **4 AI states silently dropped** — `useWebSocket` filters incoming `state` against `["idle","listening","thinking","speaking","error"]`. The store defines and the backend emits `aware`, `searching`, `mapping`, `alert` too. They're silently discarded.
3. **MusicPlayer transport broken** — `MusicPlayer.tsx` POSTs `{text: "..."}` to `/chat`; backend's `ChatIn` expects `{message: ...}`. Every transport command returns `{accepted: false}`.

### Decisions captured during brainstorming

- **Channels in scope:** voice (amplitude + visemes), perception (face + last gesture), telemetry (CPU/mem/mood), body action (nod/shake/wave/shrug). All four in one spec, plus the bugs.
- **Orb interpretation:** procedural sphere stays. Visemes drive a **ripple uniform** in a new core shader (not literal lip-sync). Body actions become **GSAP keyframes** on a child group (bounce/wobble/orbit/expand).
- **Plumbing:** WS push (single connection). New `_broadcast_loop()` daemon thread on the backend pushes amplitude/visemes at 30 Hz, telemetry at 2 Hz, perception every 5s as a heartbeat (plus on-change), body action on-change only.

## Architecture

| File | Action | Responsibility |
|---|---|---|
| `backend/zendaya_state_server.py` | Modify | Add `_broadcast_loop()` daemon thread + per-channel decimation. Snapshot extended on initial connect. |
| `backend/tests/test_state_server_broadcast.py` | Create | Pytest unit tests for tick + shape correctness + decimation + snapshot |
| `zendaya-hud-react/package.json` | Modify | Dev-deps: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `happy-dom` |
| `zendaya-hud-react/vitest.config.ts` | Create | Vitest config (happy-dom env, `@testing-library/jest-dom` setup) |
| `zendaya-hud-react/src/store/zendayaStore.ts` | Modify | Add `visemes`, `telemetry`, `perception`, `bodyActionPulse` slices + setters. Export full `AiState` |
| `zendaya-hud-react/src/hooks/useWebSocket.ts` | Modify | Widen AI filter to all 9 states; handle new message types; 10s heartbeat ping |
| `zendaya-hud-react/src/hooks/useBodyAction.ts` | Create | Subscribe to `bodyActionPulse`; run GSAP timelines on the body group (nod/shake/wave/shrug) |
| `zendaya-hud-react/src/components/Orb/Orb.tsx` | Modify | Swap core mesh to a `ShaderMaterial` with viseme-driven ripple uniform; restructure to two nested groups (voice scaling outer, body action inner); mount `useBodyAction` |
| `zendaya-hud-react/src/components/HUD/TelemetryWidget.tsx` | Create | Corner overlay: CPU/mem bars + mood text + offline banner |
| `zendaya-hud-react/src/components/HUD/PerceptionIndicator.tsx` | Create | Top-left indicator: face dot + last-gesture chip (stale-fade) |
| `zendaya-hud-react/src/components/HUD/Hud.tsx` | Modify | Mount the two new widgets; add `useMoodAtmosphere` effect for mood→`bgDim` bias |
| `zendaya-hud-react/src/components/HUD/MusicPlayer.tsx` | Modify | Bug fix: change POST body key `text` → `message` |
| `zendaya-hud-react/src/__tests__/*` | Create | Vitest tests for store, useWebSocket, widgets, useBodyAction |

No new top-level module. Existing repo structure unchanged.

## Backend broadcast loop + message shapes

**New daemon thread `_broadcast_loop()` in `zendaya_state_server.py`.** Started from the existing FastAPI startup event; stopped via `_broadcast_stop = threading.Event()` in the corresponding shutdown event. The tick body is wrapped in a single try/except so one bad tick can't kill the thread.

**Cadence:**

| Channel | Rate | Trigger / decimation |
|---|---|---|
| `amplitude` | 30 Hz | Suppressed if `abs(new − last_sent) < 0.005` |
| `visemes` | 30 Hz | Suppressed if every weight is within 0.01 of last sent |
| `telemetry` | 2 Hz | Always sent (small payload) |
| `perception` | 2 Hz on-change + 5s heartbeat | Compared by content; heartbeat keeps clients in sync |
| `body_action` | On-change only | `set_body_action()` broadcasts immediately; the loop does NOT poll it. After broadcast, in-memory value resets to `""` so a repeat call re-broadcasts |

The 30 Hz tick uses `time.sleep(1/30)`. CPU cost on an idle system: <0.5%.

**Message shapes (flat one-key objects matching the existing hook's `if (data.X)` pattern):**

```json
{"amplitude": 0.42}
{"visemes": {"aa": 0.1, "ih": 0.0, "ee": 0.0, "oh": 0.6, "ou": 0.0}}
{"telemetry": {"cpu": 21.4, "mem": 58.2, "mic_level": 0.0,
               "mood": "neutral", "vision_active": false, "gestures_active": false,
               "hud_enabled": true, "online": true,
               "user_name": "Ikenna", "language": "english",
               "last_gesture": {"name": "none", "ts": 0.0}}}
{"perception": {"face": {"present": true, "ts": 1780165000.0},
                "last_gesture": {"name": "Thumb_Up", "ts": 1780164997.5}}}
{"body_action": "nod"}
```

**`set_body_action()` validates against `{"nod","shake","wave","shrug",""}`**; unknown values become `""` (no-op) with a one-line log.

**`set_amplitude()` and `set_visemes()` keep their HTTP endpoints unchanged** for back-compat. The broadcast is purely additive.

**Initial-connect snapshot extended:** the existing handshake `{"state": ..., "text": ...}` gains `telemetry`, `perception`, and `now_playing` (if non-null) so the UI doesn't show stale defaults until the first tick arrives.

## Frontend store + WS hook + bundled bug fixes

### `zendayaStore.ts` — extend the shape

```ts
export type Visemes = { aa: number; ih: number; ee: number; oh: number; ou: number };
export type Telemetry = {
  cpu: number; mem: number; mic_level: number;
  mood: string; vision_active: boolean; gestures_active: boolean;
  hud_enabled: boolean; online: boolean;
  user_name: string; language: string;
  last_gesture: { name: string; ts: number };
};
export type Perception = {
  face: { present: boolean; ts: number };
  last_gesture: { name: string; ts: number };
};
export type BodyAction = "" | "nod" | "shake" | "wave" | "shrug";

// New slices
visemes: Visemes;                                       // default all-zeros
telemetry: Telemetry | null;                            // null until first tick
perception: Perception | null;
bodyActionPulse: { action: BodyAction; ts: number };    // ts changes on each pulse

// New setters
setVisemes: (v: Visemes) => void;
setTelemetry: (t: Telemetry) => void;
setPerception: (p: Perception) => void;
firePulseBodyAction: (a: BodyAction) => void;           // increments ts even on repeat
```

`bodyActionPulse.ts` increments on every call so `useEffect([pulse.ts])` re-fires the GSAP timeline even when the same action repeats.

### `useWebSocket.ts` — three changes

1. **Widen the AI filter.** Replace the `VALID_AI` allowlist with the full `AiState` union: `["idle","aware","listening","thinking","speaking","searching","mapping","alert","error"]`. The store already defines them; the hook just stops dropping them.
2. **Handle the new message keys** (additive `if` branches mirroring existing pattern):
   ```ts
   if (typeof data.amplitude === "number") setAudioLevel(clamp(data.amplitude, 0, 1));
   if (data.visemes && typeof data.visemes === "object") setVisemes(normaliseVisemes(data.visemes));
   if (data.telemetry && typeof data.telemetry === "object") setTelemetry(data.telemetry);
   if (data.perception && typeof data.perception === "object") setPerception(data.perception);
   if (typeof data.body_action === "string" && data.body_action) firePulseBodyAction(data.body_action as BodyAction);
   ```
3. **Heartbeat:** send `{"ping": true}` every 10s. Backend tolerates unknown payloads. Keeps NAT/firewall mappings alive.

### Bundled bug fixes

1. **`audio_level` revived** — the moment the backend broadcasts `amplitude`, the existing orb voice-scaling at [Orb.tsx:82-83](../../zendaya-hud-react/src/components/Orb/Orb.tsx) comes alive. No frontend change beyond #2 in this section. Worth calling out as a separate verifiable outcome.
2. **AI state filter widening** — covered above; resolves the silent-drop of `aware/searching/mapping/alert`.
3. **`MusicPlayer.tsx` transport key** — change the `JSON.stringify({ text })` line to `JSON.stringify({ message: text })`. One-line fix.

## Orb wiring

### Amplitude scaling

Already implemented at [Orb.tsx:82-83](../../zendaya-hud-react/src/components/Orb/Orb.tsx): `1 + z.audioLevel * 0.15`, smoothed at `dt * 10`. Comes alive automatically once the backend broadcasts `amplitude`. No code change needed for amplitude.

### Visemes → ripple

Replace the core mesh's `MeshBasicMaterial` with a small `ShaderMaterial` carrying three new uniforms and a vertex displacement:

```glsl
// uniforms
uniform float uRippleStrength;   // 0..1, derived from sum(visemes) / 5
uniform float uRippleFreq;       // 8.0 baseline
uniform float uTime;             // seconds since boot

// vertex shader — displace along normal
float ripple = sin(uTime * uRippleFreq + position.x * 6.0)
             * sin(uTime * uRippleFreq * 1.3 + position.y * 6.0);
vec3 displaced = position + normal * ripple * uRippleStrength * 0.06;
gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
```

In `useFrame`:

```ts
const visemeSum = z.visemes.aa + z.visemes.ih + z.visemes.ee + z.visemes.oh + z.visemes.ou;
const targetRipple = Math.min(1, visemeSum);
ripple.current += (targetRipple - ripple.current) * Math.min(1, dt * 8);
coreMat.uniforms.uRippleStrength.value = ripple.current;
coreMat.uniforms.uTime.value = performance.now() * 0.001;
```

When Zendaya is silent the orb is smooth; while she vocalises the surface ripples. Readable as "she's vocalising" without claiming literal lip-sync.

### Body action via GSAP

New hook `src/hooks/useBodyAction.ts`:

```ts
import { useEffect } from "react";
import gsap from "gsap";
import * as THREE from "three";
import { useZendaya } from "../store/zendayaStore";

export function useBodyAction(groupRef: React.MutableRefObject<THREE.Group | null>) {
  const pulse = useZendaya((s) => s.bodyActionPulse);
  useEffect(() => {
    const g = groupRef.current;
    if (!g || !pulse.action) return;
    try {
      gsap.killTweensOf([g.position, g.rotation, g.scale]);
      switch (pulse.action) {
        case "nod":   nodTimeline(g); break;
        case "shake": shakeTimeline(g); break;
        case "wave":  waveTimeline(g); break;
        case "shrug": shrugTimeline(g); break;
      }
    } catch (e) {
      console.warn("[orb] body-action GSAP failed, falling back to raf wobble", e);
      fallbackWobble(g);
    }
  }, [pulse.ts, groupRef]);
}
```

Four timelines, ~30 lines total:

| Action | Visual | Rough timing |
|---|---|---|
| `nod` | Vertical bounce down→up→neutral | 0.45s, `position.y` ±0.15, ease `back.out(2)` |
| `shake` | Horizontal wobble L↔R three times | 0.6s, keyframes on `position.x`, ease `sine.inOut` |
| `wave` | Tilt + small orbit arc | 0.8s, combined `rotation.z` + `position.x`, ease `power2.inOut` |
| `shrug` | Scale-up squash then settle | 0.5s, `scale` 1.12 → 1.0, ease `elastic.out(1, 0.6)` |

### Orb structure — two nested groups

```tsx
return (
  <group ref={group}>            {/* voice scaling here, existing */}
    <group ref={bodyGroup}>      {/* body-action GSAP here, new */}
      <mesh ref={glow}>…</mesh>
      <mesh ref={core}>…</mesh>
    </group>
  </group>
);
```

`useBodyAction(bodyGroup)` runs on the inner; the existing voice scaling stays on the outer. No conflict.

## Telemetry + Perception widgets

### `TelemetryWidget.tsx`

Corner overlay (top-right). Tailwind-only. Hidden while `telemetry === null`.

```tsx
export default function TelemetryWidget() {
  const t = useZendaya((s) => s.telemetry);
  if (!t) return null;
  return (
    <div className="absolute top-4 right-4 flex flex-col gap-1 text-xs
                    text-orange-300/80 font-mono select-none pointer-events-none">
      <Row label="CPU" value={t.cpu} unit="%" />
      <Row label="MEM" value={t.mem} unit="%" />
      <div className="opacity-60">mood: {t.mood}</div>
      {!t.online && <div className="text-red-400/80">offline</div>}
    </div>
  );
}

function Row({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-10 opacity-60">{label}</span>
      <div className="w-20 h-1 bg-orange-300/10 rounded overflow-hidden">
        <div className="h-full bg-orange-400/60" style={{ width: `${Math.min(100, value)}%` }} />
      </div>
      <span className="w-10 text-right">{value.toFixed(0)}{unit}</span>
    </div>
  );
}
```

### `PerceptionIndicator.tsx`

Top-left. Face dot + last-gesture chip; chip auto-hides after 3s of staleness.

```tsx
export default function PerceptionIndicator() {
  const p = useZendaya((s) => s.perception);
  if (!p) return null;
  const stale = Date.now() / 1000 - p.last_gesture.ts > 3.0;
  const gestureLabel = p.last_gesture.name && p.last_gesture.name !== "none" && !stale
    ? p.last_gesture.name.replace(/_/g, " ")
    : null;
  return (
    <div className="absolute top-4 left-4 flex items-center gap-2 text-xs
                    text-orange-300/80 font-mono select-none pointer-events-none">
      <span className={`w-2 h-2 rounded-full ${
        p.face.present ? "bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" : "bg-zinc-500/40"
      }`} />
      <span className="opacity-70">{p.face.present ? "sees you" : "looking"}</span>
      {gestureLabel && (
        <span className="ml-2 px-1.5 py-0.5 rounded bg-orange-400/10
                         border border-orange-400/30 animate-pulse">
          {gestureLabel}
        </span>
      )}
    </div>
  );
}
```

### `Hud.tsx` — mount + mood-atmosphere effect

```tsx
<>
  {/* existing HUD contents */}
  <TelemetryWidget />
  <PerceptionIndicator />
</>
```

Inside `Hud.tsx` (or split into a tiny `useMoodAtmosphere` hook):

```ts
useEffect(() => {
  const moodToBgDim: Record<string, number> = {
    "neutral": 0.7, "focused": 0.6, "tired": 0.85, "alert": 0.5,
  };
  if (telemetry?.mood) setBgDim(moodToBgDim[telemetry.mood] ?? 0.7);
}, [telemetry?.mood]);
```

This closes the loop on the dead `bgDim` setter the scout flagged.

## Error handling

| Failure | Behavior |
|---|---|
| Backend `_broadcast_loop()` tick raises | Try/except around tick body; rate-limited log; continue looping |
| Provider callback raises (telemetry/perception) | That channel sends `null` payload one time, then suppresses until provider recovers |
| `set_body_action("unknown")` | Allowlist filter; value becomes `""` (no-op) + one-line log |
| WS message has malformed shape (`telemetry: 42`) | Type guards in hook; one-line console warn; message dropped |
| `setVisemes` receives NaN / out-of-range | `normaliseVisemes` clamps to `[0, 1]`, NaN/missing → 0 |
| GSAP runtime failure | `useBodyAction` try/catches; falls back to 200 ms requestAnimationFrame wobble; one-line warn |
| Orb shader compile fails (driver edge case) | Catch, fall back to `MeshBasicMaterial` for the core; voice scaling + body action still work |
| WS reconnect storm | Existing exponential backoff (800ms → 8000ms); new heartbeat doesn't reset it |
| Stale telemetry on initial connect | First tick post-reconnect is fresh; worst case 500ms stale frame |
| MusicPlayer POST still fails after key fix | `pushNotification("Music command failed.")`; don't throw |
| `useAdaptiveQuality` drops to `"low"` | Orb skips ripple uniform updates (kept at 0); visemes still flow into the store |
| Tauri window minimized | Unchanged; backend keeps broadcasting; CPU footprint = tick + tiny payloads |

No silent failures. Each degrade prints one informative line.

## Testing strategy

### Setup (new)

Add to `zendaya-hud-react/package.json` dev-deps: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `happy-dom`. Create `vitest.config.ts` (happy-dom env, `@testing-library/jest-dom` setup file).

Backend tests slot into the existing `backend/tests/` pytest suite (78 passing tests today; this adds one new file).

### Frontend unit tests

1. **`zendayaStore`** — new setters mutate the right slices; `firePulseBodyAction` increments `ts` even on repeat; `normaliseVisemes` clamps and handles NaN.
2. **`useWebSocket`** — table-driven mock-WS event dispatch covering all new message types AND the four previously-dropped AI states (`aware`, `searching`, `mapping`, `alert`); malformed payloads dropped without throwing.
3. **`TelemetryWidget`** — null hides, populated renders, `online: false` shows offline banner.
4. **`PerceptionIndicator`** — null hides, populated renders dot + chip, stale gesture hides chip, `face.present: false` shows grey dot + "looking".
5. **`useBodyAction`** — mock GSAP; assert keyframe calls per action; assert effect re-fires on `ts` change with same action.

### Backend unit tests

6. **`backend/tests/test_state_server_broadcast.py`** — fake provider; `_collect_tick()` produces expected shapes per channel; amplitude/viseme decimation suppresses near-identical values; `set_body_action("nod")` broadcasts then resets in-memory value to `""`; `set_body_action("garbage")` becomes `""`; provider exception sends `{"telemetry": null}` once then suppresses.
7. **Initial-connect snapshot** — mock WS client; assert first message contains snapshot keys.

### Not tested

- Real broadcast cadence under load (flaky on CI; manual ear-test).
- Real GSAP visual output (keyframe-smoke via mock GSAP covers behavior; pixel accuracy is subjective).
- Real Tauri window behavior (manual checklist).

### Manual verification checklist

- [ ] Start `zendaya-hud-react` dev server with backend running. Orb visible.
- [ ] Speak — orb pulses visibly. Core ripples during vocalisation.
- [ ] Telemetry widget appears in top-right within 1s; CPU/mem bars update every ~500 ms; mood text changes with system mood.
- [ ] Stand in front of webcam (vision enabled) — Perception dot turns emerald.
- [ ] Make a recognised gesture — chip flashes briefly, then fades after 3s.
- [ ] Trigger `set_body_action("nod")` from backend (debug endpoint or test script) — orb performs a discrete bounce.
- [ ] Trigger same body action twice in 500 ms — orb bounces twice (repeat-pulse working).
- [ ] Send `set_state("alert")` — orb takes the alert pulse intensity (regression — was silently dropped before).
- [ ] MusicPlayer transport — pause/skip a Spotify track from the HUD; backend logs receive `{"message": "..."}` not `{"text": "..."}`.
- [ ] Kill backend mid-session — frontend WS reconnects within ~5s; widgets clear, then repopulate on reconnect.

## Done criteria

- `_broadcast_loop()` is running on the backend and the new pytest file passes (incl. decimation + snapshot tests).
- The 4 new Zustand slices exist, the WS hook routes all 5 new message types into them, and the AI filter is widened.
- Orb's core renders with the ripple shader; viseme messages produce visible ripple; voice scaling works (the long-dead amplitude path is alive).
- `useBodyAction` runs GSAP timelines for all 4 actions; `bodyActionPulse.ts` re-triggers on repeat.
- `TelemetryWidget` and `PerceptionIndicator` are mounted in `Hud.tsx`, render correctly when populated, hide when null.
- Mood biases `bgDim` (closes the dead-state finding).
- MusicPlayer transport POSTs `{message: ...}` and the backend accepts it.
- Vitest suite passes; existing 78 pytest tests still pass.
- Manual checklist runs clean on the user's machine.

## Risks and unknowns

| Risk | Mitigation |
|---|---|
| Vitest + happy-dom doesn't play well with R3F / Three.js modules at import time | Tests only target store/hooks/widgets — none of them import Three. Orb test is deferred to manual verification |
| The user's pre-existing 4,400-line uncommitted diff overlaps `backend/zendaya_state_server.py` and would clobber the broadcast loop on resolution | The voice and AAF specs already documented this pattern. Same caveat: spec changes land against HEAD; user re-stitches when they handle the pre-existing diff |
| GSAP package version mismatch causes silent timeline failures | Try/catch fallback in `useBodyAction` ensures *some* visual feedback; surface in dev console |
| 30 Hz broadcast causes WS backpressure on slow networks | Local-loopback only; bandwidth is not a real concern. Decimation already reduces actual messages sent |
| Shader compile fails on the user's GPU driver | Try/catch falls back to `MeshBasicMaterial`; voice scaling + body action still work |
| Mood string from backend doesn't match the `moodToBgDim` table | Default fallback (0.7) covers unknown moods |
| New broadcast thread interferes with FastAPI shutdown | Use existing FastAPI startup/shutdown events; `_broadcast_stop` event signals clean exit |

## Deferred / future work

- Visual polish pass: shader palette, glow tuning, post-processing (bloom/vignette/noise).
- New module: command palette, conversation history panel, alarms-from-AAF panel.
- Body action via richer orb mesh or VRM avatar (Path B / Path C from brainstorming).
- Wiring `notifications` to a backend push channel (currently only via `dispatchAction("show_notification", ...)`).
- `setSpeakerAzimuth` driver for spatial audio (no backend signal today).
- Adaptive-quality auto-tuning of the broadcast cadence (drop to 15 Hz when `fps < 30`).
- Auto-calibrating ambient floor for `useMoodAtmosphere` based on observed `mood` distribution over time.
