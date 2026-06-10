# Offline-First Coqui TTS Voice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Zendaya a free, offline Coqui TTS voice as her default, with ElevenLabs kept on-demand and `pyttsx3` as last resort.

**Architecture:** A new, isolated `backend/zendaya_offline_tts.py` lazy-loads a Coqui VITS model and returns 22050 Hz int16 PCM. A `PcmBytesResponse` adapter exposes that PCM through the same `.iter_content()` interface that `zendaya.py`'s existing `_stream_pcm_playback()` already consumes, so the HUD orb, visemes, and barge-in work unchanged. A tiny engine-selector hook in `speak_async()` routes offline-vs-cloud; a `/voice` command (plus natural phrases) flips a persisted preference.

**Tech Stack:** Python 3.14, `coqui-tts` 0.27.5, `torch` 2.11 (CPU), `torchcodec` + FFmpeg, `numpy`, `pytest`.

**Repo conventions (read before starting):**
- Backend modules import each other top-level (e.g. `import zendaya_visemes as _viz`). The new module lives in `backend/`.
- Tests live in `backend/tests/`; `backend/tests/conftest.py` puts `backend/` on `sys.path` and provides a `tmp_data_dir` fixture that monkeypatches `zendaya_data_store.DATA_DIR`. The `slow` marker is registered in root `pytest.ini`.
- **Venv python:** `C:\Users\IKA\Zendaya\venv\Scripts\python.exe`. Shell is PowerShell 5.1 — use `;` not `&&`, and `Push-Location`/`Pop-Location` (never `cd &&`).
- **Git is constrained in this repo:** NEVER `git add -A` or `git add .`. Stage only the exact files named in each commit step. Commit with `git -c commit.gpgsign=false commit`. `backend/zendaya.py` is part of an uncommitted protected WIP diff — when you commit Task 6, stage ONLY `backend/zendaya.py` (plus the new module/tests), and run `git show --stat HEAD` to confirm nothing else slipped in. Do not touch `backend/zendaya_system_access.py`, `pyproject.toml`, root `.gitignore`, or `zendaya_logs/`.

**Module API created across the plan (for reference):**
```text
# backend/zendaya_offline_tts.py
MODEL_NAME = "tts_models/en/vctk/vits"
DEFAULT_SPEAKER = "p225"
TARGET_SR = 22050
VALID_ENGINES = ("offline", "elevenlabs")
class OfflineTTSError(RuntimeError): ...
class PcmBytesResponse:               # .iter_content(chunk_size) -> generator[bytes]
def get_voice_engine() -> str
def set_voice_engine(engine: str) -> str
def parse_voice_command(user_text: str) -> str | None   # "offline" | "elevenlabs" | "status" | None
def handle_voice_command(action: str) -> str
def synth_to_pcm(text: str, target_sr: int = TARGET_SR, speaker: str | None = None) -> bytes
def warmup() -> bool
def is_ready() -> bool
```

---

## File Structure

- **Create:** `backend/zendaya_offline_tts.py` — offline TTS engine, engine-preference persistence, `/voice` command parsing, PCM adapter. One responsibility: "produce Zendaya's offline voice + manage which engine is active."
- **Create:** `backend/tests/test_zendaya_offline_tts.py` — unit tests (Coqui mocked) + one skipped real-synth test.
- **Create:** `backend/requirements-offline-voice.txt` — records the new deps (`torchcodec`; FFmpeg is a system dep).
- **Modify:** `backend/zendaya.py` — add `_speak_offline_async()`, an engine hook at the top of `speak_async()`, an offline fallback in the ElevenLabs-unavailable branch, and a `/voice` dispatch in `handle_user_command()`.

---

## Task 1: Dependency remediation (one-time environment setup)

**Files:**
- Create: `backend/requirements-offline-voice.txt`

This task makes `import TTS` actually work in the venv. The module unit tests (Tasks 2–5) mock Coqui and do **not** need these installs, but the real voice (Task 6) does. Do this first to de-risk.

- [ ] **Step 1: Record the dependencies**

Create `backend/requirements-offline-voice.txt`:
```text
# Offline voice (Coqui TTS) extra dependencies.
# coqui-tts and torch are already installed in the venv.
# torchcodec is required because torch>=2.9 moved audio IO to it.
torchcodec>=0.14
# System dependency (NOT pip): FFmpeg shared libraries must be installed and on PATH
# so torchcodec can load codecs. On Windows:  winget install Gyan.FFmpeg
```

