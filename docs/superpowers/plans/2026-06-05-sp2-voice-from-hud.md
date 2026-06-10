# SP-2: Voice from the HUD — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Zendaya's real ElevenLabs TTS voice play out of the HUD (browser) when a HUD client is connected, falling back to the backend speaker when none is, while keeping the existing orb lip-sync intact.

**Architecture:** The backend tees live PCM (already streaming through `_stream_pcm_playback`) over the existing `/ws` WebSocket as base64-in-JSON frames. The sink (HUD vs. local speaker) is decided **once per utterance** based on `hud_client_count()` and never flips mid-stream. In the HUD, a singleton `VoiceQueue` (its own Web Audio `AudioContext`) plays the PCM gaplessly. The queue is fed directly from `useWebSocket`'s `onmessage` — NOT through Zustand — to avoid a React re-render per audio chunk. Amplitude/viseme broadcasts continue unchanged on the same ordered socket, so lip-sync is untouched.

**Tech Stack:** Backend — Python 3.14, FastAPI/Starlette, pytest, numpy, sounddevice, ElevenLabs streaming TTS (pcm_22050). Frontend — React 18 + TypeScript, Zustand 4, Vite 5, Vitest 2 + happy-dom, @testing-library/react, Web Audio API.

---

## Wire protocol (4 frame types, all nested under the `audio` key)

```jsonc
{ "audio": { "event": "begin", "rate": 22050, "id": 7 } }            // utterance starts
{ "audio": { "event": "chunk", "id": 7, "seq": 12, "b64": "…" } }    // one PCM int16 window, base64
{ "audio": { "event": "end",   "id": 7 } }                           // no more chunks for id 7
{ "audio": { "event": "stop" } }                                     // barge-in: flush everything now
```

The HUD ignores any `chunk`/`end` whose `id` ≠ the current `begin` id (drops barge-in stragglers and late-joiner echoes). WebSocket delivery is ordered, so `seq` is informational only — the HUD schedules chunks in arrival order.

## Staging policy (CRITICAL — read before committing anything)

