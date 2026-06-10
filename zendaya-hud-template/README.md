# Zendaya HUD — Tauri Wrapper

Standalone .exe wrapper for the dark sci-fi HUD frontend
(`backend/zendaya_ui.html`). Mirrors the Tauri pet pattern, but vanilla
(no React/Vite) since the HUD is a single-file HTML.

```
┌──────────────────┐   HTTP localhost:7475   ┌───────────────────────┐
│ backend/         │ ◄──────────────────────►│ zendaya-hud (Tauri)    │
│ zendaya.py +     │   WS  /ws               │ HUD HTML + Canvas ring │
│ zendaya_ui.html  │   GET /face_mode        │ Three.js globe panel   │
└──────────────────┘                         └───────────────────────┘
```

> This folder is a **template**. `npm create tauri-app` requires an empty
> target, so canonical files live here. After scaffolding `zendaya-hud/`,
> copy these files on top.

---

## 1. One-time scaffold

From `C:\Users\IKA\Zendaya\`:

```bash
npm create tauri-app@latest zendaya-hud
```

When prompted:

- **App name:** `zendaya-hud`
- **Identifier:** `com.zendaya.hud`
- **Frontend language:** `TypeScript / JavaScript`
- **UI template:** `Vanilla`
- **UI flavor:** `JavaScript`
- **Package manager:** `npm`

```bash
cd zendaya-hud
npm install
```

Then **copy** every file from `zendaya-hud-template/` on top of
`zendaya-hud/` (overwriting the scaffold defaults).

The `src/index.html` in this template is identical to
`backend/zendaya_ui.html`. Keep them in sync — the source of truth is
`backend/zendaya_ui.html` (because the Python brain serves it at
`http://127.0.0.1:7475/ui` for browser users). The build script at the
bottom of this file sync-copies on `npm run dev`/`npm run tauri build`.

---

## 2. Run in dev

```bash
npm run tauri dev
```

You should see a transparent, borderless window with the HUD ring. It
auto-connects to `ws://127.0.0.1:7475/ws` (overridden via the Tauri config
URL `?ws=...` if you need the spec port 8765).

---

## 3. Build .exe

```bash
npm run tauri build
```

Outputs:

- `src-tauri/target/release/zendaya-hud.exe`
- `src-tauri/target/release/bundle/msi/zendaya-hud_*.msi`
- `src-tauri/target/release/bundle/nsis/zendaya-hud_*-setup.exe`

Drop the `.exe` (or run the installer) on any Windows machine — it just
needs the Python backend running on `127.0.0.1:7475` to talk to.

---

## 4. Window behavior

`tauri.conf.json` is preconfigured for HUD use:

- `transparent: false` (HUD is opaque dark — different from the pet)
- `decorations: false` (no title bar — the HUD draws its own corner brackets)
- `alwaysOnTop: false` (you actually want to look at this fullscreen)
- `fullscreen: true`
- CSP `connect-src http://127.0.0.1:7475 ws://127.0.0.1:7475 ws://127.0.0.1:8765`
  so it can reach both port options.

Press `Esc` to close the globe panel. `Alt+F4` to quit (no tray icon yet).

---

## Why a separate Tauri folder?

Could the pet folder serve both? Yes, with a route. We don't, because:

1. The pet is full-3D and heavy; the HUD is HTML+Canvas and ~150KB.
   Different bundles keep startup snappy for whichever mode the user
   picks.
2. The pet wants `transparent + always-on-top + small`. The HUD wants
   `opaque + fullscreen`. Tauri window configs don't change at runtime
   ergonomically.
3. Voice command "switch to hud" launches this .exe; "switch to pet"
   launches the other. Simpler than juggling routes inside one bundle.