- [ ] **Step 2: Install torchcodec into the venv**

Run (PowerShell):
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pip install torchcodec
```
Expected: `Successfully installed torchcodec-0.14.0` (cp314 wheel).

- [ ] **Step 3: Install FFmpeg (system) and verify it is on PATH**

Run:
```powershell
winget install --id Gyan.FFmpeg -e --source winget
```
Then open a NEW PowerShell (so PATH refreshes) and verify:
```powershell
ffmpeg -version
```
Expected: a version banner (e.g. `ffmpeg version 7.x`). If `ffmpeg` is not found, add its `bin\` folder to PATH and re-open the shell.

- [ ] **Step 4: Verify `import TTS` succeeds with the compat shim**

Run:
```powershell
$env:PYTHONIOENCODING = "utf-8"
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import torch, transformers.pytorch_utils as p; p.isin_mps_friendly = getattr(p,'isin_mps_friendly', lambda e,t: torch.isin(e,t)); import TTS; print('IMPORT TTS OK', TTS.__version__)"
```
Expected: `IMPORT TTS OK 0.27.5` (no `isin_mps_friendly` and no `torchcodec` ImportError).

- [ ] **Step 5: Commit the requirements record**

```powershell
git add backend/requirements-offline-voice.txt
git -c commit.gpgsign=false commit -m "build(voice): record offline TTS deps (torchcodec + FFmpeg)"
```

---

## Task 2: Module scaffold + engine-preference persistence

**Files:**
- Create: `backend/zendaya_offline_tts.py`
- Test: `backend/tests/test_zendaya_offline_tts.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_zendaya_offline_tts.py`:
```python
"""Unit tests for Zendaya's offline Coqui TTS engine (Coqui mocked for speed)."""
from __future__ import annotations

import numpy as np
import pytest


def test_default_voice_engine_is_offline(tmp_data_dir):
    import zendaya_offline_tts as ot
    assert ot.get_voice_engine() == "offline"


def test_set_and_get_voice_engine_roundtrip(tmp_data_dir):
    import zendaya_offline_tts as ot
    assert ot.set_voice_engine("elevenlabs") == "elevenlabs"
    assert ot.get_voice_engine() == "elevenlabs"
    assert ot.set_voice_engine("offline") == "offline"
    assert ot.get_voice_engine() == "offline"


def test_set_voice_engine_rejects_unknown(tmp_data_dir):
    import zendaya_offline_tts as ot
    with pytest.raises(ValueError):
        ot.set_voice_engine("bogus")


