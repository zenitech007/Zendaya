# Pack A — Conversation Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Zendaya's voice loop feel conversational: acoustic barge-in (talk over her), a configurable follow-up window with a "still-listening" cue, and backchannels during long tasks.

**Architecture:** All changes live in `backend/voice/` (the listener) — no brain-path changes. A new `voice/cue.py` plays short cached/generated PCM clips through sounddevice (gated so it never fights real TTS). A new `_BargeDetector` in `listener_v2.py` decides "is the user talking over her?" from Silero VAD + a self-calibrating during-TTS energy baseline. Everything is env-toggleable.

**Tech Stack:** Python 3.14, numpy, sounddevice, Silero VAD (existing), `voice.offline_tts` (existing), pytest.

**Scope note:** Streaming sentence-by-sentence TTS (Pack A item 4) is **deferred to its own plan** — `gemini_reply` in `zendaya.py` is non-streaming (`generate_content` + `.text` at lines ~843/876), so it needs a separate Gemini-streaming refactor of the reply path.

**Repo conventions (read first):**
- Repo root `C:\Users\IKA\Zendaya`. Shell: **PowerShell 5.1** — `;` not `&&`. Venv python: `C:\Users\IKA\Zendaya\venv\Scripts\python.exe`. Tests: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/<file> -v`.
- Backend uses absolute package imports with `backend/` on `sys.path` (`backend/tests/conftest.py`). `slow` marker registered in `pytest.ini`.
- Git: NEVER `git add -A`/`git add .`. Stage only named files. Commit `git -c commit.gpgsign=false commit`, end messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Leave `zendaya_logs/` runtime files alone.
- Active listener = `backend/voice/listener_v2.py`. Key existing pieces: frame loop `_run_listener_session()` (the `tts_on` branch ~lines 637-658), `_TTS_SPEAKING` event, `_stop_tts()`, `_drain_queue()`, `_AmbientGate`, Silero VAD `_VAD.is_speech(frame)`, `_start_dispatch_worker` (~221-257), constants `SAMPLE_RATE=16000`, `FRAME_SAMPLES`, `VAD_TRIGGER_FRAMES=4`, `FOLLOW_UP_S=20.0`.

**Env knobs added:** `ZENDAYA_BARGE_MODE` (acoustic|wake|off, default acoustic), `ZENDAYA_BARGE_MARGIN` (float, default 1.6), `ZENDAYA_FOLLOWUP_S` (float, default 10), `ZENDAYA_FOLLOWUP_CUE` (on|off, default on), `ZENDAYA_BACKCHANNEL` (on|off, default on).

---

## File Structure
- **Create:** `backend/voice/cue.py` — generate/cache short PCM clips; gated playback through sounddevice. One responsibility: "make a short sound without fighting real TTS."
- **Create:** `backend/tests/test_conversation_flow.py` — unit tests for cue gating, `_BargeDetector`, backchannel timer, follow-up config.
- **Modify:** `backend/voice/listener_v2.py` — `_BargeDetector`, barge wiring in the `tts_on` branch, follow-up config + cue, backchannel timer in `_start_dispatch_worker`.
- **Modify:** `README.md`, `CLAUDE.md` — note the new env knobs.

---

## Task 1: `voice/cue.py` — gated short-clip playback

**Files:** Create `backend/voice/cue.py`; Test `backend/tests/test_conversation_flow.py`

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_conversation_flow.py`:
```python
"""Pack A conversation-flow tests: cue gating, barge detector, backchannel, follow-up."""
from __future__ import annotations

import numpy as np
import pytest

from voice import cue


def test_tone_pcm_is_int16_and_right_length():
    pcm = cue.tone_pcm(freq=660, ms=120, samplerate=16000)
    arr = np.frombuffer(pcm, dtype="<i2")
    assert arr.dtype == np.int16
    assert abs(len(arr) - int(16000 * 0.120)) <= 2


def test_play_skips_when_tts_active(monkeypatch):
    played = []
    monkeypatch.setattr(cue, "_raw_play", lambda pcm, sr: played.append(len(pcm)))
    monkeypatch.setattr(cue, "_tts_is_active", lambda: True)
    cue.play_pcm(b"\x00\x00" * 100, samplerate=16000)
    assert played == []  # gated out while real TTS speaks


def test_play_runs_when_idle(monkeypatch):
    played = []
    monkeypatch.setattr(cue, "_raw_play", lambda pcm, sr: played.append(len(pcm)))
    monkeypatch.setattr(cue, "_tts_is_active", lambda: False)
    cue.play_pcm(b"\x00\x00" * 100, samplerate=16000)
    assert played == [200]
```

