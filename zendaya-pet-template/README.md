# Zendaya Pet — Tauri + React + TypeScript

The web-native rebuild of the desktop mascot. Same Python backend as before
(`backend/zendaya.py` + FastAPI server on `127.0.0.1:7475`), but the face is
now React + Three.js inside a transparent, borderless, always-on-top
Tauri window.

```
┌──────────────────┐   HTTP localhost:7475   ┌───────────────────────┐
│ backend/         │ ◄──────────────────────►│ zendaya-pet (Tauri)    │
│ zendaya.py       │   GET  /ai_status       │ React + R3F + VRM      │
│ FastAPI bridge   │   POST /chat            │ Tailwind UI            │
└──────────────────┘                         └───────────────────────┘
```

> This folder is a **template**. The `npm create tauri-app` scaffolder
> demands an empty target folder, so the canonical files live here in
> `zendaya-pet-template/`. Once you've scaffolded `zendaya-pet/`, copy
> these files on top.

---

## 1. One-time scaffold

Run from `C:\Users\IKA\Zendaya\` (parent of this template folder):

```bash
npm create tauri-app@latest zendaya-pet
```

When prompted:

- **Package manager:** `npm`
- **UI template:** `React`
- **UI flavor:** `TypeScript`

Then:

```bash
cd zendaya-pet
npm install

# 3D + VRM
npm install three @react-three/fiber @react-three/drei \
  @pixiv/three-vrm @pixiv/three-vrm-springbone

# Tailwind v3 (v4 changes the config story)
npm install -D tailwindcss@^3 postcss autoprefixer
npx tailwindcss init -p
```

`npx tailwindcss init -p` writes default `tailwind.config.js` and
`postcss.config.js` — you'll overwrite both with the versions in this
template.

Tauri's Rust toolchain prerequisites (one-time install): see
<https://v2.tauri.app/start/prerequisites/>. On Windows that's the
"Microsoft Visual Studio C++ Build Tools" + Rust via `rustup`.

---

## 2. Drop the template files in

From `C:\Users\IKA\Zendaya\zendaya-pet-template\`, copy:

| Source (template) | Destination (scaffolded) |
|---|---|
| `src/App.tsx` | `zendaya-pet/src/App.tsx` (overwrite) |
| `src/main.tsx` | `zendaya-pet/src/main.tsx` (overwrite) |
| `src/index.css` | `zendaya-pet/src/index.css` (overwrite if present, else create) |
| `src/lib/api.ts` | `zendaya-pet/src/lib/api.ts` |
| `src/hooks/useAiStatus.ts` | `zendaya-pet/src/hooks/useAiStatus.ts` |
| `src/components/Avatar.tsx` | `zendaya-pet/src/components/Avatar.tsx` |
| `src/components/ChatBox.tsx` | `zendaya-pet/src/components/ChatBox.tsx` |
| `src/components/SpeechBubble.tsx` | `zendaya-pet/src/components/SpeechBubble.tsx` |
| `tailwind.config.js` | `zendaya-pet/tailwind.config.js` (overwrite) |
| `postcss.config.js` | `zendaya-pet/postcss.config.js` (overwrite) |

PowerShell one-liner if you'd rather just splat it across:

```powershell
Copy-Item -Recurse -Force `
  C:\Users\IKA\Zendaya\zendaya-pet-template\src `
  C:\Users\IKA\Zendaya\zendaya-pet\
Copy-Item -Force `
  C:\Users\IKA\Zendaya\zendaya-pet-template\tailwind.config.js, `
  C:\Users\IKA\Zendaya\zendaya-pet-template\postcss.config.js `
  C:\Users\IKA\Zendaya\zendaya-pet\
```

Make sure `src/main.tsx` does `import "./index.css"` (the template version
already does).

---

## 3. Patch `src-tauri/tauri.conf.json`

See `SCAFFOLD_NOTES.md` (next to this README) — it has the exact JSON.
Short version: set the window to `decorations:false`, `transparent:true`,
`alwaysOnTop:true`, `width:480`, `height:900`, and add a `connect-src`
entry for `http://127.0.0.1:7475` in the CSP.

---

## 4. Drop the VRM file in `public/`

Vite serves anything under `public/` at the web root, so referencing
`/Zendaya.vrm` in code Just Works.

```powershell
Copy-Item C:\Users\IKA\Zendaya\backend\assets\Zendaya.vrm `
          C:\Users\IKA\Zendaya\zendaya-pet\public\Zendaya.vrm
