# Zendaya Godot 4 Frontend — Setup Guide

This guide walks you through wiring the **Python brain** (`zendaya.py`)
to the **Godot 4 face** (the VRM avatar in this folder).

```
┌─────────────────┐   HTTP localhost:7475   ┌─────────────────┐
│ zendaya.py      │ ◄──────────────────────►│ Godot 4 (this)  │
│ FastAPI server  │   GET  /ai_status       │ pet.gd polls    │
│ + console/voice │   POST /chat            │ + drives blend  │
└─────────────────┘                         └─────────────────┘
```

---

## 1. Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.10+ | Same env you already run `zendaya.py` from |
| `fastapi`, `uvicorn`, `pydantic` | latest | `pip install fastapi uvicorn pydantic` |
| Godot | **4.2 or newer** | Standard build, not the .NET build. Download from <https://godotengine.org/download> |

The two VRM files are already on disk:
`backend/assets/Zendaya.vrm` (default) and `backend/assets/Zendaya-orange.vrm`.

---

## 2. Run the Python backend

```bash
cd C:\Users\IKA\Zendaya\backend
python zendaya.py
```

Expected console output (relevant lines):

```
✅ Gemini AI ready.
Proactive alerts active.
🪟 State server: http://127.0.0.1:7475
You:
```

Smoke-test from a second shell:

```bash
curl http://127.0.0.1:7475/health
# → {"ok": true, "name": "Zendaya"}

curl http://127.0.0.1:7475/ai_status
# → {"state": "idle", "text": "", "ts": ...}
```

If port 7475 is already used, edit
`zendaya_state_server.py` → change the default in `start()`, and
update `STATUS_URL` / `CHAT_URL` in `pet.gd` to match.

---

## 3. Open the Godot project

1. Launch Godot 4.
2. **Project Manager → Import** → browse to
   `backend/godot_frontend/project.godot` → **Import & Edit**.

You will see the `Pet` scene with an empty `Avatar` Marker3D.
The avatar slot is empty until you finish steps 4–5.

---

## 4. Install the VRM Importer addon

1. In Godot, click the **AssetLib** tab (top of the editor, next to *2D / 3D / Script*).
2. Search **"VRM"**. The plugin you want is published by **V-Sekai** —
   typical name: `vrm` or `Godot VRM Importer`.
3. **Download** → **Install** (accept the file list).
4. **Project → Project Settings → Plugins** → tick **Enable** next to the VRM addon.
5. **Restart the editor** when prompted. Godot will rescan and pick up `.vrm`
   files as importable scenes.

---

## 5. Import the VRM file

Godot can only import files inside the project folder, so we copy:

```bash
copy C:\Users\IKA\Zendaya\backend\assets\Zendaya.vrm C:\Users\IKA\Zendaya\backend\godot_frontend\assets\
```

Back in Godot:

1. The **FileSystem** panel (bottom-left) should now show
   `assets/Zendaya.vrm`. Wait a few seconds for the import to finish
   (you'll see a tiny gear icon while importing).
2. Open `pet.tscn` (double-click in FileSystem).
3. In the **Scene** panel, select the `Avatar` Marker3D node.
4. **Drag** `assets/Zendaya.vrm` from the FileSystem panel onto the
   `Avatar` node in the Scene panel. Godot will instance it as a child.
5. **Ctrl+S** to save the scene.

> If the avatar appears huge / tiny / off-screen, select the imported
> child under `Avatar` and tweak `Position` and `Scale` in the Inspector
> until the upper body fills the window.

---

## 6. Verify window settings

`project.godot` already enables them, but double-check
**Project → Project Settings → Display → Window**:

| Setting | Value |
|---|---|
| Size → **Transparent** | ✅ on |
| Size → **Borderless** | ✅ on |
| Size → **Always On Top** | ✅ on |
| **Per Pixel Transparency → Allowed** | ✅ on |

And **Rendering → Viewport → Transparent Background**: ✅ on.

If any of those are off, the avatar gets a black or grey rectangle
behind it.

---

## 7. Run the scene

Make sure `zendaya.py` is still running (step 2). Then in Godot press **F5**.

You should see:

- A borderless window with **just the avatar** floating on the desktop.
- Always on top.
- A small input box at the bottom: `Talk to Zendaya…`.
- A label area near the top showing Zendaya's last reply.
- Subtle idle animation: blinks, slight head sway.

---

## 8. Smoke-test the loop

In the Godot input box, type **"hi"** and hit Enter.

Watch the `zendaya.py` console — you should see Zendaya's reply
print there. Within ~250 ms:

1. State flips to **thinking** (Godot polls `/ai_status` four times a second).
2. `send_response` flips it to **talking** with the reply text.
3. Avatar's mouth (`A` blend shape) oscillates as a quick lipsync
   stand-in; the reply text appears in the top label.
4. After ~10–15 s of no further updates, state auto-decays back to **idle**.

You can also drive it from the curl side:

```bash
curl -X POST http://127.0.0.1:7475/chat -H "Content-Type: application/json" -d "{\"message\":\"what time is it\"}"
# → {"accepted": true}
```

---

## 9. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Black box behind avatar | Per-pixel transparency disabled | Re-tick the Display settings in step 6 and restart Godot. On Linux, transparency depends on a compositor (`picom`, GNOME Mutter, etc.) being active. |
| `Drop a .vrm under the Avatar node` shown | Scene's `Avatar` node has no child | Repeat step 5: drag `Zendaya.vrm` onto `Avatar`, save scene. |
| Avatar pink / untextured | VRM addon not enabled or not restarted after install | Project Settings → Plugins → enable, then restart Godot. |
| `[chat HTTP 0 …]` in label | `zendaya.py` not running, or port 7475 blocked | Start `zendaya.py` first. Check no other process owns 7475 (`netstat -ano | findstr 7475`). |
| Avatar sits in idle forever, mouth never moves | Polling fails silently | Open Godot's *Output* panel (bottom). Check `curl http://127.0.0.1:7475/ai_status` works. |
| Mouth animation looks frozen | Blend shape names differ on your VRM | `pet.gd` `_set_shape()` tries common variants (`A`, `a`, `Mouth_A`, …). If yours uses something else, add it to the candidate list in that function. |
| Labels show garbled glyphs | Default Godot font missing emoji | Cosmetic only — replace `LabelSettings_1` font in the scene. |

---

## 10. Switching between the two VRMs

To swap from `Zendaya.vrm` (default) to `Zendaya-orange.vrm`:

1. Copy `Zendaya-orange.vrm` into `backend/godot_frontend/assets/` if it
   isn't there yet.
2. Open `pet.tscn` in Godot.
3. In the Scene panel, **delete** the current child under `Avatar`.
4. Drag `assets/Zendaya-orange.vrm` onto `Avatar`.
5. Save (Ctrl+S). Press F5.

`pet.gd` discovers blend shapes at runtime, so no code changes needed.

---

## 11. Window-aware behaviours

Once both halves are running, Zendaya watches your foreground window and
acts on it. The Python side runs `zendaya_window_watcher` (4 Hz) and
exposes two new endpoints:

| Endpoint | Purpose |
|---|---|
| `GET /window` | Latest focused-window snapshot + new events (focus_changed, window_opened, window_closed). |
| `POST /window/control` | `{"action": "close|maximize|minimize|focus", "title": "..."}` — runs the matching helper from `zendaya_system_access.py`. |

Behaviour state machine (in `pet.gd`):

- **IDLE_FREESTAND** — no usable target, or the focused window is Zendaya
  herself. She stays put.
- **WALK** — focus changed to a new window. She slowly translates her
  borderless OS window across the desktop toward the new title bar with
  an arm-swing overlay.
- **PERCH** — once within ~30 px of the title bar she lands on it
  (head-turn reaction) and tracks small moves/resizes.
- **SLEEP** — perched on the same window with chat idle for 8 s. Head
  drops, eyes close, label shows `💤`. Wakes on any state or event.

Reactions (one-shot):

| Event | Reaction |
|---|---|
| `focus_changed` | Right-hand wave |
| `window_opened` | Head turn toward the new window |
| `window_closed` | Surprised face + small mouth-open |

Click affordances (on the avatar):

- **Left-click** → POST `focus` for the currently focused window + wave.
- **Right-click** → POST `minimize` + small turn gesture.

Voice / text phrases (handled in `parse_system_command`):

```
maximize chrome
minimize visual studio code
focus chrome   |   switch to chrome
close notepad  |   close the notepad window
list windows
```

To **disable** perch-on-window entirely, edit one line at the top of
`pet.gd`:

```gdscript
const auto_follow := false
```

She'll go back to floating freely wherever you put her window.

Smoke-test from a shell:

```bash
curl http://127.0.0.1:7475/window
# → {"focused": {"title": "...", "rect": [l,t,r,b], "state": "normal"}, "events": []}

curl -X POST http://127.0.0.1:7475/window/control \
  -H "Content-Type: application/json" \
  -d "{\"action\":\"minimize\",\"title\":\"Notepad\"}"
# → {"ok": true, "message": "Minimized: ..."}
```

Known limitations:

- No multi-monitor / mixed-DPI compensation — perch position can be a
  few pixels off on hetero setups.
- "Walking" is a 1-D lerp, not real pathfinding. Looks alive; doesn't
  avoid obstacles.
- Closing a window uses `WM_CLOSE`, so the target app's own
  unsaved-changes dialog (if any) handles confirmation.

---

## What's NOT included (intentional)

- **Real phoneme lipsync** — the mouth oscillates on a sine wave while
  Zendaya is talking. Real lipsync would need streaming audio levels
  from ElevenLabs back to the state server. Future work.
- **Mic input from Godot** — voice still goes through
  `zendaya_voice_listener` in the Python side. Godot is text-only.
- **Auto-reconnect / retry UI** — if `zendaya.py` isn't running, the
  Godot pet just sits in idle and silently fails polls. Restart Python,
  the pet picks up automatically on the next tick.