- [ ] **Step 2: Run to verify fail** — `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_conversation_flow.py -v` → FAIL (`No module named 'voice.cue'`).

- [ ] **Step 3: Implement** — create `backend/voice/cue.py`:
```python
"""Short attention/backchannel clips played through sounddevice, gated so they
never overlap real TTS. Used by the follow-up 'still-listening' cue and by
backchannels during long tasks."""
from __future__ import annotations

import os
import threading

import numpy as np

SAMPLE_RATE = 16000
_LOCK = threading.Lock()


def tone_pcm(freq: float = 660.0, ms: int = 120, samplerate: int = SAMPLE_RATE,
             volume: float = 0.25) -> bytes:
    """A short sine 'blip' with a quick fade in/out, as int16 PCM bytes."""
    n = int(samplerate * ms / 1000)
    t = np.arange(n, dtype=np.float32) / samplerate
    wave = np.sin(2 * np.pi * freq * t).astype(np.float32) * volume
    fade = max(1, n // 8)
    env = np.ones(n, dtype=np.float32)
    env[:fade] = np.linspace(0.0, 1.0, fade)
    env[-fade:] = np.linspace(1.0, 0.0, fade)
    wave *= env
    return (np.clip(wave, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()


def _tts_is_active() -> bool:
    """True while real TTS is speaking (so cues don't talk over her)."""
    try:
        from voice import listener_v2
        return listener_v2._TTS_SPEAKING.is_set()
    except Exception:
        return False


def _raw_play(pcm: bytes, samplerate: int) -> None:
    try:
        import sounddevice as sd
        arr = np.frombuffer(pcm, dtype="<i2")
        sd.play(arr, samplerate=samplerate, blocking=True)
    except Exception as e:
        print(f"(cue play failed: {e})")


def play_pcm(pcm: bytes, samplerate: int = SAMPLE_RATE) -> None:
    """Play a PCM clip unless real TTS is currently active. Serialized so two
    clips never overlap."""
    if not pcm or _tts_is_active():
        return
    with _LOCK:
        if _tts_is_active():
            return
        _raw_play(pcm, samplerate)
```

- [ ] **Step 4: Run to verify pass** — same pytest command → 3 passed.

- [ ] **Step 5: Commit**
```powershell
git add backend/voice/cue.py backend/tests/test_conversation_flow.py
git -c commit.gpgsign=false commit -m "feat(voice): cue module for gated short-clip playback" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Follow-up window — configurable duration + "still-listening" cue

**Files:** Modify `backend/voice/listener_v2.py`; Test `backend/tests/test_conversation_flow.py`

- [ ] **Step 1: Add the failing test** — append:
```python
def test_followup_seconds_env(monkeypatch):
    monkeypatch.setenv("ZENDAYA_FOLLOWUP_S", "7.5")
    import importlib
    from voice import listener_v2
    importlib.reload(listener_v2)
    assert listener_v2._followup_seconds() == 7.5
    monkeypatch.delenv("ZENDAYA_FOLLOWUP_S", raising=False)
    importlib.reload(listener_v2)
    assert listener_v2._followup_seconds() == 10.0
```

- [ ] **Step 2: Run to verify fail** — `... -m pytest backend/tests/test_conversation_flow.py -k followup -v` → FAIL (`_followup_seconds` missing).

- [ ] **Step 3: Implement** — in `backend/voice/listener_v2.py`:

(a) Change the constant `FOLLOW_UP_S = 20.0` to a default + helper:
```python
FOLLOW_UP_S = 10.0                  # default; overridable via ZENDAYA_FOLLOWUP_S


def _followup_seconds() -> float:
    try:
        return float(os.environ.get("ZENDAYA_FOLLOWUP_S", FOLLOW_UP_S))
    except (TypeError, ValueError):
        return FOLLOW_UP_S
```

(b) Where the loop computes the window, use the helper + emit a one-shot cue. Change:
```python
            in_followup = (time.time() - _last_dispatch_ts) < FOLLOW_UP_S
```
to:
```python
            in_followup = (time.time() - _last_dispatch_ts) < _followup_seconds()
            if in_followup and not _followup_cued:
                _followup_cued = True
                if os.environ.get("ZENDAYA_FOLLOWUP_CUE", "on").lower() != "off":
                    from voice import cue as _cue
                    _cue.play_pcm(_cue.tone_pcm(freq=720, ms=90))
            if not in_followup:
                _followup_cued = False
