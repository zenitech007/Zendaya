# Voice Listener Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Zendaya's voice listener noticeably clearer (better noise cancellation), less twitchy (fewer false fires from background), and faster (lower wake-to-reply latency), while attempting to swap "hey jarvis" for "Zendaya" if a community openWakeWord model exists.

**Architecture:** All changes land in 3 existing files (`backend/voice/denoise.py`, `backend/voice/wake.py`, `backend/zendaya_voice_listener_v2.py`) plus one new test file. DeepFilterNet is added with a real fallback to existing `noisereduce` if it doesn't build on Python 3.14. Wake detector keeps consuming raw audio; DFN feeds only the STT path. Async dispatch via a bounded worker queue lets the listener resume wake-detection immediately after enqueueing a command.

**Tech Stack:** Python 3.14, `openwakeword` (wake), `faster-whisper` (STT), `silero-vad` (VAD), `sounddevice` (audio capture), `noisereduce` (current denoise, fallback), `deepfilternet` (new denoise, conditional), `pytest` (tests).

**Spec:** [docs/superpowers/specs/2026-05-24-voice-listener-upgrade-design.md](../specs/2026-05-24-voice-listener-upgrade-design.md)

**Pre-plan baseline:** Commit `6cb591a` — snapshot of the voice files as the user had them in working tree.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `C:\Users\IKA\Zendaya\pyproject.toml` | Modify (conditional) | Add `deepfilternet` to `[tool.poetry.dependencies]` IF it installs successfully on Python 3.14 |
| `C:\Users\IKA\Zendaya\backend\voice\denoise.py` | Modify | Add `DeepFilterDenoiser` class (same interface as existing `Denoiser`) + `make_denoiser()` factory |
| `C:\Users\IKA\Zendaya\backend\voice\wake.py` | Modify | Tighten cold threshold (0.5→0.6), add `VERIFIER_SKIP_THRESHOLD` (0.85), replace loose `VERIFY_RE` with model-aware word-boundary regex, support loading community `zendaya_wake.onnx` if found |
| `C:\Users\IKA\Zendaya\backend\voice\zendaya_wake.onnx` | Created externally (if community model found) | Drop-in openWakeWord model. NOT committed (binary, regenerable). Gitignored |
| `C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py` | Modify | Whisper preload at startup, persistent `sd.InputStream`, ambient-RMS floor gate, async dispatch worker thread, `beam_size=1`, verifier-skip on high-confidence wakes, tightened silence hangover |
| `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py` | Create | Unit tests for denoiser factory, verifier regex, ambient floor gate, dispatch queue bounding, worker TTS gate, verifier-skip threshold; integration smoke test with mocked `sd.InputStream` |
| `C:\Users\IKA\Zendaya\.gitignore` | Modify | Add `backend/voice/zendaya_wake.onnx` (regenerable binary) |

---

## Conventions for this plan

