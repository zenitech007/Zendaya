# SP-3 · In-HUD Music Player — Design

**Date:** 2026-06-04
**Status:** Approved (design); pending implementation plan
**Part of:** "Full AI UI" initiative (SP-3 of 4)

---

## Context

Today the HUD's `MusicPlayer.tsx` is only a **now-playing display + remote
control**: it renders `store.nowPlaying` (art, track, artist, progress) and its
transport buttons `POST` plain-text commands (`"pause music"`, `"next track"`)
to `/chat`. The **actual audio is produced outside the HUD**:
`backend/zendaya_spotify.py` either drives the **Spotify desktop app** (Web API
+ `_launch_spotify_desktop`) or, for local files, calls
`subprocess.Popen(["cmd","/c","start", …])` to open them in the **Windows
default media player** (`local_music_play`). The backend broadcasts a
`now_playing` payload over WS → `useWebSocket.ts` maps it into
`store.nowPlaying`.

So the HUD *shows and controls* music but never *plays* it. The user's ask:
"play all music through the HUD music player and **not** open Spotify app or
local music player." SP-3 makes the audio actually come out of the HUD itself.

This is the third of four decomposed sub-projects:

- **SP-1 · Command bridge** *(done)* — type commands in the HUD to drive Zendaya + control the HUD.
- **SP-2 · Voice from the HUD** *(not yet designed)* — Zendaya's TTS audio plays in the browser.
- **SP-3 · In-HUD music player** *(this spec)* — local music plays out of the HUD's own `<audio>`.
- **SP-4 · Launch & ship** *(not yet designed)* — build-to-static, serve from backend, desktop shortcut.

### Decisions locked in during brainstorming

1. **Audio source:** **local library first.** Spotify stays remote-control-only
   (drives the desktop app, as today) until a later phase. The Spotify Web
   Playback SDK (Premium-gated) is out of scope.
2. **Control model:** **voice/chat-driven.** Zendaya picks tracks from spoken/
   typed commands; the HUD shows now-playing + a working transport
   (play/pause/next/prev, auto-advance, seek). No browse/search panel.
3. **Backend edits authorized:** `backend/zendaya_spotify.py` may be edited (it
   is untracked WIP, **not** on the never-touch protected list). New routes go
   on the **clean, tracked** `backend/zendaya_state_server.py`. The protected
   `backend/zendaya.py` stays **untouched**. The WIP file is **never
   auto-staged**; the diff is shown and the user controls commit/staging.
4. **Architecture:** **frontend-authoritative (Approach A).** The HUD `<audio>`
   element is the single playback authority; the backend selects + serves +
   stores/broadcasts.

### What already exists (verified)

- `local_music_play(query)` in `zendaya_spotify.py`: `_pick_local_track` then
  `subprocess.Popen` (the default-player launch we are removing), then records
  `_LOCAL_NOW` (path/started_at/duration/track/artist/is_playing).
- `now_playing_payload()`: prefers Spotify; else returns the `_LOCAL_NOW`
  snapshot with **wall-clock-estimated** progress + a 2 s expiry. Carries
  track/artist/progress/duration/source — **no file path or stream URL.**
- `zendaya_state_server.py` owns the FastAPI `app` and every route (`/chat`,
  `/ws`, `/health`, `/telemetry`, …), the `set_now_playing()` /
  `set_action()` broadcast helpers, and the now-playing poll loop's fan-out.
  `FileResponse` is already imported.
- `backend/zendaya.py` (protected) routes `play` intents → `spotify_command` →
  broadcasts `now_playing_payload()`, and runs a periodic now-playing **poll
  loop** that re-broadcasts `now_playing_payload()`.
- Frontend: `useWebSocket.ts` maps `now_playing` → `store.setNowPlaying` and
  dispatches named `action`s via `dispatchAction` (delegating to
  `hudControls.ts`). `MusicPlayer.tsx` renders `store.nowPlaying`.

## Goals

1. Local tracks **play out of the HUD's own `<audio>` element** — no external
   app opens — triggered by Zendaya's existing voice/chat "play …" intent.
2. A working in-HUD transport: play/pause, next/prev, **auto-advance** through
   the folder, **click-to-seek**, with an **accurate** progress bar.
3. Voice transport ("pause", "next") nudges the HUD's player.
4. **No drift:** the backend's broadcast snapshot always matches what the HUD is
   actually playing (single-writer discipline).
5. `backend/zendaya.py` untouched; new routes only on the clean state server.

## Non-goals (deferred, not dropped)

- Spotify-in-browser (Web Playback SDK / Premium).
- Browse/search library panel; click-to-start-a-track UI.
- Volume slider, shuffle, repeat, queue persistence, local album art.
- Any SP-2/SP-4 feature.

## Architecture