```

(c) Initialize `_followup_cued = False` as a local near the top of `_run_listener_session()` (next to `wake_fired = False`). The `if not in_followup: _followup_cued = False` line in (b) re-arms the cue each time the window closes, so the cue fires once per open-mic period.

- [ ] **Step 4: Run to verify pass** — `... -k followup -v` → pass. Then `& "...python.exe" -c "import ast; ast.parse(open(r'backend/voice/listener_v2.py',encoding='utf-8').read()); print('OK')"`.

- [ ] **Step 5: Commit**
```powershell
git add backend/voice/listener_v2.py backend/tests/test_conversation_flow.py
git -c commit.gpgsign=false commit -m "feat(voice): configurable follow-up window + still-listening cue" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Backchannels — dispatch-worker watchdog timer

**Files:** Modify `backend/voice/listener_v2.py`; Test `backend/tests/test_conversation_flow.py`

- [ ] **Step 1: Add the failing tests** — append:
```python
def test_backchannel_plays_a_clip(monkeypatch):
    from voice import listener_v2
    calls = []
    monkeypatch.setattr(listener_v2, "_play_backchannel_clip", lambda: calls.append(1))
    monkeypatch.setenv("ZENDAYA_BACKCHANNEL", "on")
    listener_v2._maybe_backchannel()
    assert calls == [1]


def test_backchannel_off_is_noop(monkeypatch):
    from voice import listener_v2
    calls = []
    monkeypatch.setattr(listener_v2, "_play_backchannel_clip", lambda: calls.append(1))
    monkeypatch.setenv("ZENDAYA_BACKCHANNEL", "off")
    listener_v2._maybe_backchannel()
    assert calls == []
```

- [ ] **Step 2: Run to verify fail** — `... -k backchannel -v` → FAIL.

- [ ] **Step 3: Implement** — in `backend/voice/listener_v2.py`:

(a) Add near the top (after imports/constants):
```python
BACKCHANNEL_AFTER_S = 3.0
_BACKCHANNEL_TEXTS = ("one sec", "still on it", "mm-hm")
_backchannel_idx = 0


def _play_backchannel_clip() -> None:
    """Synthesize (cached) and play one short backchannel via the cue path."""
    global _backchannel_idx
    try:
        from voice import cue, offline_tts
        text = _BACKCHANNEL_TEXTS[_backchannel_idx % len(_BACKCHANNEL_TEXTS)]
        _backchannel_idx += 1
        pcm = offline_tts.synth_to_pcm(text, target_sr=cue.SAMPLE_RATE)
        cue.play_pcm(pcm, samplerate=cue.SAMPLE_RATE)
    except Exception as e:
        print(f"(backchannel failed: {e})")


def _maybe_backchannel() -> None:
    if os.environ.get("ZENDAYA_BACKCHANNEL", "on").lower() == "off":
        return
    _play_backchannel_clip()
```

(b) In `_start_dispatch_worker`'s `_run()`, arm a one-shot timer around the handler call. Change:
```python
            try:
                handler(text)
            except Exception as e:
```
to:
```python
            timer = threading.Timer(BACKCHANNEL_AFTER_S, _maybe_backchannel)
            timer.daemon = True
            timer.start()
            try:
                handler(text)
            except Exception as e:
```
and in the matching `finally`/after the try, cancel it. If there is no `finally`, add one:
```python
            try:
                handler(text)
            except Exception as e:
                import traceback
                print(f"[voice v2] dispatch handler crashed: {e}")
                traceback.print_exc()
            finally:
                timer.cancel()
```

- [ ] **Step 4: Run to verify pass** — `... -k backchannel -v` → pass; then `ast.parse` OK.

- [ ] **Step 5: Commit**
```powershell
git add backend/voice/listener_v2.py backend/tests/test_conversation_flow.py
git -c commit.gpgsign=false commit -m "feat(voice): backchannels during long handlers via dispatch-worker timer" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `_BargeDetector` — self-calibrating over-talk detector

**Files:** Modify `backend/voice/listener_v2.py`; Test `backend/tests/test_conversation_flow.py`

- [ ] **Step 1: Add the failing tests** — append:
```python
class _StubVAD:
    def __init__(self, speech=True):
        self._speech = speech
    def is_speech(self, frame):
        return self._speech


def _frame(rms, n=512):
    # build an int16 frame with the target normalized RMS
    val = int(rms * 32768)
    return np.full(n, val, dtype=np.int16)