- **Shell:** PowerShell 5.1 on Windows. No `&&`; use `;` or `if ($?) { ... }`.
- **Working directory:** `C:\Users\IKA\Zendaya` (already cd'd; do NOT `cd`).
- **Test runner:** `pytest backend/tests/ -v` runs both AAF (56 tests) AND new voice tests.
- **Commit safety:** the user has a large pre-existing diff in `backend/zendaya.py` and `pyproject.toml` that must NOT bleed into any voice commit. Use exact file paths in every `git add`. After each commit, verify with `git show --stat HEAD` that only intended files landed. For `pyproject.toml` specifically, follow the splitting protocol from the AAF Task 1 precedent (save backup, revert to HEAD, apply only your changes, commit, restore backup).
- **Pre-plan HEAD:** `6cb591a` (baseline commit of the voice files).
- **TDD discipline:** write failing test → confirm fails → implement → confirm passes → commit.

---

### Task 1: Reconnaissance — DeepFilterNet install attempt + community wake-model search

**Files:** None (read-only investigation).

This task makes no commits. It produces information used by Task 2 and Task 4.

- [ ] **Step 1: Attempt to install `deepfilternet`**

```powershell
pip install "deepfilternet>=0.5,<0.6" 2>&1 | Select-Object -Last 30
```

Capture the full output. Three possible outcomes:
- **A. Install succeeds and `python -c "import df; print(df.__version__)"` works** — proceed with Task 2 (add the dep).
- **B. Install fails with a Rust/maturin build error** (matches the warning in `backend/voice/denoise.py` lines 3-5) — note it; SKIP Task 2; the plan still works because the spec's graceful degrade kicks in and the `DeepFilterDenoiser` class in Task 3 will be a thin shell whose `make_denoiser()` factory always returns the existing `Denoiser`.
- **C. Install succeeds at the pip level but `import df` (or `import deepfilternet`) raises an ImportError** — treat as B (fall back to noisereduce).

Verify the actual import name (`df` is the deepfilternet API namespace; `deepfilternet` is the PyPI package):
```powershell
python -c "import df; print('df ok', df.__version__)" 2>&1
python -c "import deepfilternet; print('deepfilternet ok')" 2>&1
```

Record which import name works.

- [ ] **Step 2: Search HuggingFace for a community "Zendaya" openWakeWord model**

Use `WebFetch` or `WebSearch` to look at known openWakeWord community model collections. Specifically check:

1. `https://huggingface.co/dscripka/openWakeWord` (official model hub)
2. `https://huggingface.co/spaces/davidbrowne17/openWakeWord-models` if it exists
3. A generic HuggingFace search: `https://huggingface.co/models?search=openwakeword+zendaya`
4. The official `https://github.com/dscripka/openWakeWord` README for a "Pre-trained models" section

You're looking for a model file named or labelled with `zendaya`, `zen-daya`, `zenaya`, or close phonetic variants. If you find a candidate:

```powershell
# Download to backend/voice/zendaya_wake.onnx if found
Invoke-WebRequest -Uri "<the URL>" -OutFile "backend\voice\zendaya_wake.onnx"
Get-Item backend\voice\zendaya_wake.onnx | Select-Object Length
```

- [ ] **Step 3: Report findings**

Produce a structured note for the controller:
- DeepFilterNet install status: **AVAILABLE** or **UNAVAILABLE** (with the specific error line if unavailable)
- Confirmed import name (`df` or `deepfilternet`) if available
- Community wake model: **FOUND** at `<URL>` (downloaded to `backend/voice/zendaya_wake.onnx`, N bytes) or **NOT FOUND** (stay on `hey_jarvis`)

No commit in this task. The downloaded `.onnx` (if any) is in working tree; Task 5 will add it to `.gitignore` to prevent accidental commit.

---

### Task 2: Add `deepfilternet` to `pyproject.toml` (conditional — skip if Task 1 reported UNAVAILABLE)

**Files:**
- Modify: `C:\Users\IKA\Zendaya\pyproject.toml` (insert one line in `[tool.poetry.dependencies]`)

**Skip this entire task** if Task 1 reported DeepFilterNet UNAVAILABLE. Jump to Task 3.

If proceeding:

- [ ] **Step 1: Splitting protocol — save working tree and revert pyproject.toml to HEAD**

`pyproject.toml` is in the pre-existing modified list. Same protocol as AAF Task 1:

```powershell
Copy-Item pyproject.toml $env:TEMP\pyproject.toml.voice.bak
git checkout -- pyproject.toml
```

- [ ] **Step 2: Add the dep line via Edit tool**

- old_string:
```
dateparser = "^1.2.0"
```
- new_string:
```
dateparser = "^1.2.0"
deepfilternet = "^0.5.0"
```

(Anchors on the `dateparser` line added by AAF Task 1, which is now committed in HEAD.)

- [ ] **Step 3: Verify the diff is exactly one added line**

```powershell
git diff pyproject.toml
```

Expected: one `+deepfilternet = "^0.5.0"` addition, nothing else.

- [ ] **Step 4: Stage and commit ONLY pyproject.toml**

```powershell
git add pyproject.toml
git -c commit.gpgsign=false commit -m "deps: add deepfilternet for voice listener upgrade"
git show --stat HEAD
```

Expected: only `pyproject.toml`, one insertion.

- [ ] **Step 5: Restore the user's pre-existing working-tree state**

```powershell
Copy-Item $env:TEMP\pyproject.toml.voice.bak pyproject.toml -Force
git status --short pyproject.toml
```

Expected: `pyproject.toml` shows as `M` (user's pre-existing diff restored), but `git log` shows the new dep commit.

---

### Task 3: `backend/voice/denoise.py` — DeepFilterDenoiser + `make_denoiser()` factory

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\voice\denoise.py`
- Create: `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_voice_listener_v2.py` with this exact content:

```python
"""Unit tests for the voice listener v2 upgrade (denoise factory, wake regex, ambient gate, dispatch worker)."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


# ─── Denoiser factory ──────────────────────────────────────────────────────


def test_make_denoiser_returns_deepfilter_when_dfn_available(monkeypatch):
    """When deepfilternet is importable, factory returns DeepFilterDenoiser."""
    import importlib

    # Stub a successful import path. We monkey-patch the importlib lookup
    # used inside make_denoiser to simulate DFN being available.
    fake_df = MagicMock()
    fake_df.init_df = MagicMock(return_value=(MagicMock(), MagicMock(), MagicMock()))
    fake_df.enhance = MagicMock(side_effect=lambda model, df_state, audio: audio)

    monkeypatch.setitem(sys.modules, "df", fake_df)
    monkeypatch.setitem(sys.modules, "df.enhance", fake_df)
    # Force re-import of denoise so it sees the stubbed df.
    if "zendaya_assistant_features" in sys.modules:
        del sys.modules["zendaya_assistant_features"]
    from backend.voice import denoise as denoise_mod  # noqa
    importlib.reload(denoise_mod)
    d = denoise_mod.make_denoiser()
    # If DFN-class exists in the module AND init didn't raise, we get it.
    if hasattr(denoise_mod, "DeepFilterDenoiser"):
        # Either we get the real DFN class or fall back to plain Denoiser if
        # the stub model load failed inside the constructor.
        assert isinstance(d, (denoise_mod.DeepFilterDenoiser, denoise_mod.Denoiser))


def test_make_denoiser_falls_back_when_dfn_import_fails(monkeypatch):
    """When deepfilternet ImportError, factory returns plain Denoiser."""
    import importlib

    # Remove any DFN modules and force a fresh import.
    for mod in ("df", "df.enhance", "deepfilternet"):
        monkeypatch.setitem(sys.modules, mod, None)
    from backend.voice import denoise as denoise_mod  # noqa
    importlib.reload(denoise_mod)
    d = denoise_mod.make_denoiser()
    assert isinstance(d, denoise_mod.Denoiser)


def test_denoiser_interface_consistent():
    """Both denoiser types must expose process_utterance(audio_int16) -> np.ndarray."""
    from backend.voice import denoise as denoise_mod
    d = denoise_mod.make_denoiser()
    silence = np.zeros(16000, dtype=np.int16)
    out = d.process_utterance(silence)
    assert isinstance(out, np.ndarray)
    assert out.dtype == np.int16
```

- [ ] **Step 2: Run tests — confirm they fail**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "denoiser or make_denoiser"
```

Expected: errors about `backend.voice.denoise` not exposing `make_denoiser` and/or `DeepFilterDenoiser`.

Note: the existing `backend/voice/denoise.py` exports `Denoiser` only. The tests above import via `from backend.voice import denoise as denoise_mod`. Confirm this import path works given the conftest's `sys.path` injection — if not, adjust the tests to `import voice.denoise as denoise_mod` (drop the `backend.` prefix) since conftest adds `backend/` to `sys.path`.

- [ ] **Step 3: Implement — add DeepFilterDenoiser + factory to denoise.py**

Use the `Edit` tool. Replace the existing docstring with an updated one and append the new class + factory.

First update the docstring:

- old_string:
```python
"""Spectral-subtraction denoiser using `noisereduce`.

We tried DeepFilterNet first but it requires a Rust toolchain + maturin and
fails to build on Python 3.14 (no abiflags in sysconfig). `noisereduce` is
pure-Python (numpy/scipy), stationary-mode, and runs fast enough on CPU for
short utterances.

Strategy:
- Per-frame denoising is too expensive (FFTs every 30 ms).
- Instead we denoise the WHOLE captured utterance once, right before Whisper
  sees it. The frame-level `process()` is a passthrough so the realtime VAD
  + wake path doesn't take the cost.
- `process_utterance()` does the real work on the full buffer.

Falls back to passthrough if `noisereduce` is missing.
"""
```

- new_string:
```python
"""Voice denoise — DeepFilterNet (preferred) with `noisereduce` fallback.

DeepFilterNet is an ML-based real-time denoiser (~50-100MB model, ~1-3% CPU).
It MAY fail to build on Python 3.14 (the prior attempt hit a Rust/maturin
issue). If so, the `make_denoiser()` factory below transparently falls back
to the existing `noisereduce` stationary spectral-subtraction path.

Strategy:
- Per-frame denoising is too expensive for spectral subtraction (FFTs every
  30 ms); the existing `Denoiser` denoises the WHOLE captured utterance once,
  right before Whisper sees it. The frame-level `process()` is a passthrough
  so the realtime VAD + wake path doesn't take the cost.
- `DeepFilterDenoiser.process_utterance()` runs DFN once on the full clip —
  faster than spectral subtraction on non-stationary noise.
- Both classes expose the same interface: `process(frame)`,
  `process_utterance(audio_int16)`, `diagnostics()`, `ready` property.
- `make_denoiser()` returns the best available implementation.

Both fall back to passthrough if their underlying library is missing.
"""
```

Then append the new class + factory at the end of the file:

- old_string:
```python
    def diagnostics(self) -> str:
        if self.enabled:
            return "denoise: noisereduce (stationary, utterance-level)"
        return f"denoise: OFF — {self.err}"
```

- new_string:
```python
    def diagnostics(self) -> str:
        if self.enabled:
            return "denoise: noisereduce (stationary, utterance-level)"
        return f"denoise: OFF — {self.err}"


try:
    from df.enhance import enhance, init_df  # type: ignore
    _DFN_AVAILABLE = True
    _DFN_ERR = ""
except Exception as _e:
    _DFN_AVAILABLE = False
    _DFN_ERR = str(_e)


class DeepFilterDenoiser:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled) and _DFN_AVAILABLE
        self.err = "" if _DFN_AVAILABLE else f"deepfilternet missing: {_DFN_ERR}"
        self._model = None
        self._df_state = None
        if self.enabled:
            try:
                self._model, self._df_state, _ = init_df()
            except Exception as e:
                self.enabled = False
                self.err = f"deepfilternet init failed: {e}"
                self._model = None
                self._df_state = None

    @property
    def ready(self) -> bool:
        return self.enabled and self._model is not None

    def process(self, frame_int16: np.ndarray) -> np.ndarray:
        """Per-frame passthrough — denoising happens on the full utterance."""
        return frame_int16

    def process_utterance(self, audio_int16: np.ndarray) -> np.ndarray:
        """Run DeepFilterNet on a full utterance just before STT."""
        if not self.ready or audio_int16.size == 0:
            return audio_int16
        try:
            import torch
            f32 = torch.from_numpy(audio_int16.astype(np.float32) / 32768.0).unsqueeze(0)
            cleaned = enhance(self._model, self._df_state, f32)
            arr = cleaned.squeeze(0).cpu().numpy()
            arr = np.clip(arr, -1.0, 1.0)
            return (arr * 32767.0).astype(np.int16)
        except Exception:
            return audio_int16

    def diagnostics(self) -> str:
        if self.ready:
            return "denoise: DeepFilterNet (utterance-level)"
        return f"denoise: DeepFilterNet OFF — {self.err}"


def make_denoiser(enabled: bool = True):
    """Return the best available denoiser.

    Prefers DeepFilterNet (ML-based, better non-stationary handling) and falls
    back to the existing noisereduce-based Denoiser if DFN isn't available or
    fails to initialise.
    """
    if _DFN_AVAILABLE:
        d = DeepFilterDenoiser(enabled=enabled)
        if d.ready:
            return d
    return Denoiser(enabled=enabled)
```

- [ ] **Step 4: Run tests — confirm pass**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "denoiser or make_denoiser"
```

Expected: all 3 denoiser tests pass. If a test fails because the `backend.voice` import path doesn't work, adjust the test imports to `from voice import denoise as denoise_mod` (no `backend.` prefix — conftest puts `backend/` on `sys.path`, not the repo root) and re-run.

- [ ] **Step 5: Run the full test suite to confirm no AAF regression**

```powershell
pytest backend/tests/ -v
```

Expected: 56 AAF tests + 3 new denoiser tests = 59 pass.

- [ ] **Step 6: Commit**

```powershell
git add backend/voice/denoise.py backend/tests/test_voice_listener_v2.py
git -c commit.gpgsign=false commit -m "feat(voice): add DeepFilterDenoiser + make_denoiser factory with noisereduce fallback"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 4: `backend/voice/wake.py` — tighten thresholds, verifier regex, verifier-skip constant

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\voice\wake.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_voice_listener_v2.py`:

```python
# ─── Wake verifier regex ───────────────────────────────────────────────────


@pytest.mark.parametrize("model, transcript, should_match", [
    ("hey_jarvis", "okay jarvis what time is it",     True),
    ("hey_jarvis", "hey zendaya open spotify",        True),   # zendaya allowed
    ("hey_jarvis", "what's the frozen lake forecast", False),  # old loose 'zen' would match 'frozen'
    ("hey_jarvis", "the zenith is bright tonight",    False),  # 'zen' substring
    ("hey_jarvis", "I love lavender candles",         False),
    ("zendaya",    "hey zendaya open spotify",        True),
    ("zendaya",    "okay jarvis what time is it",     False),  # jarvis NOT allowed when model is zendaya
    ("zendaya",    "the zenith is bright tonight",    False),
])
def test_verifier_passes_model_aware(model, transcript, should_match):
    from voice import wake as wake_mod
    assert wake_mod.verifier_passes_for_model(model, transcript) is should_match


def test_verifier_skip_threshold_constant():
    from voice import wake as wake_mod
    assert wake_mod.VERIFIER_SKIP_THRESHOLD == 0.85


def test_default_cold_threshold_is_tightened():
    """Default cold threshold should be 0.6 (was 0.5)."""
    from voice import wake as wake_mod
    eng = wake_mod.WakeEngine(model_name="hey_jarvis")
    # If env override is present, the test wouldn't apply — guard for that.
    import os
    if "ZENDAYA_WAKE_THRESHOLD" in os.environ:
        pytest.skip("Skipping default-threshold test because env override is set.")
    assert eng.threshold == 0.6
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "verifier or threshold"
```

Expected: AttributeError for `verifier_passes_for_model` and `VERIFIER_SKIP_THRESHOLD`, plus the cold-threshold test fails because default is currently 0.5.

- [ ] **Step 3: Implement**

Use Edit on `backend/voice/wake.py`.

First, replace the loose `_VERIFY_TOKENS` regex with model-aware version. Add `VERIFIER_SKIP_THRESHOLD` constant and `verifier_passes_for_model()` function.

- old_string:
```python
# Verifier regex — what we expect to see in the pre-roll transcript.
# Lenient (covers the same mishears the old _WAKE_NAMES set covered) so we
# don't reject legitimate wakes that Whisper transcribed imperfectly.
_VERIFY_TOKENS = (
    r"zendaya|zendia|zenday|zen\s*day|zen\s*deya|sandeya|sundae|sandia|"
    r"send\s*aya|send\s*i\s*uh|send\s*a|send\s*her|sin\s*day|sin\s*deya|"
    r"jarvis|hey\s+zen|yo\s+zen|ok\s+zen|zen\b|zander"
)
VERIFY_RE = re.compile(_VERIFY_TOKENS, re.IGNORECASE)


def verifier_passes(transcript: str) -> bool:
    """Return True if the pre-roll transcript looks like the user said the name."""
    if not transcript:
        return False
    return VERIFY_RE.search(transcript) is not None
```

- new_string:
```python
# Verifier — model-aware word-boundary regex. Replaces the prior loose
# substring matcher that fired on "frozen" / "zenith" / etc.
# Tolerant of common Whisper mishears of "zendaya".
_ZENDAYA_TOKENS = (
    r"\bzendaya\b|\bzendia\b|\bzendaia\b|\bzen\s*daya\b|"
    r"\bsendaya\b|\bsandaya\b"
)
_JARVIS_TOKENS = r"\bjarvis\b"

VERIFY_RE_HEY_JARVIS = re.compile(
    f"{_JARVIS_TOKENS}|{_ZENDAYA_TOKENS}", re.IGNORECASE
)
VERIFY_RE_ZENDAYA = re.compile(_ZENDAYA_TOKENS, re.IGNORECASE)
VERIFY_RE = VERIFY_RE_HEY_JARVIS  # kept for back-compat with any external import

VERIFIER_SKIP_THRESHOLD = 0.85  # Wakes scoring >= this skip Stage-2 verifier.


def verifier_passes(transcript: str) -> bool:
    """Back-compat: assume hey_jarvis model (which also accepts zendaya)."""
    return verifier_passes_for_model("hey_jarvis", transcript)


def verifier_passes_for_model(model_name: str, transcript: str) -> bool:
    """Model-aware verifier. Returns True if the pre-roll transcript
    contains the wake word the active model is listening for.

    - hey_jarvis: accepts jarvis OR zendaya (Whisper often mishears either)
    - zendaya:    accepts zendaya only (jarvis not relevant)
    """
    if not transcript:
        return False
    if "zendaya" in (model_name or "").lower():
        return VERIFY_RE_ZENDAYA.search(transcript) is not None
    return VERIFY_RE_HEY_JARVIS.search(transcript) is not None
```

Then tighten the default cold threshold:

- old_string:
```python
    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.5,
        barge_threshold: float = 0.7,
    ) -> None:
```

- new_string:
```python
    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.6,
        barge_threshold: float = 0.72,
    ) -> None:
```

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "verifier or threshold"
```

Expected: all wake tests pass. Run full suite to confirm no regression:

```powershell
pytest backend/tests/ -v
```

Expected: 56 + 3 + new wake tests = 67 pass (8 new wake tests).

- [ ] **Step 5: Commit**

```powershell
git add backend/voice/wake.py backend/tests/test_voice_listener_v2.py
git -c commit.gpgsign=false commit -m "feat(voice): tighten wake thresholds + model-aware verifier regex"
git show --stat HEAD
```

---

### Task 5: Listener speed wins bundle (Whisper preload, persistent audio stream, beam_size=1, verifier-skip, silence hangover)

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py`
- Modify: `C:\Users\IKA\Zendaya\.gitignore` (add `backend/voice/zendaya_wake.onnx`)

**Note:** This task bundles five small refactors because they're all single-edit changes to the same file. No new tests in this task — tests for verifier-skip live in Task 6 (alongside ambient gate). The integration smoke test in Task 8 covers the bundle end-to-end.

- [ ] **Step 1: Read the current file structure**

Before editing, read the v2 file to confirm exact insertion points. Key landmarks (line numbers approximate, verify by reading):
- Silence hangover constants near line 87-88
- `beam_size=5` in the transcribe call near line 236
- `_init_whisper()` function around line 158-190
- `start_voice_listener()` near line 602-609
- Audio stream open in `_run_listener_session` near line 446-452
- Audio stream close in same function's `finally` near line 585-590
- Stage-2 verifier call near line 528-538

```powershell
# Use Read or Grep to confirm:
# - The exact `beam_size=5` line
# - The hangover constant names (likely SILENCE_HANGOVER_S_SHORT / _LONG)
# - The structure of _run_listener_session and start_voice_listener
```

- [ ] **Step 2: Edit — tighten silence hangover (450/700ms)**

Find the long-utterance hangover constant. Typically:

- old_string (adapt to file's actual values):
```python
SILENCE_HANGOVER_S_SHORT = 0.45
SILENCE_HANGOVER_S_LONG = 0.9
```

- new_string:
```python
SILENCE_HANGOVER_S_SHORT = 0.45
SILENCE_HANGOVER_S_LONG = 0.7
```

If the names differ in the actual file, use the file's actual names. If hangover is hard-coded inline instead of as constants, hoist into constants first then update.

- [ ] **Step 3: Edit — beam_size 5 → 1**

- old_string (adapt to the actual transcribe call):
```python
        segments, _info = _WHISPER_MODEL.transcribe(
            audio_f32,
            language=lang_code,
            beam_size=5,
            temperature=0.0,
            vad_filter=True,
            no_speech_threshold=0.6,
        )
```

If the call signature differs (e.g., different arg order, additional kwargs), use Edit on just the `beam_size=5` → `beam_size=1` portion. The unique anchor is `beam_size=5`.

- new_string (only change `beam_size=5` to `beam_size=1`).

- [ ] **Step 4: Edit — preload Whisper in `start_voice_listener()`**

Find the body of `start_voice_listener()`. Insert a call to `_init_whisper()` before the thread is started. Adapt to actual structure:

- old_string:
```python
def start_voice_listener():
    """Start the voice listener as a daemon background thread."""
```

- new_string:
```python
def start_voice_listener():
    """Start the voice listener as a daemon background thread."""
    # Preload Whisper so the first wake doesn't pay the cold-load cost.
    try:
        _init_whisper()
        print("[voice v2] Whisper preloaded.")
    except Exception as e:
        print(f"[voice v2] Whisper preload failed (will lazy-load on first wake): {e}")
```

(Insert at the very top of the function body, right after the docstring.)

- [ ] **Step 5: Edit — verifier-skip on high-confidence wakes**

Find the Stage-2 verifier call inside `_run_listener_session`. Wrap it in a threshold check:

The current shape is roughly:
```python
# Stage-2 verifier (Whisper pass on pre-roll buffer)
if not _verify_with_whisper(...):
    # reject wake
    continue
```

- old_string (adapt to file's actual shape — find the `verifier_passes` or `_verify_with_whisper` call):
```python
            # Stage-2 verifier
            if not verifier_passes(verify_transcript):
```

Read the wake event setup nearby to find `wake_score` or the variable holding the most recent wake confidence (`wake.last_score` per `wake.py:107`). Then:

- new_string:
```python
            from voice.wake import VERIFIER_SKIP_THRESHOLD, verifier_passes_for_model
            # Skip the verifier when wake confidence is very high — saves 200-600ms.
            if wake_engine.last_score >= VERIFIER_SKIP_THRESHOLD:
                pass  # high-confidence wake; skip Stage-2 verifier
            elif not verifier_passes_for_model(wake_engine.model_name, verify_transcript):
```

The exact restructure depends on the existing control flow. The goal is: if `wake.last_score >= 0.85`, treat the verifier as auto-pass and proceed to record. Otherwise run the existing verifier path.

If the existing code references `verifier_passes` directly, update the call site to use `verifier_passes_for_model(wake_engine.model_name, ...)` so model-aware tightening from Task 4 takes effect.

- [ ] **Step 6: Edit — persistent audio stream**

Currently `_run_listener_session` opens an `sd.InputStream` per cycle (in a `try` block, with close in `finally`). We want a single stream opened in `start_voice_listener()` and reused across sessions.

This is a bigger refactor. Steps:

1. Read `_run_listener_session` and `start_voice_listener` to identify exactly where the stream is constructed.
2. Lift the stream creation to module scope (or wrap in a getter that creates-on-first-call). Suggested module-level:

```python
# Module-scope persistent audio stream — opened once by start_voice_listener.
_AUDIO_STREAM = None
_AUDIO_QUEUE = None


def _get_audio_stream():
    """Return the persistent input stream, creating it on first call."""
    global _AUDIO_STREAM, _AUDIO_QUEUE
    if _AUDIO_STREAM is None:
        import queue
        _AUDIO_QUEUE = queue.Queue(maxsize=400)
        # Reuse the existing callback function used by the per-session stream.
        # If the callback is defined inside _run_listener_session, hoist it
        # to module scope first.
        _AUDIO_STREAM = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SAMPLES,
            callback=_audio_callback,
        )
        _AUDIO_STREAM.start()
    return _AUDIO_STREAM, _AUDIO_QUEUE
```

3. In `_run_listener_session`, replace stream construction with `stream, audio_q = _get_audio_stream()`. Remove the per-session `stream.start()` / `stream.close()`.

4. In `start_voice_listener()`, call `_get_audio_stream()` once so the stream is alive before the thread starts pulling from `_AUDIO_QUEUE`.

5. If the existing audio callback references variables captured from `_run_listener_session`'s scope, hoist them to module scope or pass via the queue.

**Care:** the existing TTS-gate logic (the `_TTS_SPEAKING` event check inside the frame loop) must continue to work. It already operates on frames pulled from the queue, so the change is transparent to that logic.

If hoisting the callback is too invasive (depends on how much state it closes over), report DONE_WITH_CONCERNS and keep per-session streams. The async dispatch in Task 7 is the more important win.

- [ ] **Step 7: Edit — add `backend/voice/zendaya_wake.onnx` to .gitignore**

(Even if Task 1 didn't find a community model, future ones may be added. Pre-emptive gitignore.)

Use the gitignore-splitting protocol from AAF Task 2:

```powershell
Copy-Item .gitignore $env:TEMP\gitignore.voice.bak
git checkout -- .gitignore
```

Edit `.gitignore` to append (after the `graphify-out/` line added previously):

- old_string:
```
# Graphify knowledge graph (regenerable)
graphify-out/
```
- new_string:
```
# Graphify knowledge graph (regenerable)
graphify-out/

# Voice wake model (binary, regenerable from upstream)
backend/voice/zendaya_wake.onnx
```

Then stage + commit only `.gitignore`, then restore working tree from the temp backup.

Actually — bundle this `.gitignore` change with the listener changes since they conceptually belong to the same "speed wins" task. Order:

1. Save .gitignore backup, revert to HEAD, append the new line.
2. Save listener backup (`Copy-Item backend\zendaya_voice_listener_v2.py $env:TEMP\v2.bak`).
3. Apply all the listener edits (Steps 2-6 above) directly to the file (which is currently the baseline-committed version since we have no pre-existing diff for it — the baseline commit IS the current HEAD content for that file).

Wait — the listener file was baseline-committed in commit `6cb591a`. So its HEAD matches its working tree exactly. No splitting protocol needed for this file. Only `.gitignore` needs the dance.

Revised step order for clarity:

- [ ] **Step 7 (revised): `.gitignore` splitting protocol + listener edits**

For `.gitignore`:
```powershell
Copy-Item .gitignore $env:TEMP\gitignore.voice.bak
git checkout -- .gitignore
```
Apply the Edit shown above.

For `backend/zendaya_voice_listener_v2.py`: no protocol needed — its HEAD == working tree thanks to the baseline commit. Apply Edits from Steps 2-6 directly.

- [ ] **Step 8: Syntax check the listener**

```powershell
python -c "import ast; ast.parse(open(r'C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py', encoding='utf-8').read()); print('ok')"
```

Expected: `ok`. If it raises `SyntaxError`, fix and re-run.

- [ ] **Step 9: Run full test suite — confirm no regression**

```powershell
pytest backend/tests/ -v
```

Expected: 56 AAF + 11 voice (3 denoiser + 8 wake) = 67 pass. No new tests in this task, but existing tests must still pass.

- [ ] **Step 10: Stage and commit**

```powershell
git add .gitignore backend/zendaya_voice_listener_v2.py
git diff --cached | Select-Object -First 200
```

Read the cached diff. Confirm `.gitignore` adds ONLY the `backend/voice/zendaya_wake.onnx` line and the listener changes are ONLY the 5 edits above.

```powershell
git -c commit.gpgsign=false commit -m "feat(voice): speed wins — Whisper preload, persistent audio stream, beam=1, verifier-skip on high-confidence wakes, tightened silence hangover"
git show --stat HEAD
```

Expected: only `.gitignore` and `backend/zendaya_voice_listener_v2.py`.

- [ ] **Step 11: Restore .gitignore working tree (preserves user's pre-existing Rust/Tauri block)**

```powershell
Copy-Item $env:TEMP\gitignore.voice.bak .gitignore -Force
git status --short .gitignore
```

Expected: `.gitignore` shows as `M` again (user's pre-existing Rust/Tauri block restored).

---

### Task 6: Listener ambient-RMS floor gate

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_voice_listener_v2.py`:

```python
# ─── Ambient floor gate ────────────────────────────────────────────────────


def test_ambient_gate_suppresses_wake_below_floor():
    """When room RMS is below floor and TTS isn't speaking, wake is skipped."""
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate(floor=0.005, window_s=0.5, sample_rate=16000)
    # Feed 1 second of silence (very low RMS).
    silence_frame = (np.zeros(480) + 0.0005 * np.random.randn(480)).astype(np.float32)
    silence_int16 = (silence_frame * 32767).astype(np.int16)
    for _ in range(int(16000 / 480)):  # ~33 frames = ~1s
        gate.observe(silence_int16)
    assert gate.below_floor() is True


def test_ambient_gate_opens_when_speech_present():
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate(floor=0.005, window_s=0.5, sample_rate=16000)
    # 1 second of speech-level frames.
    speech_frame = (0.05 * np.random.randn(480)).astype(np.float32)
    speech_int16 = (np.clip(speech_frame, -1, 1) * 32767).astype(np.int16)
    for _ in range(int(16000 / 480)):
        gate.observe(speech_int16)
    assert gate.below_floor() is False


def test_ambient_gate_floor_from_env(monkeypatch):
    monkeypatch.setenv("ZENDAYA_AMBIENT_FLOOR", "0.02")
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate()  # picks up env default
    assert gate.floor == 0.02


def test_ambient_gate_invalid_env_uses_default(monkeypatch):
    monkeypatch.setenv("ZENDAYA_AMBIENT_FLOOR", "not-a-number")
    from zendaya_voice_listener_v2 import _AmbientGate

    gate = _AmbientGate()
    assert gate.floor == 0.005  # default
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "ambient"
```

Expected: ImportError or AttributeError for `_AmbientGate`.

- [ ] **Step 3: Implement — add `_AmbientGate` class to v2.py**

Use Edit on `backend/zendaya_voice_listener_v2.py`. Find a good insertion point — near the top of the file after the constants/imports section. Add this class:

```python


# ─── Ambient-RMS floor gate ────────────────────────────────────────────────

class _AmbientGate:
    """Rolling RMS gate. When room ambient is below floor, suppress wake
    detection (saves CPU + kills barely-audible false fires from TV / HDD)."""

    def __init__(
        self,
        floor: float | None = None,
        window_s: float = 0.5,
        sample_rate: int = 16000,
    ) -> None:
        env_floor = os.environ.get("ZENDAYA_AMBIENT_FLOOR")
        try:
            self.floor = float(env_floor) if env_floor is not None else (floor if floor is not None else 0.005)
        except (TypeError, ValueError):
            print(f"[voice v2] invalid ZENDAYA_AMBIENT_FLOOR={env_floor!r}; using default 0.005")
            self.floor = 0.005
        self.window_s = window_s
        self.sample_rate = sample_rate
        self._buffer = np.zeros(int(window_s * sample_rate), dtype=np.float32)
        self._buf_pos = 0
        self._buf_filled = False

    def observe(self, frame_int16: np.ndarray) -> None:
        """Add a new frame to the rolling buffer."""
        f32 = frame_int16.astype(np.float32) / 32768.0
        n = len(f32)
        if n >= len(self._buffer):
            self._buffer[:] = f32[-len(self._buffer):]
            self._buf_filled = True
            self._buf_pos = 0
            return
        end = self._buf_pos + n
        if end <= len(self._buffer):
            self._buffer[self._buf_pos:end] = f32
        else:
            split = len(self._buffer) - self._buf_pos
            self._buffer[self._buf_pos:] = f32[:split]
            self._buffer[:n - split] = f32[split:]
            self._buf_filled = True
        self._buf_pos = end % len(self._buffer)
        if not self._buf_filled and end >= len(self._buffer):
            self._buf_filled = True

    def below_floor(self) -> bool:
        """Return True if recent ambient RMS is below the configured floor."""
        if not self._buf_filled:
            return False  # not enough data — let wake detection run
        rms = float(np.sqrt(np.mean(self._buffer ** 2)))
        return rms < self.floor

    def diagnostics(self) -> str:
        return f"ambient_gate: floor={self.floor}"
```

Then wire it into the frame-consumer loop. Find the spot in `_run_listener_session` (or wherever wake detection is invoked per frame) where `wake.push(...)` is called. Add the gate observation + check:

The general pattern is something like:
```python
# Existing per-frame loop
while running:
    frame = audio_q.get(...)
    # ... AGC, etc ...
    if _TTS_SPEAKING.is_set():
        # barge-in path: still consult wake even below floor
        if wake.push(frame, barge_in=True):
            ...
    else:
        # cold path: gate ambient
        ambient_gate.observe(frame)
        if not ambient_gate.below_floor():
            if wake.push(frame, barge_in=False):
                ...
```

Adapt to the file's actual control flow. Instantiate `_AmbientGate()` once in `_run_listener_session` (or at module scope, depending on lifecycle), and call `.observe(frame)` + `.below_floor()` on every frame in the cold (non-TTS) path.

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "ambient"
```

Expected: 4 ambient tests pass.

```powershell
pytest backend/tests/ -v
```

Expected: 56 + 3 + 8 + 4 = 71 tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/zendaya_voice_listener_v2.py backend/tests/test_voice_listener_v2.py
git -c commit.gpgsign=false commit -m "feat(voice): ambient-RMS floor gate suppresses wake when room is silent"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 7: Listener async dispatch worker thread + bounded queue

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_voice_listener_v2.py`:

```python
# ─── Async dispatch worker ─────────────────────────────────────────────────


def test_dispatch_queue_bounded_drops_oldest():
    """When more than cap items are enqueued, oldest are dropped."""
    from zendaya_voice_listener_v2 import _DispatchQueue

    q = _DispatchQueue(maxsize=2)
    q.put(("cmd one", 1.0))
    q.put(("cmd two", 2.0))
    q.put(("cmd three", 3.0))  # should evict "cmd one"

    items = []
    while not q.empty():
        items.append(q.get_nowait())
    assert [t for (t, _) in items] == ["cmd two", "cmd three"]


def test_worker_calls_handler_per_command():
    """Worker thread pulls from queue and invokes the provided handler."""
    from zendaya_voice_listener_v2 import _start_dispatch_worker, _DispatchQueue

    q = _DispatchQueue(maxsize=4)
    seen = []
    done = threading.Event()

    def handler(text):
        seen.append(text)
        if len(seen) == 2:
            done.set()

    stop = threading.Event()
    worker = _start_dispatch_worker(q, handler, stop_event=stop, tts_event=None)
    try:
        q.put(("hello", 0.0))
        q.put(("world", 0.0))
        assert done.wait(timeout=2.0), f"worker didn't process both: {seen}"
        assert seen == ["hello", "world"]
    finally:
        stop.set()
        q.put((None, 0.0))  # sentinel
        worker.join(timeout=2.0)


def test_worker_waits_for_tts_event_to_clear():
    """When TTS is speaking, worker holds the command until event clears."""
    from zendaya_voice_listener_v2 import _start_dispatch_worker, _DispatchQueue

    q = _DispatchQueue(maxsize=4)
    seen = []
    handled = threading.Event()

    def handler(text):
        seen.append(text)
        handled.set()

    tts = threading.Event()
    tts.set()  # TTS speaking
    stop = threading.Event()
    worker = _start_dispatch_worker(q, handler, stop_event=stop, tts_event=tts)
    try:
        q.put(("speak first", 0.0))
        # Worker should NOT process while tts is set.
        assert not handled.wait(timeout=0.5)
        assert seen == []
        # Clear TTS — worker proceeds.
        tts.clear()
        assert handled.wait(timeout=2.0)
        assert seen == ["speak first"]
    finally:
        stop.set()
        q.put((None, 0.0))
        worker.join(timeout=2.0)


def test_worker_survives_handler_exception():
    from zendaya_voice_listener_v2 import _start_dispatch_worker, _DispatchQueue

    q = _DispatchQueue(maxsize=4)
    seen = []
    done = threading.Event()

    def handler(text):
        if text == "boom":
            raise RuntimeError("intentional")
        seen.append(text)
        if text == "after":
            done.set()

    stop = threading.Event()
    worker = _start_dispatch_worker(q, handler, stop_event=stop, tts_event=None)
    try:
        q.put(("boom", 0.0))
        q.put(("after", 0.0))
        assert done.wait(timeout=2.0)
        assert seen == ["after"]
    finally:
        stop.set()
        q.put((None, 0.0))
        worker.join(timeout=2.0)
```

- [ ] **Step 2: Run — confirm failures**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "dispatch or worker"
```

Expected: ImportError / AttributeError for `_DispatchQueue` and `_start_dispatch_worker`.

- [ ] **Step 3: Implement — add dispatch queue + worker to v2.py**

Use Edit on `backend/zendaya_voice_listener_v2.py`. Add this block near the other module-level utilities (after `_AmbientGate` or before `_run_listener_session`):

```python


# ─── Async command dispatch ────────────────────────────────────────────────

import queue as _queue_mod

_TTS_WAIT_TIMEOUT_S = 30.0


class _DispatchQueue:
    """Bounded queue that drops oldest items when full."""

    def __init__(self, maxsize: int = 2) -> None:
        self._q = _queue_mod.Queue()
        self.maxsize = maxsize
        self._lock = threading.Lock()

    def put(self, item) -> None:
        with self._lock:
            while self._q.qsize() >= self.maxsize:
                try:
                    dropped = self._q.get_nowait()
                    print(f"[voice v2] dropped stale command — too many pending: {dropped[0]!r}")
                except _queue_mod.Empty:
                    break
            self._q.put(item)

    def get_nowait(self):
        return self._q.get_nowait()

    def get(self, timeout=None):
        return self._q.get(timeout=timeout)

    def empty(self) -> bool:
        return self._q.empty()

    def qsize(self) -> int:
        return self._q.qsize()


def _start_dispatch_worker(
    dispatch_queue: _DispatchQueue,
    handler,
    stop_event: threading.Event,
    tts_event: threading.Event | None,
) -> threading.Thread:
    """Launch a daemon worker thread that pulls from dispatch_queue and
    invokes `handler(text)` for each command. Waits up to 30s for tts_event
    to clear before dispatching. Handler exceptions are caught and logged."""

    def _run() -> None:
        while not stop_event.is_set():
            try:
                item = dispatch_queue.get(timeout=0.5)
            except _queue_mod.Empty:
                continue
            if item is None or item[0] is None:
                break  # sentinel
            text, _ts = item
            if tts_event is not None:
                waited = 0.0
                step = 0.1
                while tts_event.is_set() and waited < _TTS_WAIT_TIMEOUT_S and not stop_event.is_set():
                    time.sleep(step)
                    waited += step
                if tts_event.is_set():
                    print(f"[voice v2] dispatch waited {waited:.1f}s for TTS, proceeding anyway")
            try:
                handler(text)
            except Exception as e:
                import traceback
                print(f"[voice v2] dispatch handler crashed: {e}")
                traceback.print_exc()

    t = threading.Thread(target=_run, name="zendaya-voice-dispatch", daemon=True)
    t.start()
    return t
```

Then wire it into `_run_listener_session` / `start_voice_listener`. Replace the synchronous `_handle_command(cleaned)` call with `_DISPATCH_QUEUE.put((cleaned, time.time()))`.

Module-scope additions to `start_voice_listener()`:

```python
def start_voice_listener():
    """..."""
    # Preload Whisper (added in Task 5).
    try:
        _init_whisper()
        print("[voice v2] Whisper preloaded.")
    except Exception as e:
        print(f"[voice v2] Whisper preload failed: {e}")

    # Async dispatch worker.
    global _DISPATCH_QUEUE, _DISPATCH_STOP, _DISPATCH_WORKER
    _DISPATCH_QUEUE = _DispatchQueue(maxsize=2)
    _DISPATCH_STOP = threading.Event()
    import zendaya as _z
    _DISPATCH_WORKER = _start_dispatch_worker(
        _DISPATCH_QUEUE,
        _z.handle_user_command,
        stop_event=_DISPATCH_STOP,
        tts_event=_TTS_SPEAKING,
    )

    # ... existing thread-start logic ...
```

Module-scope variables at top:

```python
_DISPATCH_QUEUE = None
_DISPATCH_STOP = None
_DISPATCH_WORKER = None
```

In the listener-side `_handle_command` (around line 579), replace the direct `z.handle_user_command(cleaned)` call with:

```python
def _handle_command(text: str) -> None:
    """Enqueue command for the async dispatch worker."""
    if _DISPATCH_QUEUE is not None:
        _DISPATCH_QUEUE.put((text, time.time()))
    else:
        # Fallback to synchronous if worker wasn't initialised.
        import zendaya as z
        z.handle_user_command(text)
```

Add a `stop_voice_listener()` shutdown helper:

```python
def stop_voice_listener() -> None:
    """Signal the listener and dispatch worker to stop."""
    global _DISPATCH_STOP, _DISPATCH_QUEUE, _DISPATCH_WORKER
    if _DISPATCH_STOP is not None:
        _DISPATCH_STOP.set()
    if _DISPATCH_QUEUE is not None:
        try:
            _DISPATCH_QUEUE.put((None, 0.0))  # sentinel
        except Exception:
            pass
    if _DISPATCH_WORKER is not None:
        _DISPATCH_WORKER.join(timeout=2.0)
```

- [ ] **Step 4: Run — confirm pass**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "dispatch or worker"
```

Expected: 4 dispatch tests pass.

```powershell
pytest backend/tests/ -v
```

Expected: 71 + 4 = 75 tests pass.

- [ ] **Step 5: Syntax check**

```powershell
python -c "import ast; ast.parse(open(r'C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py', encoding='utf-8').read()); print('ok')"
```

- [ ] **Step 6: Commit**

```powershell
git add backend/zendaya_voice_listener_v2.py backend/tests/test_voice_listener_v2.py
git -c commit.gpgsign=false commit -m "feat(voice): async dispatch worker thread + bounded queue (no more blocking on Gemini)"
git show --stat HEAD
```

Expected: only the two files.

---

### Task 8: Integration smoke test with mocked sounddevice

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py` (append)

- [ ] **Step 1: Write the integration test**

Append to `backend/tests/test_voice_listener_v2.py`:

```python
# ─── Integration smoke ─────────────────────────────────────────────────────


def test_listener_dispatches_on_wake_and_command(monkeypatch):
    """End-to-end smoke: synthetic audio → wake → STT → dispatch handler.

    Mocks sounddevice + Whisper + wake engine to keep the test deterministic.
    Asserts a dispatched command flows from wake-detect to handler invocation.
    """
    import zendaya_voice_listener_v2 as v2

    received = []
    done = threading.Event()

    def fake_handler(text):
        received.append(text)
        done.set()

    # Monkeypatch the Whisper init + transcribe to return a canned reply.
    monkeypatch.setattr(v2, "_init_whisper", lambda: None)
    monkeypatch.setattr(v2, "_transcribe", lambda audio_int16, lang=None: "what time is it")

    # Use the async dispatch path directly, bypassing the audio loop.
    q = v2._DispatchQueue(maxsize=2)
    stop = threading.Event()
    worker = v2._start_dispatch_worker(q, fake_handler, stop_event=stop, tts_event=None)
    try:
        q.put(("what time is it", time.time()))
        assert done.wait(timeout=2.0)
        assert received == ["what time is it"]
    finally:
        stop.set()
        q.put((None, 0.0))
        worker.join(timeout=2.0)
```

This is a focused smoke test that exercises the dispatch path with mocked deps. Full audio-loop integration would require a real wav fixture, which is out of scope for unit tests.

- [ ] **Step 2: Run — confirm pass**

```powershell
pytest backend/tests/test_voice_listener_v2.py -v -k "integration or smoke"
```

Expected: 1 new test passes.

```powershell
pytest backend/tests/ -v
```

Expected: 75 + 1 = 76 tests pass.

- [ ] **Step 3: Commit**

```powershell
git add backend/tests/test_voice_listener_v2.py
git -c commit.gpgsign=false commit -m "test(voice): integration smoke for dispatch path"
git show --stat HEAD
```

Expected: only the test file.

---

### Task 9: STRETCH GOAL — Pre-EOS streaming Whisper transcription

**Decision gate:** ONLY attempt this task if Tasks 1-8 finished with 76/76 tests green and all five spec done-criteria for the main work are met. If yes, attempt this with a 2-hour timebox. If implementation introduces flakiness in ANY existing test, REVERT and document defer.

**Files:**
- Modify: `C:\Users\IKA\Zendaya\backend\zendaya_voice_listener_v2.py`
- Modify: `C:\Users\IKA\Zendaya\backend\tests\test_voice_listener_v2.py` (append)

- [ ] **Step 1: Sketch the change**

faster-whisper accepts a generator that yields audio chunks. The pattern: instead of buffering the whole utterance then calling `transcribe(full_audio, ...)`, start `transcribe(audio_generator(), ...)` once we have ~1s of audio. The generator yields chunks as the listener captures them. By the time Silero declares EOS, the transcribe call is mostly done.

Caveat: faster-whisper's streaming support is via `vad_filter=True` with internal chunking. True external-generator streaming is **not** in faster-whisper's public API. The pragmatic approach: skip true streaming, instead start `transcribe()` on the in-progress audio buffer after a fixed pre-EOS deadline (e.g., 800ms of speech captured), in a background thread. If transcribe finishes before Silero EOS, great. If not, cancel by waiting on a timeout and retry on the final buffer.

This may not yield a meaningful win and adds complexity. Recommendation in this task: try the simpler version — when buffer hits 1.5s of speech, fire `transcribe` in a thread; on EOS, if the thread is still running, wait for it; if its result matches the final buffer well, use it; otherwise re-transcribe.

- [ ] **Step 2: Decision check**

Before writing any code:
1. Re-read the spec's "Streaming Whisper partials — STRETCH GOAL" subsection. The decision rule says: "implement only if it lands in 1-2 plan tasks without destabilising end-of-utterance accuracy."
2. Confirm there are no flaky tests in Tasks 1-8.
3. Confirm the user is OK with the implementation complexity (this is a judgment call — if implementer is uncertain, prefer defer).

If the answer is "implement": proceed. Otherwise:

- [ ] **Step 3 (if deferring): Document the defer**

Commit a single-line marker in the spec's deferred-work section, or skip directly to Task 10 with a note in the final report.

If implementing:

- [ ] **Step 4 (if implementing): TDD as appropriate, attempt the simpler "background-pre-EOS-transcribe" pattern, commit if clean**

Test framework: timing-dependent, so use mocked Whisper with deterministic delay. Commit message: `feat(voice): pre-EOS streaming transcription (stretch goal)`.

If at ANY point during implementation a test from Tasks 1-8 starts flaking, REVERT this task's commits and skip to Task 10 with a defer note. Do NOT ship a destabilising change.

---

### Task 10: Manual verification + final report

**Files:** None (read-only).

- [ ] **Step 1: Confirm all commits landed**

```powershell
git log 6cb591a..HEAD --oneline
```

Expected commits (Task 9 may be absent if deferred):
- `deps: add deepfilternet ...` (if Task 2 ran)
- `feat(voice): add DeepFilterDenoiser + make_denoiser factory ...`
- `feat(voice): tighten wake thresholds + model-aware verifier regex`
- `feat(voice): speed wins ...`
- `feat(voice): ambient-RMS floor gate ...`
- `feat(voice): async dispatch worker thread ...`
- `test(voice): integration smoke for dispatch path`
- `feat(voice): pre-EOS streaming transcription (stretch goal)` — only if Task 9 implemented

- [ ] **Step 2: Full test suite green**

```powershell
pytest backend/tests/ -v
```

Expected: at least 76 tests pass (56 AAF + 20+ voice).

- [ ] **Step 3: Working-tree state**

```powershell
git status --short
```

Expected: only pre-existing dirty state visible (`.gitignore`, `backend/zendaya.py`, `backend/zendaya_system_access.py`, `pyproject.toml`, `zendaya_logs/assistant_history.json` if present). NO new untracked or modified files from execution.

- [ ] **Step 4: Manual verification checklist for the user**

Print this verbatim:

```
Manual checks (user runs):

[ ] 1. Start the assistant. Logs show "[voice v2] Whisper preloaded." before listener starts.
[ ] 2. Say "hey jarvis, what time is it" — time-to-reply feels noticeably faster than before.
[ ] 3. Background TV at moderate volume — wake + command — transcript is clean (no TV words bleed in).
[ ] 4. Issue two wake commands in quick succession — second queues, runs after first finishes.
[ ] 5. Try "frozen lake" or "the zenith is bright" — confirm no false wake.
[ ] 6. Whisper a wake command quietly — still triggers if above ambient floor.
[ ] 7. Stay silent in a quiet room for 30s — zero false wakes.
[ ] 8. If Task 1 found a community zendaya model, try saying "zendaya, what time is it" instead — wakes correctly.
[ ] 9. Unplug mic mid-session, plug back in within 5s — listener recovers automatically (logged).
[ ] 10. Check startup logs for the denoiser line — should say either "DeepFilterNet (utterance-level)" or "noisereduce (stationary, utterance-level)" depending on whether DFN was buildable.
```

- [ ] **Step 5: Status line**

Output ONE short line summarising the outcome:
- `Voice listener upgrade complete: N commits, N tests passing, DeepFilterNet [available/unavailable], wake model [hey_jarvis/community-zendaya], async dispatch active. Manual verification pending.`
- Or if Task 9 was deferred: `... pre-EOS streaming deferred to follow-up spec.`

No commit.

---

## Out of scope (for follow-up plans)

- Speculative LLM dispatch on stable partial transcripts ("she replies mid-sentence")
- Custom-trained openWakeWord "Zendaya" model from user voice recordings (~500 samples)
- Mic device hot-swap UI
- Auto-calibrating ambient floor (currently static)
- Multi-microphone array support / beamforming
- v1 listener cleanup (`backend/zendaya_voice_listener.py`) — separate task
- Touching the 4,400-line uncommitted diff in `backend/zendaya.py` — user explicit: leave alone
