# Zendaya HUD (React + Three.js)

Cinematic Jarvis-style HUD frontend, per `Zendaya_UI_Architecture_Blueprint.pdf`.
Replaces the single-file `zendaya_ui.html` for users who want the full
React/GSAP/postprocessing experience. The Python backend at
`backend/zendaya_state_server.py` is unchanged — this just talks to it over
WS at `ws://127.0.0.1:7475/ws`.

## Stack

- React 18 + TypeScript + Vite
- Three.js via `@react-three/fiber` + `@react-three/drei`
- Postprocessing: bloom + vignette + noise
- GSAP timelines for scene transitions
- Framer Motion for 2D HUD overlays
- Zustand store (`src/store/zendayaStore.ts`)
- Tailwind v3

## Run as desktop app (Tauri)

```bash
cd zendaya-hud-react
npm install
npm run dev:app        # dev: native window via bundled WebView2
npm run build:app      # produces src-tauri/target/release/zendaya-hud.exe + installer
```

`dev:app` runs `node scripts/dev-with-webview.mjs`, which points
`WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` at `src-tauri/webview2-runtime/`
(a Junction to the pet's bundled runtime — the system WebView2 install on
this machine is broken). For a release build, the runtime is bundled
automatically via `webviewInstallMode.fixedRuntime`.

## Run in browser (debug only)

```bash
npm run dev
```

Opens <http://127.0.0.1:5180>. WS endpoint defaults to
`ws://127.0.0.1:7475/ws`. Override via query string:
`http://127.0.0.1:5180/?ws=ws://localhost:8765`.

## WS protocol

The store accepts these inbound messages:

| Field           | Type   | Effect                                    |
| --------------- | ------ | ----------------------------------------- |
| `state`         | string | `idle/listening/thinking/speaking/error`  |
| `text`          | string | Latest reply caption                      |
| `audio_level`   | number | 0..1; drives orb scale + voice viz bars   |
| `panel`         | string | `globe` shows MapModule; `none` hides     |
| `action`        | string | One of the blueprint actions (below)      |
| `payload`       | object | Action-specific data                      |

Actions: `open_map`, `close_map`, `dock_orb`, `undock_orb`,
`show_terminal`, `hide_terminal`, `activate_voice`, `deactivate_voice`,
`minimize_ui`, `restore_ui`, `show_notification` (payload.text).

Use `zendaya_state_server.set_action(name, payload)` from Python.

## Files

```
src/
  App.tsx                    # Canvas + EffectComposer + HUD overlay
  main.tsx                   # entry
  index.css                  # Tailwind base + body gradient
  components/
    Orb/Orb.tsx              # voice-reactive 3D orb + rings + halo
    Particles/Particles.tsx  # GPU points orbit shell
    MapModule/MapModule.tsx  # procedural globe (no external texture)
    VoiceVisualizer/...      # 2D bar waveform overlay
    DockSystem/...           # bottom-edge action dock
    HUD/Hud.tsx              # corner brackets + status + caption + notifs
  scenes/MainScene.tsx       # GSAP timeline: orb dock ⇄ map center
  store/zendayaStore.ts      # Zustand: AI state + UI flags + notifs
  hooks/useWebSocket.ts      # WS client → store mutations
```

## Future

- Multi-monitor: spawn a second window via Tauri once we wrap this.
- Terminal panel (action `show_terminal` exists in the store).
- Dashboard scene (telemetry: cpu/mem/mic level) — backend already exposes `/telemetry`.