def test_barge_fires_on_sustained_overtalk(monkeypatch):
    from voice import listener_v2
    monkeypatch.delenv("ZENDAYA_BARGE_MARGIN", raising=False)
    det = listener_v2._BargeDetector(_StubVAD(speech=True), trigger_frames=3)
    # establish a low echo/ambient baseline with non-speech-energy frames
    det._baseline = 0.02
    fired = [det.observe(_frame(0.20)) for _ in range(3)]   # loud over-talk
    assert fired[-1] is True


def test_barge_ignores_echo_level_energy(monkeypatch):
    from voice import listener_v2
    det = listener_v2._BargeDetector(_StubVAD(speech=True), trigger_frames=3)
    det._baseline = 0.20            # speakers: baseline already at her echo level
    fired = [det.observe(_frame(0.20)) for _ in range(6)]   # only echo-level energy
    assert not any(fired)


def test_barge_needs_sustained_frames():
    from voice import listener_v2
    det = listener_v2._BargeDetector(_StubVAD(speech=True), trigger_frames=4)
    det._baseline = 0.02
    assert det.observe(_frame(0.30)) is False  # 1 frame
    assert det.observe(_frame(0.30)) is False  # 2
    assert det.observe(_frame(0.02)) is False  # dip resets counter
    assert det.observe(_frame(0.30)) is False  # 1 again
```

- [ ] **Step 2: Run to verify fail** — `... -k barge -v` → FAIL (`_BargeDetector` missing).

- [ ] **Step 3: Implement** — in `backend/voice/listener_v2.py` add:
```python
BARGE_TRIGGER_FRAMES = 5            # ~150 ms of over-talk to confirm


class _BargeDetector:
    """During TTS, decides 'is the user talking over her?' Self-calibrates an
    echo/ambient baseline (so speakers don't self-trigger) and requires sustained
    VAD speech whose energy exceeds that baseline by a margin."""

    def __init__(self, vad, margin: float | None = None, trigger_frames: int | None = None):
        try:
            self.margin = float(os.environ.get("ZENDAYA_BARGE_MARGIN",
                                                margin if margin is not None else 1.6))
        except (TypeError, ValueError):
            self.margin = 1.6
        self.trigger_frames = int(trigger_frames if trigger_frames is not None
                                  else BARGE_TRIGGER_FRAMES)
        self._vad = vad
        self._baseline = None
        self._consec = 0
        self._alpha = 0.1            # baseline EMA rate (slow)

    def reset(self) -> None:
        self._baseline = None
        self._consec = 0

    @staticmethod
    def _rms(frame_int16: np.ndarray) -> float:
        f = frame_int16.astype(np.float32) / 32768.0
        return float(np.sqrt(np.mean(f * f))) if f.size else 0.0

    def observe(self, frame_int16: np.ndarray) -> bool:
        rms = self._rms(frame_int16)
        if self._baseline is None:
            self._baseline = rms
        try:
            is_speech = bool(self._vad and self._vad.is_speech(frame_int16))
        except Exception:
            is_speech = False
        candidate = is_speech and rms > self._baseline * self.margin
        if candidate:
            self._consec += 1
            if self._consec >= self.trigger_frames:
                self._consec = 0
                return True
        else:
            self._consec = 0
            self._baseline = (1 - self._alpha) * self._baseline + self._alpha * rms
        return False
```

- [ ] **Step 4: Run to verify pass** — `... -k barge -v` → pass.

- [ ] **Step 5: Commit**
```powershell
git add backend/voice/listener_v2.py backend/tests/test_conversation_flow.py
git -c commit.gpgsign=false commit -m "feat(voice): self-calibrating _BargeDetector for acoustic over-talk" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Wire acoustic barge-in into the TTS branch

**Files:** Modify `backend/voice/listener_v2.py`. (No new unit test — hot-loop edit; verified by syntax + full suite + live mic.)

- [ ] **Step 1: Add the mode helper + detector init.** Near the constants add:
```python
def _barge_mode() -> str:
    m = os.environ.get("ZENDAYA_BARGE_MODE", "acoustic").strip().lower()
    return m if m in ("acoustic", "wake", "off") else "acoustic"
```
In `_run_listener_session()`, right after `_WAKE = WakeEngine(barge_threshold=0.72)`, add:
```python
    _BARGE = _BargeDetector(_VAD)
    _barge_prev_tts = False
```

