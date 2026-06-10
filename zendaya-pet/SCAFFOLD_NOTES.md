# Scaffold notes — `tauri.conf.json` patch

After running `npm create tauri-app@latest zendaya-pet`, open
`zendaya-pet/src-tauri/tauri.conf.json` and apply the changes below.
Keep the keys you don't see here at their scaffolded defaults.

The fields you care about live under `app.windows[0]` (the main
window) and `app.security` (CSP + capabilities).

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "Zendaya Pet",
  "version": "0.1.0",
  "identifier": "com.zendaya.pet",
  "build": {
    "beforeDevCommand": "npm run dev",
    "devUrl": "http://localhost:1420",
    "beforeBuildCommand": "npm run build",
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "label": "main",
        "title": "Zendaya Pet",
        "width": 480,
        "height": 900,
        "minWidth": 320,
        "minHeight": 480,
        "resizable": true,
        "decorations": false,
        "transparent": true,
        "alwaysOnTop": true,
        "skipTaskbar": false,
        "shadow": false,
        "center": false,
        "x": 80,
        "y": 80
      }
    ],
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://127.0.0.1:7475 ipc: http://ipc.localhost; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self' 'wasm-unsafe-eval'; worker-src 'self' blob:"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  }
}
```

## What each window flag does

| Field | Value | Why |
|---|---|---|
| `decorations` | `false` | No title bar / borders. Lets the avatar look like a free-floating sprite. |
| `transparent` | `true` | Per-pixel transparency reaches the OS compositor. |
| `alwaysOnTop` | `true` | Pet stays above every other window. |
| `skipTaskbar` | `false` | Keep her in Alt+Tab so you can find her if she walks off-screen. Set `true` if you'd rather she vanish from the taskbar. |
| `shadow` | `false` | Disables the OS drop-shadow; without it the shadow rectangle gives away the invisible window bounds. |
| `width` / `height` | `480` × `900` | Mirrors the Godot version's portrait shape. |
| `x` / `y` | `80` / `80` | Spawn position. Combined with `center:false`. |

## What the CSP allows

| Directive | Purpose |
|---|---|
| `connect-src ... http://127.0.0.1:7475` | Lets the renderer hit the FastAPI server. Without this, every `fetch` to `/ai_status` and `/chat` is blocked. |
| `img-src 'self' data: blob:` | VRM textures decode through `blob:` URLs internally; `data:` covers any inline thumbnails. |
| `style-src 'self' 'unsafe-inline'` | Tailwind injects `<style>` tags at runtime in dev. The `'unsafe-inline'` keyword is the standard escape. |
| `script-src 'self' 'wasm-unsafe-eval'` | Three.js + KTX2/Draco loaders use WASM. |
| `worker-src 'self' blob:` | Three.js spawns workers for asset decoding. |

## Per-platform extras

### macOS

Add at the top level of `tauri.conf.json` (next to `productName`):

```json
"macOSPrivateApi": true
```

…then transparent + always-on-top works the same as on Windows. Without
it, the macOS WebView ignores the alpha channel.

### Linux

Transparency depends on a compositor. GNOME / KDE / `picom` are fine.
Bare i3 without `picom` will render the alpha channel as black.

## Allowed-list / capabilities (Tauri 2)

Tauri 2 uses a capability file at
`src-tauri/capabilities/default.json`. The default scaffold gives the
main window enough permissions for the bare `core:default` set, which
covers `fetch` and DOM access. **No edits needed** unless you start
calling `@tauri-apps/api/window` from the React side (e.g. for
`appWindow.setPosition()`). If you do:

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Capability for the main window",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:window:allow-set-position",
    "core:window:allow-set-size"
  ]
}
```

## Known gotchas

- **First `npm run tauri dev` is slow.** It compiles Tauri's Rust side
  from scratch — easily 3–5 minutes. Subsequent runs are fast.
- **CSP errors show up in DevTools, not the terminal.** If a fetch
  silently fails, hit `Ctrl+Shift+I` in the Tauri window → Console.
- **`width`/`height` are scaffolded with the splash window in mind.**
  If you keep the default 800×600, the avatar sits in the middle of a
  much larger transparent rectangle and clicks pass through unexpected
  areas. Use the 480×900 above.