**Core principle:** the HUD `<audio>` is the single source of truth for
*playback*. The backend **selects** a track, **serves** its bytes, and
**stores + broadcasts** a now-playing snapshot. After the initial selection,
**the HUD is the single writer** of the backend's local now-playing state (via a
sync endpoint), so there is never a second queue to drift. Voice transport
commands are *nudges*: the backend fans out a `music_control` action, the HUD
applies it to `<audio>`, then writes the new state back. Both existing broadcast
channels are reused — `now_playing` for metadata, `action` for control.

### New wire contract

- `now_playing` payload (local source only) gains:
  - `stream_url`: e.g. `/music/stream/<track_id>`
  - `track_id`: opaque stable id (sha1(abspath)[:16])
- New `action` type: `music_control` with payload `{cmd: "play"|"pause"|"next"|"prev"}`.

### New HTTP routes (on `zendaya_state_server.py`, never `zendaya.py`)

- `GET /music/list` → `[{id, title, artist, duration_ms, stream_url}]` (ordered;
  builds the HUD's queue).
- `GET /music/stream/{id}` → `FileResponse(path)` (FastAPI provides HTTP Range →
  seeking); `resolve(id) → None` ⇒ `404`.
- `POST /music/now` → body `{track_id, is_playing, position_ms}` (or
  `{track_id: null}` to clear). The HUD writes back so the backend's broadcast
  snapshot equals what is actually playing.

### End-to-end data flow

1. **"play some jazz"** → `zendaya.py` (untouched) → `spotify_command` →
   `local_music_play(query)` → picks a file, records `_LOCAL_NOW` with
   `track_id` (**no subprocess**) → existing code broadcasts `now_playing` with
   `stream_url` + `track_id`.
2. HUD `MusicPlayer` sees a **new** `trackId` → `<audio>.src = streamUrl` →
   plays. It fetches `/music/list` once to build its queue, locating the current
   track by `trackId`.
3. **Transport buttons** act directly on `<audio>` (instant play/pause, real
   seek) and queue (next/prev load the adjacent track's `streamUrl`); the
   progress bar reads the **real** `audio.currentTime`. Each change →
   `POST /music/now`.
4. **Track `ended`** → auto-advance to the next queue track → load + play →
   `POST /music/now`.
5. **Voice "pause"/"next"** → `spotify_command` (local mode) → `emit_control` →
   `set_action("music_control", …)` → WS → `dispatchAction` → `pushMusicCmd` →
   `MusicPlayer` effect applies it to `<audio>`/queue → `POST /music/now`.
6. The now-playing **poll loop** (in protected `zendaya.py`) keeps
   re-broadcasting the snapshot — but it is now an idempotent echo of what the
   HUD wrote, so the HUD sees the same `trackId` and **ignores it** (no reload).

### File map

| File | Change | Responsibility |
|---|---|---|
| `backend/zendaya_hud_music.py` | **NEW** (committable) | `scan` + `list_tracks`, stable `track_id`, `resolve(id)→Path` (containment-checked), `select(query)`, `emit_control(cmd)`, `stream_url_for(id)` |
| `backend/zendaya_spotify.py` | **EDIT** (WIP, surgical) | `local_music_play`: no subprocess, delegate to `select`; `now_playing_payload` local branch: add `stream_url`/`track_id`, drop wall-clock expiry; `spotify_command` transport branches: local mode → `emit_control`; add `set_local_now` / `clear_local_now` setters |
| `backend/zendaya_state_server.py` | **EDIT** (clean/tracked) | add the three `/music/*` routes |
| `backend/zendaya.py` | **UNTOUCHED** | already routes `play` + broadcasts now_playing + poll loop |
| `src/store/zendayaStore.ts` | EDIT | `NowPlaying` += `streamUrl?`/`trackId?`; add `musicCmd: {cmd, seq} \| null` + `pushMusicCmd(cmd)` |
| `src/hooks/useWebSocket.ts` | EDIT | map `stream_url`/`track_id`; route `music_control` action → `pushMusicCmd` |
| `src/api/music.ts` | **NEW** | `fetchTrackList()`, `streamUrl()` (reuse `backendHttpOrigin()`); `postNowPlaying()` |
| `src/music/queue.ts` | **NEW** (pure) | `nextTrack(list, currentId)` / `prevTrack(list, currentId)` |
| `src/components/HUD/MusicPlayer.tsx` | EDIT (significant) | `<audio>` wiring, local transport, real progress/seek, auto-advance, react to `musicCmd`, `POST /music/now` |

## Implementation detail

### Backend

**`zendaya_hud_music.py` (new, committable):**
- `track_id` = `sha1(os.path.abspath(path)).hexdigest()[:16]` — stable, opaque
  (no path leaked into URLs).
- `resolve(id)`: scan music dirs, match by id, then **validate containment**
  (`os.path.commonpath([dir, resolved]) == dir`) before returning; unknown id →
  `None`.
- `select(query)`: reuse `_pick_local_track`; return
  `{path, id, title, artist, duration_ms}`.
- `emit_control(cmd)`: **lazy** `import zendaya_state_server` (avoids circular
  import) → `set_action("music_control", {"cmd": cmd})`.
- `stream_url_for(id)` → `f"/music/stream/{id}"`.

**`zendaya_spotify.py` edits (surgical):**
- `local_music_play`: delete the `subprocess.Popen` block; call
  `zendaya_hud_music.select`; set `_LOCAL_NOW` (incl. `track_id`); return the
  same `"Playing '…'"` string (Zendaya still speaks it).
- `now_playing_payload` local branch: return the stored `_LOCAL_NOW` snapshot
  **as-is** plus `stream_url`/`track_id`; **remove** the wall-clock
  `elapsed`/expiry math (the HUD owns lifecycle).
- `spotify_command`: in the pause/resume/next/previous branches, when
  `not spotify_available()` → `zendaya_hud_music.emit_control(...)` and return a
  short confirmation instead of calling the Spotify API.
- Add `set_local_now(track_id, is_playing, position_ms)` and
  `clear_local_now()` used by the `/music/now` route (single writer = the HUD).

**`zendaya_state_server.py` edits (clean/tracked):** the three routes.
`/music/stream/{id}` → `FileResponse(path)`; `404` when `resolve→None`. Confirm
`CORSMiddleware` is already present (the existing cross-origin `POST /chat`
works, so it should be): `<audio>` *playback* needs no CORS, but the
`fetch('/music/list')` and `POST /music/now` do.

### Frontend

- **`queue.ts`** (pure): `nextTrack` / `prevTrack` — sequential, wrap-around;
  current-not-found → first track; empty list → `null`.
- **`api/music.ts`**: `fetchTrackList()` GETs `/music/list`;
  `streamUrl(idOrTrack)` from `backendHttpOrigin()`; `postNowPlaying(body)` →
  `POST /music/now` (best-effort, ignores failure).
- **store**: `NowPlaying` += `streamUrl?`, `trackId?`; new
  `musicCmd: {cmd: string; seq: number} | null` + `pushMusicCmd(cmd)` (monotonic
  `seq` so a repeated command still re-fires the effect).
- **`useWebSocket.ts`**: map `stream_url`→`streamUrl`, `track_id`→`trackId`; add
  `case "music_control": pushMusicCmd(payload.cmd)`.
- **`MusicPlayer.tsx`**: add `<audio ref>`. **Reload only when `trackId` changes
  to a new value** (ignore idempotent echoes). Buttons → local `<audio>`/queue
  ops. Progress bar reads `audio.currentTime` / `audio.duration` and is
  click-to-seek. `onEnded` → auto-advance. `useEffect` on `musicCmd.seq` applies
  voice commands. After any local change → `postNowPlaying`.

## Error handling

- No music dir / no tracks → `local_music_play` returns `None` (unchanged) →
  Zendaya speaks the existing "set `ZENDAYA_MUSIC_DIR`" message; `/music/list` →
  `[]`; the player card stays hidden.
- `/music/stream` `404` or `<audio>` `error` event → log + brief inline
  "couldn't load track", then auto-advance to the next track (do not crash).
- Backend offline → `fetchTrackList` rejects → queue empty, next/prev no-op; the
  card simply won't appear.
- Path traversal → `resolve` containment check → `404`.

## Testing

**Backend (pytest):**
- `zendaya_hud_music`: `track_id` stability; `resolve` valid id → path, unknown
  id → `None`, traversal id → `None`; `list_tracks` shape/order.
- `local_music_play`: temp music dir with fake audio files + `subprocess.Popen`
  patched to **raise if called** (proves no subprocess); asserts `_LOCAL_NOW`
  set with `track_id`.
- `now_playing_payload` local branch: snapshot has `stream_url`/`track_id`, no
  wall-clock expiry.
- Routes via FastAPI `TestClient`: `/music/list` JSON; `/music/stream/{id}` →
  `200` + `Accept-Ranges` + bytes, bad id → `404`; `/music/now` updates + clears
  state.

**Frontend (Vitest / happy-dom):**
- `queue.ts` navigation (sequential, wrap, not-found, empty).
- `api/music.ts` with mocked `fetch` (list parse, URL build, `postNowPlaying`).
- store: `NowPlaying` mapping + `musicCmd` `seq` increment.
- `dispatchAction("music_control")` → `pushMusicCmd`.
- `MusicPlayer` renders `<audio>` with the correct `src`. (Real play/pause/seek
  side-effects are happy-dom no-ops → covered by manual smoke.)

**Manual live smoke:** real backend + music folder → "play some music" plays in
the HUD; buttons, click-to-seek, auto-advance, and voice pause/next all work;
**no Windows player opens**.

## Constraints honored

- `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`,
  `.gitignore`, `zendaya_logs/assistant_history.json` — **never touched/staged**.
- `backend/zendaya_spotify.py` (untracked WIP) — edited per explicit user
  approval; **never auto-staged**; diff surfaced for the user to commit.
- The pre-existing uncommitted working-tree diff is left alone; staging is
  per-file and explicit (no `git add -A/-u/.`).
- Commits disable signing (`git -c commit.gpgsign=false commit …`); `git status`
  is checked after each commit to confirm no protected paths were swept in.
