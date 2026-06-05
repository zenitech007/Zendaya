# SP-2 · Voice from the HUD — Design

**Date:** 2026-06-05
**Status:** Approved (design); pending implementation plan
**Part of:** "Full AI UI" initiative (SP-2 of 4)

---

## Context

Today Zendaya's speech is produced and played **entirely on the backend
machine**. `backend/zendaya.py`'s `speak_async(text, voice_id)` streams
**ElevenLabs** TTS (`output_format: pcm_22050`) and hands the streaming HTTP
response to `_stream_pcm_playback()`, which plays it through a
`sounddevice.OutputStream` — i.e. **out of the backend's local speakers**.

While playing, that same loop computes per-chunk **RMS amplitude** and
**formant visemes** and pushes them to the state server
(`_state_server.set_amplitude(...)` / `set_visemes(...)`). The HUD already
consumes those over the WebSocket to drive the orb's **lip-sync** — but it only
ever receives the *motion*, never the *audio*. The `pyttsx3` engine
(`speak_system_fallback`) is the offline fallback, also local-speaker.

So today the HUD **looks** like it is talking while the sound comes from the
backend. The user's ask (item 3 of the "full AI UI" request): **"Zendaya speaks
from HUD, not backend."** SP-2 makes Zendaya's actual voice come out of the HUD.

This is the second of four decomposed sub-projects:

- **SP-1 · Command bridge** *(done)* — type commands in the HUD to drive Zendaya + control the HUD.
- **SP-2 · Voice from the HUD** *(this spec)* — Zendaya's TTS audio plays in the browser.
- **SP-3 · In-HUD music player** *(done)* — local music plays out of the HUD's own `<audio>`.
- **SP-4 · Launch & ship** *(not yet designed)* — build-to-static, serve from backend, desktop shortcut.

### Decisions locked in during brainstorming

1. **`zendaya.py` policy:** minimal, surgical edits are **authorized** for SP-2
   (its premise lives in `_stream_pcm_playback`). The file carries the user's
   large pre-existing WIP diff, so it is **never auto-staged** and the WIP is
   never touched (see Staging policy).
2. **Fallback sink (auto):** route voice to the HUD **when at least one HUD
   client is connected**, and fall back to the backend speaker when **none** is.
   Never goes mute; no double audio.
3. **Transport (Approach A):** **tee the live PCM stream over the existing
   WebSocket** and play it in the HUD via the **Web Audio API**. Chosen over a
   file-per-utterance `<audio>` approach (loses streaming latency, complicates
   lip-sync) and browser `speechSynthesis` (loses Zendaya's custom voice + real
   lip-sync).
4. **Lip-sync:** unchanged — the backend keeps pushing amplitude/visemes on the
   same ordered WS; audio and motion stay aligned with no new sync code.

### What already exists (verified)

- `zendaya.py:295` `_stream_pcm_playback(response, samplerate=22050)`: the
  single choke point. Opens `sd.OutputStream`, iterates `response.iter_content`,
  writes int16 samples locally, and pushes amplitude/visemes per chunk.
- `zendaya.py:291` `stop_speaking()` sets `_TTS_STOP` for barge-in; the loop
  breaks on it.
- `zendaya.py:599` `import zendaya_state_server as _state_server` (or `None`
  headless). So new **module-level** functions on the state server are callable
  exactly like `_state_server.set_amplitude(...)` is today.
- `zendaya_state_server.py:266` `_WS_CLIENTS: set` — the connected clients.
  `:57` `_broadcast_state_async(payload)` — thread-safe JSON fan-out to all
  clients via the captured event loop. `:270` `_ws_broadcast` does
  `client.send_text(json.dumps(payload))` and discards dead clients.
- The HUD's `useWebSocket.ts` `onmessage` already branches on payload keys
  (`state`, `text`, `audio_level`, `now_playing`, `visemes`, `action`, …) and
  routes `action` payloads through `dispatchAction`.

---

## Architecture

**Frontend-played, backend-streamed.** The backend remains the synthesizer
(ElevenLabs) and the lip-sync source of truth; the HUD becomes the **audio
sink** when present. The PCM the backend already generates is tee'd over the
existing `/ws` channel instead of being written to the local sound device.

```
ElevenLabs PCM stream
        │  (zendaya.py _stream_pcm_playback)
        ▼
  use_hud = hud_client_count() > 0   ← decided once per utterance
        │
   ┌────┴─────────────────────────┐
   │ use_hud == False             │ use_hud == True
   ▼                              ▼
 sd.OutputStream            _state_server.push_audio_chunk(pcm,id,seq)
 (local speaker)                   │  (rides _broadcast_state_async)
                                   ▼
                         WS  {"audio":{event,…}}  → all HUD clients
                                   ▼
                       useWebSocket → voicePlayer.handle(frame)
                                   ▼
                    VoiceQueue (AudioContext, gapless schedule)
                                   ▼
                              browser audio out
   (amplitude/visemes still pushed in BOTH branches → orb lip-sync unchanged)
```