```

To swap to `Zendaya-orange.vrm`, copy that file into `public/` instead and
change the `VRM_URL` constant at the top of `src/components/Avatar.tsx`.

---

## 5. Run the backend, then the pet

In one shell:

```bash
cd C:\Users\IKA\Zendaya\backend
python zendaya.py
```

You should see `🪟 State server: http://127.0.0.1:7475`.

In a second shell:

```bash
cd C:\Users\IKA\Zendaya\zendaya-pet
npm run tauri dev
```

First boot compiles the Rust side — that's slow (a few minutes). Later
boots are quick.

> While iterating on the React UI, `npm run dev` runs Vite alone in a
> normal browser tab. Faster feedback loop, no transparency, no
> always-on-top. Use `npm run tauri dev` whenever you need the real
> desktop window behaviour.

---

## 6. Verify

1. The Tauri window opens borderless, with the VRM avatar floating on
   your desktop. No window chrome, no opaque rectangle behind her.
2. The window stays on top of other apps.
3. Type **"hi"** in the bottom chat bar → press Enter.
4. Within ~250 ms the avatar's mouth (`aa` blendshape) starts
   oscillating, and her reply text shows in a bubble next to her head.
5. After ~10–15 s with no further updates, state auto-decays back to
   `idle` (the Python server's `_DECAY_SECS`), the bubble fades away,
   and she returns to blinking.

---

## 7. Build a release

```bash
npm run tauri build
```

Produces an installer + portable exe under
`src-tauri/target/release/bundle/`. The first release build is slow
because Tauri is statically linking webview and Rust deps; subsequent
builds are incremental.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Black/grey rectangle behind avatar | Transparency missing one of three layers | Verify `tauri.conf.json` has `transparent:true`, `Canvas` has `gl={{alpha:true}}` and inline style `background:"transparent"`, and `index.css` zeros out `html, body, #root` backgrounds. |
| `[chat HTTP 0]` or status never updates | Backend not running, or CSP blocked the fetch | Start `zendaya.py`. Check `connect-src` in `tauri.conf.json` includes `http://127.0.0.1:7475`. |
| Avatar pink / untextured | VRM textures didn't load | The CSP must allow `img-src 'self' data: blob:`. Also confirm `public/Zendaya.vrm` exists (case-sensitive). |
| Mouth never moves while talking | Blend-shape name mismatch on this rig | `Avatar.tsx` tries `["aa","a","A","Mouth_A"]`. Add the actual name from your VRM (open it in <https://vrm.dev/en/univrm/blendshape/> to inspect) to the candidate list. |
| Always-on-top doesn't stick | Some Windows tools (e.g. some game launchers) can override | Click the avatar to refocus. Tauri sets the flag at window create time. |
| Tauri build fails on first run | Rust toolchain missing | <https://v2.tauri.app/start/prerequisites/> — install rustup + MSVC build tools, then re-run. |
| Want her in a different default position | Tauri can't set "always on top" + a position pre-aware of the taskbar without help | Pass `position` in `tauri.conf.json`'s window object, or use `@tauri-apps/api/window` `appWindow.setPosition()` from `App.tsx`. |

---

## What's NOT included (intentional)

- **Real phoneme lipsync** — the mouth oscillates on a sine wave during
  `talking`. Real lipsync needs streaming audio levels from ElevenLabs
  back through the state server. Future work.
- **Microphone input** — voice still happens Python-side
  (`zendaya_voice_listener`). The Tauri pet is text-only.
- **Window perch / walk** — the bonus `GET /window` and
  `POST /window/control` endpoints are live (added during the Godot
  build) but the new Tauri pet doesn't consume them yet. Follow-up.
- **Auto-reconnect UI** — if the backend is down, the pet sits in idle
  and silently retries each tick. Restart `zendaya.py` and it picks up
  on the next 250 ms poll.

---

## Folder reference

```
zendaya-pet-template/
├── README.md              (this file)
├── SCAFFOLD_NOTES.md      tauri.conf.json patch
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── index.css
│   ├── lib/api.ts
│   ├── hooks/useAiStatus.ts
│   └── components/
│       ├── Avatar.tsx
│       ├── ChatBox.tsx
│       └── SpeechBubble.tsx
├── tailwind.config.js
├── postcss.config.js
└── .gitignore
```