- **Backend tasks (Task 1, Task 2) DO NOT COMMIT.** `backend/zendaya.py` carries the user's pre-existing WIP diff and `backend/zendaya_state_server.py` already has uncommitted SP-3 edits. Leave all backend changes (including the new test file) **unstaged and untracked** for the user to review. Run the backend tests to prove green, then stop — no `git add`, no commit.
- **Frontend tasks (Task 3–7) commit per task**, staging ONLY the exact files named in that task's commit step. Never `git add -A` / `git add .` / `git add -u`.
- Every commit disables signing: `git -c commit.gpgsign=false commit ...`.
- After every commit, run `git status` and confirm no protected paths (`backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `.gitignore`, `zendaya_logs/assistant_history.json`, anything under `.superpowers/` or `.claude/`) were swept in.
- Plan file and spec are NOT committed (left untracked, consistent with prior plans in this repo).

## Test commands (copy exactly)

- Backend (run from `backend/`): `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_voice_from_hud.py -v`
  - Benign `PytestConfigWarning: Unknown config option: asyncio_mode/maxfail/timeout` — ignore.
- Frontend single file: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- <substring>`
- Frontend full suite: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test`
- Frontend build: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run build`
- **Bash cwd persists between calls.** After a `cd .../backend`, prefix the next npm call with `cd C:/Users/IKA/Zendaya &&` or it resolves `backend/zendaya-hud-react` and fails ENOENT.

## File structure

| File | Responsibility | Task |
|------|----------------|------|
| `backend/zendaya_state_server.py` (modify) | `import base64`; add `hud_client_count()` + `audio_begin/push_audio_chunk/audio_end/audio_stop()` broadcast helpers | 1 |
| `backend/zendaya.py` (modify) | utterance-id counter; `_stream_pcm_playback` picks HUD vs. local sink once per utterance; `stop_speaking()` also emits `audio_stop` | 2 |
| `backend/tests/test_voice_from_hud.py` (create) | tests for the state-server frames + the `_stream_pcm_playback` routing decision | 1, 2 |
| `zendaya-hud-react/src/audio/pcmPlayer.ts` (create) | pure helpers: `decodeBase64ToInt16`, `int16ToFloat32` | 3 |
| `zendaya-hud-react/src/audio/VoiceQueue.ts` (create) | class over an `AudioContext`: `unlock/handle/stop`, gapless scheduling | 4 |
| `zendaya-hud-react/src/audio/voicePlayer.ts` (create) | module singleton wrapping one `VoiceQueue` | 5 |
| `zendaya-hud-react/src/hooks/useWebSocket.ts` (modify) | one branch: route `data.audio` → `voicePlayer.handle` | 6 |
| `zendaya-hud-react/src/hooks/useVoicePlayback.ts` (create) | first-gesture `voicePlayer.unlock()`; mounted in `App.tsx` | 7 |
| `zendaya-hud-react/src/App.tsx` (modify) | call `useVoicePlayback()` | 7 |

---

## Task 1: State-server audio broadcast frames

Adds the backend functions the HUD listens for. Pure broadcast helpers that serialize PCM to base64-in-JSON and report how many HUD clients are connected. **This task does NOT commit** (see Staging policy).

**Files:**
- Modify: `backend/zendaya_state_server.py` (add `import base64` after line 18 `import json`; add 5 functions after `_broadcast_state_async`, which ends at line 65)
- Test: `backend/tests/test_voice_from_hud.py` (create)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_voice_from_hud.py`:

```python
"""SP-2 — voice-from-HUD: state-server frames + _stream_pcm_playback routing."""
import base64
import sys
import types

import zendaya_state_server as ss


def _capture(monkeypatch):
    """Capture every payload passed to _broadcast_state_async."""
    sent = []
    monkeypatch.setattr(ss, "_broadcast_state_async", lambda p: sent.append(p))
    return sent


def test_hud_client_count_reflects_ws_clients(monkeypatch):
    monkeypatch.setattr(ss, "_WS_CLIENTS", set())
    assert ss.hud_client_count() == 0
    fake_clients = {object(), object()}
    monkeypatch.setattr(ss, "_WS_CLIENTS", fake_clients)
    assert ss.hud_client_count() == 2


def test_audio_begin_frame(monkeypatch):
    sent = _capture(monkeypatch)
    ss.audio_begin(22050, 7)
    assert sent == [{"audio": {"event": "begin", "rate": 22050, "id": 7}}]


def test_push_audio_chunk_base64_encodes(monkeypatch):
    sent = _capture(monkeypatch)
    pcm = b"\x01\x02\x03\x04"
    ss.push_audio_chunk(pcm, 7, 3)
    assert len(sent) == 1
    frame = sent[0]["audio"]
    assert frame["event"] == "chunk"
    assert frame["id"] == 7
    assert frame["seq"] == 3
    assert base64.b64decode(frame["b64"]) == pcm


def test_audio_end_frame(monkeypatch):
    sent = _capture(monkeypatch)
    ss.audio_end(7)
    assert sent == [{"audio": {"event": "end", "id": 7}}]


def test_audio_stop_frame(monkeypatch):
    sent = _capture(monkeypatch)
    ss.audio_stop()
    assert sent == [{"audio": {"event": "stop"}}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_voice_from_hud.py -v`
Expected: FAIL — `AttributeError: module 'zendaya_state_server' has no attribute 'hud_client_count'` (and the four `audio_*` functions).

- [ ] **Step 3: Add `import base64`**

In `backend/zendaya_state_server.py`, after line 18 (`import json`):

```python
import asyncio
import json
import base64
```

- [ ] **Step 4: Add the five functions after `_broadcast_state_async`**

`_broadcast_state_async` ends at line 65 with its `pass`. Insert these functions immediately after it (before `def set_panel` at line 68):

```python
def hud_client_count() -> int:
    """How many HUD WebSocket clients are currently connected.

    zendaya.py reads this once per utterance to decide whether the TTS voice
    plays in the browser (>=1 client) or on the local speaker (0 clients).
    """
    try:
        return len(_WS_CLIENTS)
    except Exception:
        return 0


def audio_begin(rate: int, utt_id: int) -> None:
    """Announce the start of a TTS utterance the HUD should play."""
    _broadcast_state_async({"audio": {"event": "begin", "rate": int(rate), "id": int(utt_id)}})


def push_audio_chunk(pcm_bytes: bytes, utt_id: int, seq: int) -> None:
    """Tee one PCM int16 window to the HUD as base64."""
    try:
        b64 = base64.b64encode(pcm_bytes).decode("ascii")
    except Exception:
        return
    _broadcast_state_async({"audio": {"event": "chunk", "id": int(utt_id), "seq": int(seq), "b64": b64}})


def audio_end(utt_id: int) -> None:
    """Signal that no further chunks will arrive for this utterance."""
    _broadcast_state_async({"audio": {"event": "end", "id": int(utt_id)}})


def audio_stop() -> None:
    """Barge-in: tell the HUD to flush any queued/playing audio immediately."""
    _broadcast_state_async({"audio": {"event": "stop"}})
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_voice_from_hud.py -v`
Expected: PASS (5 passed). The `_stream_pcm_playback` routing tests are added in Task 2.

- [ ] **Step 6: Do NOT commit**

Backend changes stay unstaged (Staging policy). Run `cd C:/Users/IKA/Zendaya && git status` and confirm `backend/zendaya_state_server.py` shows `M` and `backend/tests/test_voice_from_hud.py` shows as untracked — leave both as-is.

---

## Task 2: `_stream_pcm_playback` picks HUD vs. local sink per utterance

Teaches the existing PCM playback choke point to tee to the HUD when a client is connected (skipping the local `sd.OutputStream` entirely for that utterance), and to fall back to the local speaker when none is. Amplitude + visemes are pushed on BOTH paths so lip-sync is unchanged. **This task does NOT commit.**

**Files:**
- Modify: `backend/zendaya.py` (`_TTS_STOP` block at lines 288–293; `_stream_pcm_playback` at lines 295–362)
- Test: `backend/tests/test_voice_from_hud.py` (append)

- [ ] **Step 1: Write the failing test (append to the test file)**

Append to `backend/tests/test_voice_from_hud.py`:

```python
class _FakeResponse:
    def __init__(self, chunks):
        self._chunks = chunks

    def iter_content(self, chunk_size=4096):
        for c in self._chunks:
            yield c


class _FakeStateServer:
    def __init__(self, client_count):
        self._n = client_count
        self.begin_calls = []
        self.chunk_calls = []
        self.end_calls = []
        self.amp_calls = []
        self.viseme_calls = []

    def hud_client_count(self):
        return self._n

    def audio_begin(self, rate, utt_id):
        self.begin_calls.append((rate, utt_id))

    def push_audio_chunk(self, pcm, utt_id, seq):
        self.chunk_calls.append((pcm, utt_id, seq))

    def audio_end(self, utt_id):
        self.end_calls.append(utt_id)

    def audio_stop(self):
        pass

    def set_amplitude(self, level):
        self.amp_calls.append(level)

    def set_visemes(self, weights):
        self.viseme_calls.append(weights)


class _FakeStream:
    instances = []

    def __init__(self, *a, **k):
        _FakeStream.instances.append(self)
        self.writes = []

    def start(self):
        pass

    def write(self, samples):
        self.writes.append(samples)

    def stop(self):
        pass

    def close(self):
        pass


def _load_zendaya():
    import importlib
    return importlib.import_module("zendaya")


def test_routes_to_hud_when_client_connected(monkeypatch):
    z = _load_zendaya()
    fake_ss = _FakeStateServer(client_count=1)
    _FakeStream.instances = []
    monkeypatch.setattr(z, "_state_server", fake_ss)
    monkeypatch.setattr(z.sd, "OutputStream", _FakeStream)
    # 8 bytes => 4 int16 samples per chunk
    resp = _FakeResponse([b"\x00\x10\x00\x20\x00\x30\x00\x40", b"\x01\x10\x01\x20\x01\x30\x01\x40"])
    z._stream_pcm_playback(resp)
    # HUD path: begin once, a chunk per window, end once — and NO local stream.
    assert len(fake_ss.begin_calls) == 1
    assert len(fake_ss.chunk_calls) == 2
    assert len(fake_ss.end_calls) == 1
    assert _FakeStream.instances == []
    # Lip-sync still fed.
    assert len(fake_ss.amp_calls) >= 1


def test_routes_to_local_speaker_when_no_client(monkeypatch):
    z = _load_zendaya()
    fake_ss = _FakeStateServer(client_count=0)
    _FakeStream.instances = []
    monkeypatch.setattr(z, "_state_server", fake_ss)
    monkeypatch.setattr(z.sd, "OutputStream", _FakeStream)
    resp = _FakeResponse([b"\x00\x10\x00\x20\x00\x30\x00\x40"])
    z._stream_pcm_playback(resp)
    # Local path: a real stream was opened and written to; HUD frames NOT sent.
    assert len(_FakeStream.instances) == 1
    assert len(_FakeStream.instances[0].writes) >= 1
    assert fake_ss.begin_calls == []
    assert fake_ss.chunk_calls == []
    # Lip-sync still fed.
    assert len(fake_ss.amp_calls) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_voice_from_hud.py -k routes -v`
Expected: FAIL — current `_stream_pcm_playback` always opens `sd.OutputStream` and never calls `audio_begin`, so `test_routes_to_hud_when_client_connected` fails on `_FakeStream.instances == []`.

- [ ] **Step 3: Add the utterance-id counter and `audio_stop` to barge-in**

In `backend/zendaya.py`, replace the `_TTS_STOP` / `stop_speaking` block (lines 288–293):

```python
_TTS_PCM_RATE = 22050  # ElevenLabs pcm_22050 — fastest streaming, no MP3 decode
_TTS_STOP = threading.Event()
_TTS_UTT_ID = 0  # monotonic per-utterance id; the HUD drops chunks from stale ids

def _next_utt_id() -> int:
    global _TTS_UTT_ID
    _TTS_UTT_ID += 1
    return _TTS_UTT_ID

def stop_speaking():
    """Cut off any in-progress TTS playback. Used for barge-in from voice listener."""
    _TTS_STOP.set()
    # Tell any HUD client to flush its audio queue immediately.
    if _state_server is not None:
        try:
            _state_server.audio_stop()
        except Exception:
            pass
```

- [ ] **Step 4: Rewrite `_stream_pcm_playback` to pick the sink once per utterance**

Replace the whole function body (lines 295–362) with:

```python
def _stream_pcm_playback(response, samplerate: int = _TTS_PCM_RATE):
    """Play raw PCM int16 chunks from a streaming HTTP response with low latency.

    Sink is chosen ONCE per utterance: if a HUD client is connected the PCM is
    teed to the browser over the WebSocket (and the local speaker is skipped);
    otherwise it plays on the local sounddevice stream. Amplitude + visemes are
    pushed on BOTH paths so the orb lip-sync is identical either way.
    """
    import numpy as _np

    utt_id = _next_utt_id()
    to_hud = False
    if _state_server is not None:
        try:
            to_hud = _state_server.hud_client_count() > 0
        except Exception:
            to_hud = False

    stream = None
    if to_hud:
        try:
            _state_server.audio_begin(samplerate, utt_id)
        except Exception:
            to_hud = False  # if we can't announce, fall back to local speaker

    if not to_hud:
        stream = sd.OutputStream(samplerate=samplerate, channels=1, dtype="int16")
        stream.start()

    try:
        leftover = b""
        seq = 0
        for chunk in response.iter_content(chunk_size=4096):
            if _TTS_STOP.is_set():
                break
            if not chunk:
                continue
            data = leftover + chunk
            if len(data) % 2:
                leftover = data[-1:]
                data = data[:-1]
            else:
                leftover = b""
            if data:
                samples = _np.frombuffer(data, dtype=_np.int16)
                if to_hud:
                    try:
                        _state_server.push_audio_chunk(data, utt_id, seq)
                        seq += 1
                    except Exception:
                        pass
                elif stream is not None:
                    stream.write(samples)
                if _state_server is not None and len(samples):
                    try:
                        samples_f32 = samples.astype(_np.float32) / 32768.0
                        rms = float(_np.sqrt(_np.mean(samples_f32 ** 2)))
                        # Speech RMS rarely exceeds ~0.25; scale into a usable 0–1 range.
                        level = min(1.0, rms * 4.0)
                        _state_server.set_amplitude(level)
                        try:
                            import zendaya_visemes as _viz
                            # Real formant-based weights derived from the PCM window.
                            # Falls back to the char-schedule player if analysis errors.
                            try:
                                _viz.ANALYZER.samplerate = samplerate
                                weights = _viz.ANALYZER.analyze(samples_f32, rms)
                            except Exception:
                                weights = _viz.PLAYER.current()
                                weights = {k: v * level for k, v in weights.items()}
                            _state_server.set_visemes(weights)
                        except Exception:
                            pass
                    except Exception:
                        pass
    finally:
        if to_hud and _state_server is not None:
            try:
                _state_server.audio_end(utt_id)
            except Exception:
                pass
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        if _state_server is not None:
            try:
                _state_server.set_amplitude(0.0)
                _state_server.set_visemes({"aa": 0, "ih": 0, "ee": 0, "oh": 0, "ou": 0})
            except Exception:
                pass
        try:
            import zendaya_visemes as _viz
            _viz.PLAYER.stop()
            try:
                _viz.ANALYZER.reset()
            except Exception:
                pass
        except Exception:
            pass
```

- [ ] **Step 5: Run the full backend test file to verify it passes**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_voice_from_hud.py -v`
Expected: PASS (7 passed — 5 from Task 1 + 2 routing tests).

- [ ] **Step 6: Do NOT commit**

Run `cd C:/Users/IKA/Zendaya && git status`. Confirm `backend/zendaya.py` and `backend/zendaya_state_server.py` show `M` and `backend/tests/test_voice_from_hud.py` is untracked. Leave ALL of them unstaged — the user reviews backend changes manually. Do not run `git add` on any backend path.

---

## Task 3: `pcmPlayer.ts` pure decode helpers

Two pure, dependency-free functions: base64 → `Int16Array`, and `Int16Array` → `Float32Array` (normalized to [-1, 1]). These are the only audio code that's trivially unit-testable without a Web Audio context, so they get their own file. **Frontend task — commits.**

**Files:**
- Create: `zendaya-hud-react/src/audio/pcmPlayer.ts`
- Test: `zendaya-hud-react/src/__tests__/pcmPlayer.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/pcmPlayer.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { decodeBase64ToInt16, int16ToFloat32 } from "../audio/pcmPlayer";

// Little-endian int16 [256, 513] => bytes [0x00,0x01, 0x01,0x02] => base64 "AAEBAg=="
const B64_TWO_SAMPLES = "AAEBAg==";

describe("decodeBase64ToInt16", () => {
  it("decodes base64 PCM into little-endian Int16", () => {
    const out = decodeBase64ToInt16(B64_TWO_SAMPLES);
    expect(Array.from(out)).toEqual([256, 513]);
  });

  it("returns an empty array for empty input", () => {
    expect(decodeBase64ToInt16("").length).toBe(0);
  });

  it("drops a trailing odd byte rather than throwing", () => {
    // 3 bytes -> only one whole int16 sample
    const b64 = btoa(String.fromCharCode(0x00, 0x01, 0x7f));
    const out = decodeBase64ToInt16(b64);
    expect(out.length).toBe(1);
    expect(out[0]).toBe(256);
  });
});

describe("int16ToFloat32", () => {
  it("normalizes into [-1, 1]", () => {
    const out = int16ToFloat32(Int16Array.from([0, 32767, -32768]));
    expect(out[0]).toBeCloseTo(0, 5);
    expect(out[1]).toBeCloseTo(0.99997, 4);
    expect(out[2]).toBeCloseTo(-1, 5);
  });

  it("preserves length", () => {
    expect(int16ToFloat32(Int16Array.from([1, 2, 3, 4])).length).toBe(4);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- pcmPlayer`
Expected: FAIL — cannot resolve `../audio/pcmPlayer`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/audio/pcmPlayer.ts`:

```ts
/**
 * pcmPlayer.ts — pure PCM decode helpers (no Web Audio dependency).
 *
 * The backend tees ElevenLabs pcm_22050 (signed 16-bit little-endian, mono)
 * over the WebSocket as base64. These two functions turn one base64 window
 * into the Float32Array a Web Audio AudioBuffer wants.
 */

/** Decode base64 → little-endian Int16Array. A trailing odd byte is dropped. */
export function decodeBase64ToInt16(b64: string): Int16Array {
  if (!b64) return new Int16Array(0);
  const binary = atob(b64);
  const len = binary.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);
  // View as Int16 over the whole-sample byte length (drop a trailing odd byte).
  const sampleCount = len >> 1;
  const out = new Int16Array(sampleCount);
  const view = new DataView(bytes.buffer);
  for (let i = 0; i < sampleCount; i++) {
    out[i] = view.getInt16(i * 2, true /* little-endian */);
  }
  return out;
}

/** Normalize Int16 PCM into Web-Audio float range [-1, 1]. */
export function int16ToFloat32(samples: Int16Array): Float32Array {
  const out = new Float32Array(samples.length);
  for (let i = 0; i < samples.length; i++) {
    out[i] = samples[i] / 32768;
  }
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- pcmPlayer`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/audio/pcmPlayer.ts zendaya-hud-react/src/__tests__/pcmPlayer.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add pure PCM decode helpers for voice playback"
git status
```

Confirm no protected paths were staged.

---

## Task 4: `VoiceQueue.ts` gapless Web Audio scheduler

The class that owns an `AudioContext` and plays the teed PCM gaplessly. It accepts an injectable context factory so it's testable under happy-dom (which has no real `AudioContext`). Schedules each chunk to start exactly where the previous one ends (`nextStartTime`), ignores chunks from a stale utterance id, and flushes on `stop`. **Frontend task — commits.**

**Files:**
- Create: `zendaya-hud-react/src/audio/VoiceQueue.ts`
- Test: `zendaya-hud-react/src/__tests__/VoiceQueue.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/VoiceQueue.test.ts`:

```ts
import { describe, expect, it, vi } from "vitest";
import { VoiceQueue } from "../audio/VoiceQueue";
import { int16ToFloat32 } from "../audio/pcmPlayer";

// base64 of N little-endian int16 zero samples (silence is fine for scheduling math).
function b64Zeros(sampleCount: number): string {
  const bytes = new Uint8Array(sampleCount * 2); // all zero
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s);
}

class FakeBufferSource {
  buffer: any = null;
  onended: (() => void) | null = null;
  started: number | null = null;
  stopped = false;
  connect = vi.fn();
  start = vi.fn((t: number) => { this.started = t; });
  stop = vi.fn(() => { this.stopped = true; });
}

class FakeAudioContext {
  currentTime = 10; // non-zero so we can see scheduling offsets
  sampleRate = 48000;
  state: AudioContextState = "running";
  destination = {} as AudioNode;
  sources: FakeBufferSource[] = [];
  buffers: any[] = [];

  createBuffer(channels: number, length: number, rate: number) {
    const data = new Float32Array(length);
    const buf = {
      length,
      sampleRate: rate,
      duration: length / rate,
      getChannelData: () => data,
    };
    this.buffers.push(buf);
    return buf as unknown as AudioBuffer;
  }
  createBufferSource() {
    const s = new FakeBufferSource();
    this.sources.push(s);
    return s as unknown as AudioBufferSourceNode;
  }
  resume() { this.state = "running"; return Promise.resolve(); }
  close() { return Promise.resolve(); }
}

function makeQueue() {
  const ctx = new FakeAudioContext();
  const q = new VoiceQueue(() => ctx as unknown as AudioContext);
  return { ctx, q };
}

describe("VoiceQueue", () => {
  it("schedules a chunk to start at the context's current time", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(22050) }); // 1.0 s
    expect(ctx.sources.length).toBe(1);
    expect(ctx.sources[0].started).toBeCloseTo(10, 5);
  });

  it("plays chunks gaplessly (next starts where previous ends)", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(22050) }); // 1.0 s @22050
    q.handle({ event: "chunk", id: 1, seq: 1, b64: b64Zeros(11025) }); // 0.5 s @22050
    expect(ctx.sources.length).toBe(2);
    expect(ctx.sources[0].started).toBeCloseTo(10, 5);
    // second starts at 10 + 1.0 = 11.0 (buffer made at the 22050 rate, not ctx rate)
    expect(ctx.sources[1].started).toBeCloseTo(11, 5);
  });

  it("ignores chunks from a stale utterance id", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 2 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(100) }); // stale id
    expect(ctx.sources.length).toBe(0);
  });

  it("ignores a chunk that arrives before any begin", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(100) });
    expect(ctx.sources.length).toBe(0);
  });

  it("stop() halts and clears all active sources", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(22050) });
    const src = ctx.sources[0];
    q.handle({ event: "stop" });
    expect(src.stopped).toBe(true);
    // a subsequent chunk for the stopped utterance is ignored
    q.handle({ event: "chunk", id: 1, seq: 1, b64: b64Zeros(22050) });
    expect(ctx.sources.length).toBe(1);
  });

  it("uses the buffer's PCM data from the decoded base64", () => {
    const { ctx, q } = makeQueue();
    q.handle({ event: "begin", rate: 22050, id: 1 });
    q.handle({ event: "chunk", id: 1, seq: 0, b64: b64Zeros(4) });
    // int16ToFloat32 of zeros is zeros — buffer length should match sample count
    expect(ctx.buffers[0].length).toBe(4);
    expect(Array.from(int16ToFloat32(Int16Array.from([0, 0])))).toEqual([0, 0]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- VoiceQueue`
Expected: FAIL — cannot resolve `../audio/VoiceQueue`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/audio/VoiceQueue.ts`:

```ts
/**
 * VoiceQueue.ts — plays the backend's teed TTS PCM in the browser, gaplessly.
 *
 * Owns its own AudioContext (separate from the SFX/ambient AudioManager) so
 * voice routing stays simple and decoupled. Fed one base64 PCM window at a
 * time from useWebSocket. Chunks are scheduled back-to-back via nextStartTime
 * so there are no clicks between windows. Chunks whose id != the current
 * utterance are dropped (barge-in stragglers / late-joiner echoes).
 */
import { decodeBase64ToInt16, int16ToFloat32 } from "./pcmPlayer";

type AudioMsg =
  | { event: "begin"; rate: number; id: number }
  | { event: "chunk"; id: number; seq: number; b64: string }
  | { event: "end"; id: number }
  | { event: "stop" }
  | { event?: string; [k: string]: unknown };

export class VoiceQueue {
  private factory: () => AudioContext;
  private ctx: AudioContext | null = null;
  private currentId: number | null = null;
  private rate = 22050;
  private nextStartTime = 0;
  private active = new Set<AudioBufferSourceNode>();

  constructor(factory: () => AudioContext = () => new AudioContext()) {
    this.factory = factory;
  }

  private ensureCtx(): AudioContext {
    if (!this.ctx) this.ctx = this.factory();
    return this.ctx;
  }

  /** Resume the context on a user gesture (autoplay policy). Safe to call repeatedly. */
  unlock(): void {
    let ctx: AudioContext;
    try {
      ctx = this.ensureCtx();
    } catch {
      return; // no Web Audio available (e.g. test env without a factory)
    }
    if (ctx.state === "suspended") {
      try { ctx.resume().catch(() => {}); } catch { /* ignore */ }
    }
  }

  /** Route one wire frame. Tolerant of unknown/garbage shapes. */
  handle(msg: AudioMsg): void {
    switch (msg?.event) {
      case "begin":
        this.begin((msg as any).rate, (msg as any).id);
        break;
      case "chunk":
        this.push((msg as any).id, (msg as any).b64);
        break;
      case "end":
        this.end((msg as any).id);
        break;
      case "stop":
        this.stop();
        break;
      default:
        break;
    }
  }

  private begin(rate: number, id: number): void {
    let ctx: AudioContext;
    try {
      ctx = this.ensureCtx();
    } catch {
      return;
    }
    this.currentId = id;
    this.rate = rate > 0 ? rate : 22050;
    this.nextStartTime = ctx.currentTime;
  }

  private push(id: number, b64: string): void {
    if (this.currentId === null || id !== this.currentId) return;
    let ctx: AudioContext;
    try {
      ctx = this.ensureCtx();
    } catch {
      return;
    }
    const int16 = decodeBase64ToInt16(b64);
    if (int16.length === 0) return;
    const f32 = int16ToFloat32(int16);

    const buf = ctx.createBuffer(1, f32.length, this.rate);
    buf.getChannelData(0).set(f32);

    const src = ctx.createBufferSource();
    src.buffer = buf;
    src.connect(ctx.destination);

    const startAt = Math.max(this.nextStartTime, ctx.currentTime);
    try { src.start(startAt); } catch { /* already started / closed */ }
    this.nextStartTime = startAt + buf.duration;

    this.active.add(src);
    src.onended = () => { this.active.delete(src); };
  }

  private end(id: number): void {
    if (id !== this.currentId) return;
    // Let already-scheduled buffers finish; nothing to do here. A later
    // begin/stop resets state. (Kept as a hook for future fades.)
  }

  private stop(): void {
    this.currentId = null;
    this.active.forEach((s) => { try { s.stop(); } catch { /* ignore */ } });
    this.active.clear();
    this.nextStartTime = this.ctx ? this.ctx.currentTime : 0;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- VoiceQueue`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/audio/VoiceQueue.ts zendaya-hud-react/src/__tests__/VoiceQueue.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add gapless Web Audio VoiceQueue for teed TTS PCM"
git status
```

Confirm no protected paths were staged.

---

## Task 5: `voicePlayer.ts` module singleton

A one-line singleton so the WebSocket hook and the unlock hook share the same `VoiceQueue` instance. Defaults to the real `AudioContext`, created lazily on first use (so importing the module never touches Web Audio at module-eval time — safe under happy-dom). **Frontend task — commits.**

**Files:**
- Create: `zendaya-hud-react/src/audio/voicePlayer.ts`
- Test: `zendaya-hud-react/src/__tests__/voicePlayer.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/voicePlayer.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { voicePlayer } from "../audio/voicePlayer";

describe("voicePlayer singleton", () => {
  it("exposes handle() and unlock()", () => {
    expect(typeof voicePlayer.handle).toBe("function");
    expect(typeof voicePlayer.unlock).toBe("function");
  });

  it("handle('stop') before any audio context is a no-op (no throw)", () => {
    expect(() => voicePlayer.handle({ event: "stop" })).not.toThrow();
  });

  it("ignores an unknown event shape without throwing", () => {
    expect(() => voicePlayer.handle({ event: "bogus" } as any)).not.toThrow();
    expect(() => voicePlayer.handle({} as any)).not.toThrow();
  });

  it("unlock() is safe when no AudioContext exists in the environment", () => {
    // happy-dom has no AudioContext; ensureCtx throws and unlock swallows it.
    const saved = (globalThis as any).AudioContext;
    delete (globalThis as any).AudioContext;
    expect(() => voicePlayer.unlock()).not.toThrow();
    if (saved) (globalThis as any).AudioContext = saved;
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- voicePlayer`
Expected: FAIL — cannot resolve `../audio/voicePlayer`.

- [ ] **Step 3: Write the implementation**

Create `zendaya-hud-react/src/audio/voicePlayer.ts`:

```ts
/**
 * voicePlayer.ts — shared VoiceQueue singleton.
 *
 * useWebSocket feeds wire frames into voicePlayer.handle(); useVoicePlayback
 * calls voicePlayer.unlock() on the first user gesture. The underlying
 * AudioContext is created lazily inside VoiceQueue, so importing this module
 * is side-effect free (safe in tests / SSR).
 */
import { VoiceQueue } from "./VoiceQueue";

export const voicePlayer = new VoiceQueue();
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- voicePlayer`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add zendaya-hud-react/src/audio/voicePlayer.ts zendaya-hud-react/src/__tests__/voicePlayer.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): add shared voicePlayer VoiceQueue singleton"
git status
```

Confirm no protected paths were staged.

---

## Task 6: Route `data.audio` frames in `useWebSocket`

One branch in the existing `onmessage` handler hands every `audio` frame to the singleton, directly — NOT through Zustand — so PCM chunks never trigger a React re-render. **Frontend task — commits.**

**Files:**
- Modify: `zendaya-hud-react/src/hooks/useWebSocket.ts` (add import; add branch in `onmessage`)
- Test: `zendaya-hud-react/src/__tests__/useWebSocket.test.ts` (append a describe block)

- [ ] **Step 1: Write the failing test (append to the existing file)**

Append this describe block to `zendaya-hud-react/src/__tests__/useWebSocket.test.ts` (after the last block, before EOF). It mocks the singleton and asserts the frame is forwarded verbatim:

```ts
import { voicePlayer } from "../audio/voicePlayer";

describe("useWebSocket — audio frames route to voicePlayer", () => {
  it("forwards an audio frame to voicePlayer.handle", async () => {
    const spy = vi.spyOn(voicePlayer, "handle").mockImplementation(() => {});
    const { ws } = await freshHook();
    ws.fireMessage({ audio: { event: "begin", rate: 22050, id: 1 } });
    expect(spy).toHaveBeenCalledWith({ event: "begin", rate: 22050, id: 1 });
    spy.mockRestore();
  });

  it("ignores a non-object audio field", async () => {
    const spy = vi.spyOn(voicePlayer, "handle").mockImplementation(() => {});
    const { ws } = await freshHook();
    ws.fireMessage({ audio: "nope" });
    ws.fireMessage({ audio: [1, 2, 3] });
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- useWebSocket`
Expected: FAIL — `voicePlayer.handle` is never called because `useWebSocket` has no audio branch yet.

- [ ] **Step 3: Add the import**

In `zendaya-hud-react/src/hooks/useWebSocket.ts`, after the existing `import { normaliseVisemes } from "../store/normaliseVisemes";` line (line 3):

```ts
import { normaliseVisemes } from "../store/normaliseVisemes";
import { voicePlayer } from "../audio/voicePlayer";
```

- [ ] **Step 4: Add the routing branch**

In the `ws.onmessage` handler, after the `body_action` block (the block ending at line 125 with `z.firePulseBodyAction(...)`), add — still inside the `onmessage` handler, before its closing `};`:

```ts
        if (typeof data.body_action === "string" && (VALID_BODY as string[]).includes(data.body_action)) {
          z.firePulseBodyAction(data.body_action as BodyAction);
        }
        if (data.audio && typeof data.audio === "object" && !Array.isArray(data.audio)) {
          // Teed TTS PCM — play directly via the singleton, NOT through the
          // store (a chunk arrives every ~90 ms; routing through Zustand would
          // re-render the whole tree each time).
          voicePlayer.handle(data.audio);
        }
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- useWebSocket`
Expected: PASS (all useWebSocket tests, including the 2 new ones).

- [ ] **Step 6: Commit**

```bash
git add zendaya-hud-react/src/hooks/useWebSocket.ts zendaya-hud-react/src/__tests__/useWebSocket.test.ts
git -c commit.gpgsign=false commit -m "feat(hud): route teed TTS audio frames to voicePlayer"
git status
```

Confirm no protected paths were staged.

---

## Task 7: `useVoicePlayback` first-gesture unlock + App mount

Browsers suspend a freshly created `AudioContext` until a user gesture. This hook resumes the voice context on the first click/keydown/touch (mirroring `useAudioEngine`'s bootstrap pattern), then mounts in `App.tsx`. **Frontend task — commits.**

**Files:**
- Create: `zendaya-hud-react/src/hooks/useVoicePlayback.ts`
- Modify: `zendaya-hud-react/src/App.tsx` (import + call the hook)
- Test: `zendaya-hud-react/src/__tests__/useVoicePlayback.test.ts`

- [ ] **Step 1: Write the failing test**

Create `zendaya-hud-react/src/__tests__/useVoicePlayback.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from "vitest";
import { renderHook, cleanup } from "@testing-library/react";
import { voicePlayer } from "../audio/voicePlayer";
import { useVoicePlayback } from "../hooks/useVoicePlayback";

afterEach(() => cleanup());

describe("useVoicePlayback", () => {
  it("unlocks the voice context on the first user gesture", () => {
    const spy = vi.spyOn(voicePlayer, "unlock").mockImplementation(() => {});
    renderHook(() => useVoicePlayback());
    expect(spy).not.toHaveBeenCalled(); // nothing before a gesture
    window.dispatchEvent(new Event("click"));
    expect(spy).toHaveBeenCalledTimes(1);
    // de-dupes: a second gesture does not re-unlock
    window.dispatchEvent(new Event("keydown"));
    expect(spy).toHaveBeenCalledTimes(1);
    spy.mockRestore();
  });

  it("removes its listeners on unmount", () => {
    const spy = vi.spyOn(voicePlayer, "unlock").mockImplementation(() => {});
    const { unmount } = renderHook(() => useVoicePlayback());
    unmount();
    window.dispatchEvent(new Event("click"));
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- useVoicePlayback`
Expected: FAIL — cannot resolve `../hooks/useVoicePlayback`.

- [ ] **Step 3: Write the hook**

Create `zendaya-hud-react/src/hooks/useVoicePlayback.ts`:

```ts
/**
 * useVoicePlayback.ts — resume the voice AudioContext on first user gesture.
 *
 * Mount once at the App root. Browsers keep a freshly created AudioContext
 * suspended until the user interacts; this hook calls voicePlayer.unlock()
 * on the first click/keydown/touch, then detaches. Playback itself is driven
 * by useWebSocket → voicePlayer.handle().
 */
import { useEffect } from "react";
import { voicePlayer } from "../audio/voicePlayer";

export function useVoicePlayback(): void {
  useEffect(() => {
    let unlocked = false;
    const onGesture = () => {
      if (unlocked) return;
      unlocked = true;
      voicePlayer.unlock();
      window.removeEventListener("click", onGesture);
      window.removeEventListener("keydown", onGesture);
      window.removeEventListener("touchstart", onGesture);
    };
    window.addEventListener("click", onGesture);
    window.addEventListener("keydown", onGesture);
    window.addEventListener("touchstart", onGesture);
    return () => {
      window.removeEventListener("click", onGesture);
      window.removeEventListener("keydown", onGesture);
      window.removeEventListener("touchstart", onGesture);
    };
  }, []);
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test -- useVoicePlayback`
Expected: PASS (2 passed).

- [ ] **Step 5: Mount the hook in App.tsx**

In `zendaya-hud-react/src/App.tsx`, add the import alongside the other hook imports, then call it next to the existing hook calls at the top of `App()`. The existing calls read:

```ts
  useWebSocket();
  useAdaptiveQuality();
  useAudioEngine();
```

Add `useVoicePlayback();` immediately after `useAudioEngine();`:

```ts
  useWebSocket();
  useAdaptiveQuality();
  useAudioEngine();
  useVoicePlayback();
```

And add the import near the other hook imports (match the existing import style/path in the file, e.g. after the `useAudioEngine` import):

```ts
import { useVoicePlayback } from "./hooks/useVoicePlayback";
```

- [ ] **Step 6: Run the full frontend suite to verify nothing regressed**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test`
Expected: PASS — all prior tests plus the new pcmPlayer / VoiceQueue / voicePlayer / useWebSocket / useVoicePlayback tests.

- [ ] **Step 7: Commit**

```bash
git add zendaya-hud-react/src/hooks/useVoicePlayback.ts zendaya-hud-react/src/__tests__/useVoicePlayback.test.ts zendaya-hud-react/src/App.tsx
git -c commit.gpgsign=false commit -m "feat(hud): unlock voice playback on first gesture and mount in App"
git status
```

Confirm no protected paths were staged.

---

## Task 8: Final verification + manual smoke

Prove the whole feature builds and every test is green, then walk the manual end-to-end path. **No code changes; nothing to commit.**

- [ ] **Step 1: Full frontend suite**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run test`
Expected: PASS — entire suite (prior count + the new SP-2 tests).

- [ ] **Step 2: Frontend production build**

Run: `cd C:/Users/IKA/Zendaya && npm --prefix zendaya-hud-react run build`
Expected: exit 0, no TypeScript errors.

- [ ] **Step 3: Backend tests**

Run: `cd C:/Users/IKA/Zendaya/backend && python -m pytest tests/test_voice_from_hud.py -v`
Expected: PASS (7 passed).

- [ ] **Step 4: Confirm the staging boundary**

Run: `cd C:/Users/IKA/Zendaya && git status`
Expected:
- `backend/zendaya.py`, `backend/zendaya_state_server.py` show `M` (modified, **unstaged**).
- `backend/tests/test_voice_from_hud.py` is untracked.
- All frontend SP-2 files are committed (clean working tree under `zendaya-hud-react/src/audio/` and the new hook).
- No protected paths staged anywhere.

- [ ] **Step 5: Manual smoke (document for the user — requires the running app)**

These steps need the live backend + a HUD browser tab, so they're a checklist for the user, not an automated test:
1. Start the backend and open the HUD in a browser; click once anywhere (satisfies the autoplay-unlock gesture).
2. Ask Zendaya something that produces a spoken reply. Expected: the voice plays **from the browser tab**, the orb lip-syncs, and the backend speaker stays silent.
3. Close the HUD tab and ask again. Expected: the voice falls back to the **backend speaker** (the `hud_client_count() == 0` path).
4. While Zendaya is mid-sentence in the HUD, interrupt (barge-in via the voice listener). Expected: HUD audio cuts off promptly (the `stop` frame flushed the queue).

- [ ] **Step 6: Report completion**

Summarize for the user: frontend test count, build status, backend test count, the exact backend files left unstaged for their review, and the manual smoke checklist above. Then invoke `superpowers:finishing-a-development-branch`.

---

## Self-review notes (author check — not an execution step)

- **Spec coverage:** §backend-routing → Tasks 1–2; §wire-protocol → Task 1 frames + Task 4 handler; §frontend-playback → Tasks 3–5; §lip-sync/barge-in/edge-cases → Task 2 (`audio_stop` on barge-in; amplitude/visemes on both paths) + Task 4 (stale-id drop, stop-flush); §testing → every task's tests + Task 8. ✓
- **Type consistency:** `handle/unlock/begin/push/end/stop` names match across `VoiceQueue.ts`, `voicePlayer.ts`, the hook, and useWebSocket. Wire field names (`event/rate/id/seq/b64`) identical between backend frames (Task 1) and frontend reads (Task 4). ✓
- **No placeholders:** every code step shows complete, copy-pasteable content. ✓
- **Staging discipline:** backend (Tasks 1–2) never committed; frontend commits name exact files only. ✓