### 1. Backend routing (connection-aware sink)

Edit `_stream_pcm_playback()` minimally:

- At the top, capture **once**:
  `use_hud = _state_server is not None and _state_server.hud_client_count() > 0`.
  The decision is fixed for the whole utterance — it never flips mid-stream even
  if a client connects/disconnects.
- Open `sd.OutputStream` **only when `not use_hud`**.
- In the chunk loop, after the int16 `samples` are computed:
  - `if use_hud:` push the raw chunk bytes to the state server
    (`_state_server.push_audio_chunk(data, utt_id, seq)`), which base64-encodes
    and broadcasts; **do not** `stream.write`.
  - `else:` `stream.write(samples)` as today.
  - The amplitude/viseme computation runs in **both** branches, unchanged.
- Emit lifecycle frames on the HUD path: `audio_begin(rate, utt_id)` before the
  loop, `audio_end(utt_id)` in `finally`. If `_TTS_STOP` was set (barge-in),
  emit `audio_stop()` so the HUD flushes immediately.
- The `finally` only stops/closes the `OutputStream` if it was opened.
- `speak_system_fallback` (pyttsx3) stays **local-only** — if ElevenLabs is
  unavailable, the backend speaks. Acceptable degradation.

All the heavy lifting (encoding, payload shape, client count) lives in **new
module-level functions on `zendaya_state_server.py`**, so the `zendaya.py` edit
stays tiny and the logic stays unit-testable without `zendaya.py`:

```python
# zendaya_state_server.py
def hud_client_count() -> int:
    return len(_WS_CLIENTS)

# utt_id is generated by zendaya.py (a per-utterance counter) and passed in,
# so begin/chunk/end/stop all carry the same id for one utterance.
def audio_begin(rate: int, utt_id: int) -> None:
    _broadcast_state_async({"audio": {"event": "begin", "rate": rate, "id": utt_id}})

def push_audio_chunk(pcm_bytes: bytes, utt_id: int, seq: int) -> None:
    b64 = base64.b64encode(pcm_bytes).decode("ascii")
    _broadcast_state_async({"audio": {"event": "chunk", "id": utt_id, "seq": seq, "b64": b64}})

def audio_end(utt_id: int) -> None:
    _broadcast_state_async({"audio": {"event": "end", "id": utt_id}})

def audio_stop() -> None:
    _broadcast_state_async({"audio": {"event": "stop"}})
```

### 2. Wire protocol (JSON over the existing `/ws`)

A single nested `audio` key keeps the HUD dispatch to one branch:

| Frame | Shape |
|-------|-------|
| begin | `{"audio":{"event":"begin","rate":22050,"id":7}}` |
| chunk | `{"audio":{"event":"chunk","id":7,"seq":12,"b64":"…"}}` |
| end   | `{"audio":{"event":"end","id":7}}` |
| stop  | `{"audio":{"event":"stop"}}` |

PCM is `int16` mono, base64 (≈59 KB/s at 22050 Hz on localhost — trivial). The
HUD **ignores chunks whose `id` ≠ the current `begin` id**, which drops
post-barge-in stragglers and any utterance a late-joining HUD started mid-way.

### 3. Frontend playback (Web Audio, no React churn)

- **`src/audio/pcmPlayer.ts`** — pure helpers, fully unit-testable:
  - `decodeBase64ToInt16(b64: string): Int16Array`
  - `int16ToFloat32(i16: Int16Array): Float32Array` (divide by 32768)
- **`src/audio/VoiceQueue.ts`** — a class wrapping an `AudioContext` (injected
  via a factory so tests pass a mock). Schedules chunks **gaplessly**:
  - State: `ctx`, `rate`, `nextStartTime`, `currentId`, `sources: Set<AudioBufferSourceNode>`.
  - `begin(rate, id)`: set `currentId`, `rate`, reset `nextStartTime = 0`.
  - `push(float32, id)`: ignore if `id !== currentId`; build a 1-channel
    `AudioBuffer` at `rate`, copy samples, create a source, schedule at
    `start(Math.max(ctx.currentTime, nextStartTime || ctx.currentTime))`,
    advance `nextStartTime` by `buffer.duration`, track the source.
  - `end(id)`: no-op beyond bookkeeping (scheduled sources drain naturally).
  - `stop()`: `source.stop()` all tracked sources, clear, reset `nextStartTime`.
  - `unlock()`: `ctx.resume()` (autoplay policy).
  - `handle(frame)`: routes a wire `audio` frame to begin/push/end/stop, decoding
    via `pcmPlayer` for `chunk`.