def test_get_voice_engine_falls_back_on_corrupt_file(tmp_data_dir):
    import zendaya_offline_tts as ot
    (tmp_data_dir / "voice_engine.json").write_text("not json", encoding="utf-8")
    assert ot.get_voice_engine() == "offline"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'zendaya_offline_tts'`.

- [ ] **Step 3: Write the minimal module**

Create `backend/zendaya_offline_tts.py`:
```python
"""Offline TTS engine for Zendaya using Coqui TTS (VITS).

Default voice: tts_models/en/vctk/vits (22050 Hz). Produces int16 PCM bytes that
feed zendaya.py's existing PCM/viseme pipeline via PcmBytesResponse. Keeps the
shared transformers 5.x intact with an isin_mps_friendly compat shim applied
lazily, right before `import TTS`.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional

import numpy as np

import zendaya_data_store  # provides DATA_DIR (monkeypatched by the tmp_data_dir fixture)

MODEL_NAME = "tts_models/en/vctk/vits"
DEFAULT_SPEAKER = "p225"
TARGET_SR = 22050
VALID_ENGINES = ("offline", "elevenlabs")
_DEFAULT_ENGINE = "offline"


class OfflineTTSError(RuntimeError):
    """Raised when offline synthesis is unavailable or fails."""


# ── engine-preference persistence ──────────────────────────────────────────
def _engine_path() -> Path:
    # Resolved at call time so tests' tmp_data_dir monkeypatch takes effect.
    return Path(zendaya_data_store.DATA_DIR) / "voice_engine.json"


def get_voice_engine() -> str:
    try:
        data = json.loads(_engine_path().read_text(encoding="utf-8"))
        engine = data.get("engine")
        if engine in VALID_ENGINES:
            return engine
    except Exception:
        pass
    return _DEFAULT_ENGINE


def set_voice_engine(engine: str) -> str:
    engine = (engine or "").strip().lower()
    if engine not in VALID_ENGINES:
        raise ValueError(f"unknown voice engine: {engine!r}")
    path = _engine_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"engine": engine}), encoding="utf-8")
    except Exception:
        pass
    return engine
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -v
```
Expected: 4 passed.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_offline_tts.py backend/tests/test_zendaya_offline_tts.py
git -c commit.gpgsign=false commit -m "feat(voice): offline TTS module scaffold + engine persistence"
```

---

## Task 3: Text splitting, PCM conversion, and the PcmBytesResponse adapter

**Files:**
- Modify: `backend/zendaya_offline_tts.py`
- Test: `backend/tests/test_zendaya_offline_tts.py`

- [ ] **Step 1: Add the failing tests**

Append to `backend/tests/test_zendaya_offline_tts.py`:
```python
def test_split_sentences_basic():
    import zendaya_offline_tts as ot
    assert ot._split_sentences("Hello there. How are you?") == ["Hello there.", "How are you?"]


def test_split_sentences_empty():
    import zendaya_offline_tts as ot
    assert ot._split_sentences("   ") == []


def test_split_sentences_no_terminator_returns_whole():
    import zendaya_offline_tts as ot
    assert ot._split_sentences("just a clause") == ["just a clause"]


def test_wave_to_pcm16_dtype_and_range():
    import zendaya_offline_tts as ot
    wav = np.array([0.0, 1.0, -1.0, 0.5], dtype=np.float32)
    pcm = ot._wave_to_pcm16(wav, 22050, 22050)
    arr = np.frombuffer(pcm, dtype="<i2")
    assert arr.dtype == np.int16
    assert arr[0] == 0
    assert arr[1] == 32767
    assert arr[2] == -32767


def test_wave_to_pcm16_resamples_length():
    import zendaya_offline_tts as ot
    wav = np.zeros(48000, dtype=np.float32)
    pcm = ot._wave_to_pcm16(wav, 48000, 22050)
    arr = np.frombuffer(pcm, dtype="<i2")
    assert abs(len(arr) - 22050) <= 2


def test_pcm_bytes_response_chunks_exactly():
    import zendaya_offline_tts as ot
    data = bytes(range(10))
    r = ot.PcmBytesResponse(data)
    chunks = list(r.iter_content(chunk_size=4))
    assert chunks == [bytes(range(0, 4)), bytes(range(4, 8)), bytes(range(8, 10))]
    assert b"".join(chunks) == data
```

- [ ] **Step 2: Run to verify failure**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -k "split or pcm16 or pcm_bytes" -v
```
Expected: FAIL — `AttributeError: module 'zendaya_offline_tts' has no attribute '_split_sentences'`.

- [ ] **Step 3: Implement**

Add to `backend/zendaya_offline_tts.py` (after the persistence section):
```python
# ── text + audio helpers ────────────────────────────────────────────────────
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> list:
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in _SENT_SPLIT.split(text) if p.strip()]
    return parts or [text]


def _wave_to_pcm16(wav: np.ndarray, sr: int, target_sr: int) -> bytes:
    wav = np.asarray(wav, dtype=np.float32).flatten()
    if wav.size and sr != target_sr:
        n_out = int(round(wav.size * target_sr / sr))
        if n_out > 0:
            x_old = np.linspace(0.0, 1.0, num=wav.size, endpoint=False)
            x_new = np.linspace(0.0, 1.0, num=n_out, endpoint=False)
            wav = np.interp(x_new, x_old, wav).astype(np.float32)
    wav = np.clip(wav, -1.0, 1.0)
    return (wav * 32767.0).astype("<i2").tobytes()


class PcmBytesResponse:
    """Adapts a PCM byte buffer to the .iter_content() interface that
    zendaya._stream_pcm_playback() consumes (same shape as a streaming
    requests.Response), so the offline path reuses the HUD/viseme pipeline."""

    def __init__(self, data: bytes, chunk: int = 4096):
        self._data = data
        self._chunk = chunk

    def iter_content(self, chunk_size: int = 4096):
        size = chunk_size or self._chunk
        for i in range(0, len(self._data), size):
            yield self._data[i:i + size]
```

- [ ] **Step 4: Run to verify pass**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -v
```
Expected: all passed (10 total).

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_offline_tts.py backend/tests/test_zendaya_offline_tts.py
git -c commit.gpgsign=false commit -m "feat(voice): sentence split, PCM16 conversion, PcmBytesResponse adapter"
```

---

## Task 4: Lazy model load + `synth_to_pcm` (Coqui mocked in tests)

**Files:**
- Modify: `backend/zendaya_offline_tts.py`
- Test: `backend/tests/test_zendaya_offline_tts.py`

- [ ] **Step 1: Add the failing tests**

Append to `backend/tests/test_zendaya_offline_tts.py`:
```python
class _FakeSynth:
    output_sample_rate = 22050


class _FakeModel:
    def __init__(self, wav):
        self.synthesizer = _FakeSynth()
        self._wav = wav

    def tts(self, text, speaker=None):
        return self._wav


def test_synth_to_pcm_returns_int16_pcm(monkeypatch):
    import zendaya_offline_tts as ot
    wav = np.linspace(-1.0, 1.0, num=2205, dtype=np.float32)  # 0.1s @ 22050
    monkeypatch.setattr(ot, "_get_model", lambda: _FakeModel(wav))
    pcm = ot.synth_to_pcm("One sentence.")
    arr = np.frombuffer(pcm, dtype="<i2")
    assert arr.dtype == np.int16
    assert len(arr) == 2205


def test_synth_to_pcm_concats_sentences(monkeypatch):
    import zendaya_offline_tts as ot
    monkeypatch.setattr(ot, "_get_model", lambda: _FakeModel(np.zeros(100, dtype=np.float32)))
    pcm = ot.synth_to_pcm("First. Second. Third.")
    arr = np.frombuffer(pcm, dtype="<i2")
    assert len(arr) == 300


def test_synth_to_pcm_empty_text_does_not_load_model(monkeypatch):
    import zendaya_offline_tts as ot

    def _boom():
        raise AssertionError("model should not load for empty text")

    monkeypatch.setattr(ot, "_get_model", _boom)
    assert ot.synth_to_pcm("   ") == b""


def test_synth_to_pcm_wraps_model_error(monkeypatch):
    import zendaya_offline_tts as ot

    class _Broken(_FakeModel):
        def tts(self, text, speaker=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(ot, "_get_model", lambda: _Broken(np.zeros(1, dtype=np.float32)))
    with pytest.raises(ot.OfflineTTSError):
        ot.synth_to_pcm("Hello.")
```

- [ ] **Step 2: Run to verify failure**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -k synth -v
```
Expected: FAIL — `AttributeError: ... has no attribute '_get_model'` / `synth_to_pcm`.

- [ ] **Step 3: Implement lazy model + synth**

Add to `backend/zendaya_offline_tts.py`:
```python
# ── lazy Coqui model singleton ──────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()


def _install_transformers_shim() -> None:
    """transformers 5.x removed isin_mps_friendly; coqui-tts 0.27.5 still imports
    it. Re-inject a torch.isin-based equivalent before importing TTS, so we don't
    have to downgrade the shared transformers (used by airllm/optimum)."""
    try:
        import torch
        import transformers.pytorch_utils as ptu
        if not hasattr(ptu, "isin_mps_friendly"):
            def isin_mps_friendly(elements, test_elements):
                return torch.isin(elements, test_elements)
            ptu.isin_mps_friendly = isin_mps_friendly
    except Exception:
        pass


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        _install_transformers_shim()
        try:
            from TTS.api import TTS as _TTSApi
        except Exception as e:
            raise OfflineTTSError(f"Coqui TTS import failed: {e}") from e
        try:
            _model = _TTSApi(model_name=MODEL_NAME, progress_bar=False, gpu=False)
        except Exception as e:
            raise OfflineTTSError(f"Coqui model load failed: {e}") from e
    return _model


def is_ready() -> bool:
    return _model is not None


def warmup() -> bool:
    try:
        _get_model()
        return True
    except OfflineTTSError:
        return False


def synth_to_pcm(text: str, target_sr: int = TARGET_SR, speaker: Optional[str] = None) -> bytes:
    sentences = _split_sentences(text)
    if not sentences:
        return b""
    model = _get_model()
    spk = speaker or DEFAULT_SPEAKER
    out = bytearray()
    for sentence in sentences:
        try:
            wav = model.tts(text=sentence, speaker=spk)
        except Exception as e:
            raise OfflineTTSError(f"Coqui synth failed: {e}") from e
        sr = getattr(getattr(model, "synthesizer", None), "output_sample_rate", TARGET_SR) or TARGET_SR
        out += _wave_to_pcm16(np.asarray(wav, dtype=np.float32), sr, target_sr)
    return bytes(out)
```

- [ ] **Step 4: Run to verify pass**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -v
```
Expected: all passed (14 total).

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_offline_tts.py backend/tests/test_zendaya_offline_tts.py
git -c commit.gpgsign=false commit -m "feat(voice): lazy Coqui model load + synth_to_pcm with transformers shim"
```

---

## Task 5: `/voice` command parsing and handling

**Files:**
- Modify: `backend/zendaya_offline_tts.py`
- Test: `backend/tests/test_zendaya_offline_tts.py`

- [ ] **Step 1: Add the failing tests**

Append to `backend/tests/test_zendaya_offline_tts.py`:
```python
@pytest.mark.parametrize("text,expected", [
    ("/voice offline", "offline"),
    ("/voice elevenlabs", "elevenlabs"),
    ("/voice", "status"),
    ("/voice status", "status"),
    ("use offline voice", "offline"),
    ("switch to elevenlabs voice", "elevenlabs"),
    ("use your free voice", "offline"),
    ("what's the weather", None),
    ("", None),
])
def test_parse_voice_command(text, expected):
    import zendaya_offline_tts as ot
    assert ot.parse_voice_command(text) == expected


def test_handle_voice_command_status_reports_current(tmp_data_dir):
    import zendaya_offline_tts as ot
    ot.set_voice_engine("offline")
    assert "offline" in ot.handle_voice_command("status").lower()


def test_handle_voice_command_switch_persists(tmp_data_dir):
    import zendaya_offline_tts as ot
    msg = ot.handle_voice_command("elevenlabs")
    assert ot.get_voice_engine() == "elevenlabs"
    assert "elevenlabs" in msg.lower()
```

- [ ] **Step 2: Run to verify failure**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -k voice_command -v
```
Expected: FAIL — `AttributeError: ... has no attribute 'parse_voice_command'`.

- [ ] **Step 3: Implement**

Add to `backend/zendaya_offline_tts.py`:
```python
# ── /voice command ──────────────────────────────────────────────────────────
_OFFLINE_WORDS = ("offline", "coqui", "local", "free")
_CLOUD_WORDS = ("elevenlabs", "eleven", "cloud", "online")
_OFFLINE_RE = re.compile(r"\b(?:%s)\b[\w\s]*\bvoice\b" % "|".join(_OFFLINE_WORDS))
_CLOUD_RE = re.compile(r"\b(?:%s)\b[\w\s]*\bvoice\b" % "|".join(_CLOUD_WORDS))


def parse_voice_command(user_text: str) -> Optional[str]:
    """Return 'offline' | 'elevenlabs' | 'status' for a voice-engine command, else None."""
    low = (user_text or "").strip().lower()
    if not low:
        return None
    if low.startswith("/voice"):
        arg = low[len("/voice"):].strip()
        if arg in ("", "status"):
            return "status"
        if arg in _OFFLINE_WORDS:
            return "offline"
        if arg in _CLOUD_WORDS:
            return "elevenlabs"
        return "status"
    if low in ("voice status", "which voice", "what voice are you using"):
        return "status"
    if _OFFLINE_RE.search(low):
        return "offline"
    if _CLOUD_RE.search(low):
        return "elevenlabs"
    return None


def handle_voice_command(action: str) -> str:
    if action == "status":
        return "I'm currently using my %s voice." % get_voice_engine()
    engine = set_voice_engine(action)
    if engine == "offline":
        return "Okay, switching to my offline voice."
    return "Okay, switching to my ElevenLabs voice."
```

- [ ] **Step 4: Run to verify pass**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -v
```
Expected: all passed (25 total).

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_offline_tts.py backend/tests/test_zendaya_offline_tts.py
git -c commit.gpgsign=false commit -m "feat(voice): /voice command parsing + handling"
```

---

## Task 6: Wire the offline engine into `zendaya.py`

**Files:**
- Modify: `backend/zendaya.py` (`_speak_offline_async` + `speak_async` hook near line 410; `/voice` dispatch near line 2889)

This edits the protected WIP file. Make ONLY these four edits. There are no automated tests here (importing `zendaya.py` in pytest is impractical — it pulls Gemini/Google/audio at import); verify with a syntax check, the full existing suite, and a manual smoke.

- [ ] **Step 1: Add `_speak_offline_async` immediately above `def speak_async` (line 410)**

Insert this function just before `def speak_async(text: str, voice_id: str):`:
```python
def _speak_offline_async(text: str):
    """Synthesize with the offline Coqui engine and play through the shared
    PCM/viseme pipeline (same path as ElevenLabs). Falls back to system TTS."""
    import zendaya_offline_tts as _offline_tts

    def _run():
        _TTS_STOP.clear()
        _set_tts_gate(True)
        try:
            import zendaya_visemes as _viz
            _viz.PLAYER.start(_viz.build_schedule(text))
            try:
                _viz.ANALYZER.reset()
            except Exception:
                pass
        except Exception:
            pass
        try:
            pcm = _offline_tts.synth_to_pcm(text, target_sr=_TTS_PCM_RATE)
            if not pcm:
                speak_system_fallback(text)
            elif not _TTS_STOP.is_set():
                _stream_pcm_playback(
                    _offline_tts.PcmBytesResponse(pcm), samplerate=_TTS_PCM_RATE
                )
        except Exception as e:
            print(f"(Offline TTS failed: {e})")
            speak_system_fallback(text)
        finally:
            _set_tts_gate(False)

    threading.Thread(target=_run, daemon=True).start()
```

- [ ] **Step 2: Add the engine hook at the very top of `speak_async`**

Change the start of `speak_async` from:
```python
def speak_async(text: str, voice_id: str):
    """Streams ElevenLabs TTS and plays as bytes arrive (low-latency)."""
    # Per-language voice override: if the active language has its own voice ID,
```
to:
```python
def speak_async(text: str, voice_id: str):
    """Streams ElevenLabs TTS and plays as bytes arrive (low-latency)."""
    # Offline-first hybrid: unless the user selected ElevenLabs, speak offline.
    try:
        import zendaya_offline_tts as _offline_tts
        _engine_pref = _offline_tts.get_voice_engine()
    except Exception:
        _offline_tts = None
        _engine_pref = "elevenlabs"
    if _offline_tts is not None and _engine_pref == "offline":
        _speak_offline_async(text)
        return

    # Per-language voice override: if the active language has its own voice ID,
```

- [ ] **Step 3: Make the ElevenLabs-unavailable branch fall back to offline**

Change:
```python
    if not _ELEVENLABS_READY or 'sd' not in globals() or not is_connected():
        speak_system_fallback(text)
        return
```
to:
```python
    if not _ELEVENLABS_READY or 'sd' not in globals() or not is_connected():
        # Offline-first: prefer the offline engine over robotic system TTS.
        if _offline_tts is not None:
            _speak_offline_async(text)
        else:
            speak_system_fallback(text)
        return
```

- [ ] **Step 4: Add the `/voice` dispatch in `handle_user_command` (just before the `# --- Face-mode switching` block near line 2889)**

Insert:
```python
    # --- Voice engine switch: "/voice offline", "use my elevenlabs voice", "/voice status" ---
    try:
        import zendaya_offline_tts as _offline_tts
        _vcmd = _offline_tts.parse_voice_command(user_text)
    except Exception:
        _offline_tts = None
        _vcmd = None
    if _vcmd:
        msg = _offline_tts.handle_voice_command(_vcmd)
        send_response(msg)
        add_to_memory(PERSONA_NAME, msg)
        return

```

- [ ] **Step 5: Syntax-check and run the full backend suite (no regressions)**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import ast; ast.parse(open(r'backend/zendaya.py', encoding='utf-8').read()); print('zendaya.py parses OK')"
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests -q
```
Expected: `zendaya.py parses OK`, then the full suite passes (existing tests + the 25 new ones).

- [ ] **Step 6: Commit (stage ONLY zendaya.py; verify nothing else)**

```powershell
git add backend/zendaya.py
git -c commit.gpgsign=false commit -m "feat(voice): route speak_async through offline-first engine + /voice switch"
git show --stat HEAD
```
Expected: `git show --stat HEAD` lists **only** `backend/zendaya.py`. If anything else appears, `git reset HEAD~1 --soft` and re-stage just that file.

---

## Task 7: End-to-end verification (real Coqui synthesis)

**Files:** none (verification only)

- [ ] **Step 1: One-time model download + offline smoke synth**

Run (downloads `tts_models/en/vctk/vits` once; needs internet this once, then it's cached/offline):
```powershell
$env:PYTHONIOENCODING = "utf-8"
Push-Location backend
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import zendaya_offline_tts as ot; pcm = ot.synth_to_pcm('Hello, I am Zendaya, speaking with my offline voice.'); print('PCM bytes:', len(pcm), '| approx seconds:', round(len(pcm)/2/22050, 2))"
Pop-Location
```
Expected: a non-zero `PCM bytes` count and a sensible duration (~3–4s). First run prints model-download progress.

- [ ] **Step 2: Optional — add a slow real-synth regression test**

Append to `backend/tests/test_zendaya_offline_tts.py`:
```python
@pytest.mark.slow
def test_real_synthesis_smoke():
    """Real Coqui synthesis. Self-skips if deps/model are absent, so it never
    hard-fails the suite. Run the fast suite with -m "not slow"; run this with -m slow."""
    import zendaya_offline_tts as ot
    if not ot.warmup():
        pytest.skip("Coqui offline TTS not available (deps/model missing)")
    pcm = ot.synth_to_pcm("Hello from the offline voice.")
    arr = np.frombuffer(pcm, dtype="<i2")
    assert arr.dtype == np.int16
    assert len(arr) > 22050  # at least ~1s of audio
```
Run it explicitly:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_zendaya_offline_tts.py -m slow -v
```
Expected: 1 passed (takes several seconds). Then commit:
```powershell
git add backend/tests/test_zendaya_offline_tts.py
git -c commit.gpgsign=false commit -m "test(voice): slow real-synthesis smoke test"
```

- [ ] **Step 3: Manual end-to-end in the running app**

Start Zendaya, then in the HUD terminal (or by voice):
1. Say/type a normal message → confirm she replies in the **Coqui** voice (default offline) and the **orb/visemes animate**.
2. Type `/voice elevenlabs` → confirm she says "switching to my ElevenLabs voice" and subsequent replies use ElevenLabs.
3. Type `/voice offline` → confirm she switches back; the choice **persists** after a restart (check `zendaya_data/voice_engine.json`).
4. While she's speaking offline, trigger barge-in (speak the wake word) → confirm playback **cuts off**.

Expected: all four behaviors hold. If the offline voice is silent, re-check Task 1 (FFmpeg on PATH, `import TTS` OK).

- [ ] **Step 4: Pick the final VCTK speaker (optional polish)**

Audition a few speakers and set `DEFAULT_SPEAKER` in `backend/zendaya_offline_tts.py` to your favorite. Create `backend/_audition.py`:
```python
import wave
import numpy as np
import zendaya_offline_tts as ot

model = ot._get_model()
sr = model.synthesizer.output_sample_rate
for spk in ["p225", "p243", "p270", "p294", "p306", "p330", "p339", "p361"]:
    wav = np.clip(np.asarray(model.tts(text="Hi, I am Zendaya.", speaker=spk), dtype=np.float32), -1, 1)
    pcm = (wav * 32767).astype("<i2").tobytes()
    with wave.open(f"spk_{spk}.wav", "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
    print("wrote spk_" + spk + ".wav")
```
Run it, listen to the `spk_*.wav` files, update `DEFAULT_SPEAKER`, then delete the samples and the script:
```powershell
$env:PYTHONIOENCODING = "utf-8"
Push-Location backend
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" _audition.py
Pop-Location
Remove-Item backend\spk_*.wav, backend\_audition.py
```
Commit the one-line change:
```powershell
git add backend/zendaya_offline_tts.py
git -c commit.gpgsign=false commit -m "feat(voice): set default VCTK speaker"
```
(If `soundfile` isn't installed, skip this polish step or write WAVs via the `wave` module.)

---

## Done when
- `backend/tests/test_zendaya_offline_tts.py` passes (25 fast tests; slow test passes on demand).
- The full `backend/tests` suite is green (no regressions).
- Default replies use the offline Coqui voice with working orb/visemes/barge-in; `/voice elevenlabs` and `/voice offline` switch and persist.
- The future XTTS-v2 African-American clone can drop in behind `synth_to_pcm()` without touching `zendaya.py`.