- [ ] **Step 2: Replace the `tts_on` branch.** Change the existing block:
```python
            tts_on = _TTS_SPEAKING.is_set()

            # While TTS plays: only the wake engine listens, with stricter thresh.
            if tts_on:
                if _WAKE and _WAKE.ready:
                    if _WAKE.push(frame, barge_in=True):
                        barge_fired = True
                        print(f"[voice v2] BARGE-IN — score={_WAKE.last_score:.2f}")
                        _stop_tts()
                        # Wait briefly for TTS gate to clear, then proceed
                        deadline = time.time() + 1.5
                        while _TTS_SPEAKING.is_set() and time.time() < deadline:
                            time.sleep(0.03)
                        _drain_queue(keep_last_n=0)
                        rolling.clear()
                        consecutive_speech = 0
                        _set_state("listening")
                        # Drop into record path below
                        wake_fired = True
                        break
                # ignore everything else while TTS speaks
                continue
```
to:
```python
            tts_on = _TTS_SPEAKING.is_set()
            if tts_on and not _barge_prev_tts:
                _BARGE.reset()
            _barge_prev_tts = tts_on

            # While TTS plays: wake/stop-word barge always works; acoustic mode
            # also lets sustained over-talk interrupt (echo-guarded).
            if tts_on:
                mode = _barge_mode()
                did_barge = False
                reason = ""
                if mode != "off" and _WAKE and _WAKE.ready and _WAKE.push(frame, barge_in=True):
                    did_barge, reason = True, f"wake score={_WAKE.last_score:.2f}"
                elif mode == "acoustic" and _BARGE.observe(frame):
                    did_barge, reason = True, "acoustic over-talk"
                if did_barge:
                    barge_fired = True
                    print(f"[voice v2] BARGE-IN — {reason}")
                    _stop_tts()
                    deadline = time.time() + 1.5
                    while _TTS_SPEAKING.is_set() and time.time() < deadline:
                        time.sleep(0.03)
                    _drain_queue(keep_last_n=0)
                    rolling.clear()
                    consecutive_speech = 0
                    _set_state("listening")
                    wake_fired = True
                    break
                continue
```

- [ ] **Step 3: Verify** — syntax + full suite:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import ast; ast.parse(open(r'backend/voice/listener_v2.py',encoding='utf-8').read()); print('OK')"
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests -q -m "not slow"
```
Expected: `OK`, full suite green (incl. `test_conversation_flow.py` and the existing `test_voice_listener_v2.py`).

- [ ] **Step 4: Commit**
```powershell
git add backend/voice/listener_v2.py
git -c commit.gpgsign=false commit -m "feat(voice): acoustic barge-in (ZENDAYA_BARGE_MODE) with wake/stop-word backstop" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Docs + final verification

**Files:** Modify `README.md`, `CLAUDE.md`

- [ ] **Step 1: README** — under the **Voice in** bullet (or Running section) add the new runtime knobs:
```markdown
- **Conversation flow** — talk over her to interrupt (`ZENDAYA_BARGE_MODE=acoustic|wake|off`,
  `ZENDAYA_BARGE_MARGIN`), a follow-up window so you can chain turns without re-waking
  (`ZENDAYA_FOLLOWUP_S`, default 10s; cue via `ZENDAYA_FOLLOWUP_CUE`), and backchannels on
  long tasks (`ZENDAYA_BACKCHANNEL`).
```

- [ ] **Step 2: CLAUDE.md** — add one line near the voice notes:
```markdown
Conversation-flow knobs (voice/listener_v2 + voice/cue): ZENDAYA_BARGE_MODE (acoustic|wake|off),
ZENDAYA_BARGE_MARGIN, ZENDAYA_FOLLOWUP_S, ZENDAYA_FOLLOWUP_CUE, ZENDAYA_BACKCHANNEL.
```

- [ ] **Step 3: Final suite + commit**
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests -q -m "not slow"
git add README.md CLAUDE.md
git -c commit.gpgsign=false commit -m "docs(voice): document Pack A conversation-flow env knobs" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done when
- `test_conversation_flow.py` passes; full `backend/tests` stays green; `listener_v2.py` parses.
- Defaults: `ZENDAYA_BARGE_MODE=acoustic`, `ZENDAYA_FOLLOWUP_S=10`, backchannels + cue on.
- **User live mic test:** talk over her on speakers (shouldn't self-trigger on her own voice) and on headphones (interrupts cleanly); confirm the follow-up cue + a backchannel on a long task; tune `ZENDAYA_BARGE_MARGIN` if needed.

## Follow-up (separate plan)
- **Streaming sentence-by-sentence TTS** — needs a `gemini_reply` streaming refactor (`generate_content_stream`) + a flushable `SentencePlayer`. Its own spec/plan next.