- **`src/audio/voicePlayer.ts`** — a **module singleton** `VoiceQueue` (lazily
  constructs a real `AudioContext` in the browser). PCM never touches Zustand,
  so there are **no per-chunk re-renders**.
- **`useWebSocket.ts`** — one new branch in `onmessage`:
  `if (data.audio && typeof data.audio === "object") voicePlayer.handle(data.audio);`
- **`src/hooks/useVoicePlayback.ts`** — mounted once in `App`. Installs a
  one-time `pointerdown`/`keydown` listener that calls `voicePlayer.unlock()`
  and then removes itself, satisfying the browser's autoplay-gesture
  requirement. The HUD already requires interaction, so this is seamless.

### 4. Lip-sync, barge-in, edge cases

- **Lip-sync:** unchanged. Amplitude/visemes ride the same **ordered** WS
  alongside the audio chunks, so the orb stays within tens of ms of the sound.
  No new sync code; the audio path adds only one buffer of scheduling latency.
- **Barge-in:** `stop_speaking()` → `audio.stop` → `VoiceQueue.stop()` cancels
  all scheduled sources and resets `nextStartTime`.
- **HUD disconnects mid-utterance:** the backend keeps pushing to a now-dead
  socket; `_ws_broadcast` already discards dead clients — harmless. The sink
  does not switch to local mid-utterance (acceptable).
- **Multiple HUD tabs:** all connected clients play (broadcast). Normally one.
- **Late-joiner:** a HUD opening mid-sentence missed `begin`, so it ignores that
  utterance's chunks (unknown `id`) and starts clean on the next utterance. The
  connect-time `_snapshot` carries no audio.
- **ElevenLabs unavailable while HUD connected:** `speak_system_fallback`
  (pyttsx3) speaks on the backend speaker. Acceptable; noted.

### 5. Testing

- **Backend (pytest):**
  - `hud_client_count()` returns `len(_WS_CLIENTS)` (seed fake clients).
  - `audio_begin/push_audio_chunk/audio_end/audio_stop` broadcast the exact
    payload shapes (monkeypatch `_broadcast_state_async`, assert the dict;
    assert base64 round-trips to the original PCM bytes).
  - The chunk-encoding is a pure state-server helper, so it is tested without
    importing `zendaya.py`.
- **Frontend (vitest + happy-dom):**
  - `pcmPlayer`: exact-value tests for base64→int16 and int16→float32.
  - `VoiceQueue` against a **mock `AudioContext`**: `push` schedules the right
    buffer count, `nextStartTime` advances by each buffer's duration, `id`
    mismatch is ignored, `stop()` cancels all sources, `unlock()` calls
    `resume()`.
  - `useWebSocket`: an `audio` frame routes to a mocked `voicePlayer.handle`
    (mirrors the SP-3 `music_control` routing test).
  - `useVoicePlayback`: a simulated gesture calls `voicePlayer.unlock()`.
- **Not automatable:** real audible playback — happy-dom has no Web Audio. A
  short manual smoke checklist ships in the plan (start backend + HUD, speak,
  hear it from the browser tab, confirm the backend speaker is silent while the
  HUD is connected and speaks when it is not, confirm barge-in cuts off).

---

## Staging policy

Mirrors SP-3, adapted to the working-tree reality:

- **Frontend** (new `src/audio/*`, `src/hooks/useVoicePlayback.ts`, edits to
  `useWebSocket.ts` and `App.tsx`, and their tests) — these files are **clean /
  new**, so each task **commits** only its named files with
  `git -c commit.gpgsign=false`, and `git status` is checked after every commit.
- **Backend** (`zendaya.py`, `zendaya_state_server.py`, and new backend tests) —
  **DO NOT COMMIT.** `zendaya.py` carries the user's large pre-existing WIP diff,
  and `zendaya_state_server.py` already carries **uncommitted SP-3 edits** in the
  working tree. The whole backend change set is left **unstaged/untracked** for
  the user to review and commit themselves.
- **Never** `git add -A`, `git add .`, or `git add -u`. Stage only the exact
  frontend files named in each task. Never touch the protected paths
  (`zendaya_system_access.py`, `pyproject.toml`, `.gitignore`,
  `zendaya_logs/assistant_history.json`) or anything under `.claude/` /
  `.superpowers/`.

## Out of scope (YAGNI)

- Spotify audio in the HUD (SP-3 keeps Spotify remote-control-only).
- A binary-WebSocket audio channel (base64-in-JSON is plenty on localhost).
- HUD-side viseme analysis (the backend already computes them).
- A persistent "click to enable voice" UI hint (the first interaction unlocks
  silently; revisit only if it proves confusing).
- pyttsx3-to-HUD streaming (the fallback stays local).
