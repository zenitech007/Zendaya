# Custom "Zendaya" / "Zen" Wake Words — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `hey_jarvis` wake word with custom **"Zendaya"** (primary) and **"Zen"** (tamed) openWakeWord models, free and offline.

**Architecture:** Reuse the existing two-stage wake system. Stage 1 = openWakeWord; upgrade `WakeEngine` to load **multiple custom `.onnx` models by path** with **per-model thresholds** and **fired-model tracking**, falling back to `hey_jarvis` until the trained models are present. Stage 2 = the Whisper-transcript verifier, extended with a careful bare-`zen` token. The active listener (`voice/listener_v2.py`) gets two small edits. The trained `.onnx` files come from a free Colab GPU run (done by the user) and drop into `backend/voice/models/`.

**Tech Stack:** Python 3.14, openWakeWord (ONNX), numpy, pytest. (Coqui TTS only for the optional mic-free smoke test.)

**Repo conventions (read first):**
- Run from repo root `C:\Users\IKA\Zendaya`. Shell: **PowerShell 5.1** — use `;` not `&&`; venv python is `C:\Users\IKA\Zendaya\venv\Scripts\python.exe`.
- Backend uses absolute package imports with `backend/` on `sys.path` (`backend/tests/conftest.py` adds it). Tests: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/<file> -v`.
- Git: NEVER `git add -A`/`git add .`. Stage only named files. Commit `git -c commit.gpgsign=false commit`, end messages with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. Leave the unrelated `zendaya_logs/` runtime files alone.
- The active wake code lives in `backend/voice/wake.py` (the `WakeEngine` + verifier) and is used by `backend/voice/listener_v2.py` (lines ~606, ~712). `backend/voice/listener.py` is the dormant v1 listener (not imported by `zendaya.py`) — leave it unchanged.

**Module API created/changed (reference):**
```text
# backend/voice/wake.py
VERIFY_RE_ZEN = re.compile(r"\bzen\b", IGNORECASE)
verifier_passes_for_model(model_name, transcript) -> bool   # now handles zendaya | zen | jarvis
_MODELS_DIR, _BUNDLED=["zendaya","zen"], _DEFAULT_THRESHOLDS
_model_key(entry) -> str          # path->basename-no-ext, builtin->itself
_resolve_model_entries() -> list[str]   # env | bundled-present | ["hey_jarvis"] fallback
class WakeEngine(models=None, threshold=None, barge_threshold=0.72):
    .model_keys: list[str]   .thresholds: dict   .last_fired_model: str|None   .last_score: float
    .push(frame_int16, barge_in=False) -> bool   # sets last_fired_model on fire
    .ready / .reset() / .diagnostics()
```

---

## File Structure
- **Modify:** `backend/voice/wake.py` — verifier (add `zen`) + `WakeEngine` (multi-model, per-model thresholds, `last_fired_model`, fallback).
- **Modify:** `backend/voice/listener_v2.py` — default to custom models (line ~606); verify against the fired model (line ~712).
- **Create:** `backend/voice/models/README.md` — placeholder so the model dir exists in git; says where to drop `zendaya.onnx`/`zen.onnx`.
- **Create:** `backend/tests/test_wake.py` — verifier + engine unit tests; one mic-free `@slow` smoke test.
- **Create:** `docs/superpowers/guides/wake-training-colab.md` — the user's Colab training guide.
- **Modify:** `README.md`, `CLAUDE.md` — wake-word notes.

---

## Task 1: Verifier — add a careful bare-"zen" token

**Files:**
- Modify: `backend/voice/wake.py`
- Test: `backend/tests/test_wake.py`

- [ ] **Step 1: Write the failing tests** — create `backend/tests/test_wake.py`:
```python
"""Wake-word verifier + engine tests (openWakeWord mocked; no real ONNX)."""
from __future__ import annotations

import numpy as np
import pytest

from voice import wake


@pytest.mark.parametrize("transcript,ok", [
    ("zendaya", True), ("Zendaya, what's the weather", True),
    ("zen daya", True), ("sendaya", True),
    ("zen", False), ("hello there", False),
])
def test_verifier_zendaya_model(transcript, ok):
    assert wake.verifier_passes_for_model("zendaya", transcript) is ok


@pytest.mark.parametrize("transcript,ok", [
    ("zen", True), ("hey zen", True), ("Zen, play music", True),
    ("zenith", False), ("frozen yogurt", False), ("present", False),
    ("zendaya", False),
])
def test_verifier_zen_model(transcript, ok):
    assert wake.verifier_passes_for_model("zen", transcript) is ok


def test_verifier_empty_transcript_false():
    assert wake.verifier_passes_for_model("zendaya", "") is False


def test_verifier_jarvis_still_accepts_jarvis_or_zendaya():
    assert wake.verifier_passes_for_model("hey_jarvis", "jarvis") is True
    assert wake.verifier_passes_for_model("hey_jarvis", "zendaya") is True
```

- [ ] **Step 2: Run to verify failure**

Run: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -k verifier -v`
Expected: FAIL — `test_verifier_zen_model` fails (today the "zen" branch isn't routed; `verifier_passes_for_model("zen", "zen")` currently runs the hey_jarvis regex which doesn't match "zen").

- [ ] **Step 3: Implement** — in `backend/voice/wake.py`, add `VERIFY_RE_ZEN` after `VERIFY_RE_ZENDAYA` and replace `verifier_passes_for_model`:
```python
VERIFY_RE_ZEN = re.compile(r"\bzen\b", re.IGNORECASE)
```
Replace the existing `verifier_passes_for_model` body with:
```python
def verifier_passes_for_model(model_name: str, transcript: str) -> bool:
    """Model-aware Stage-2 verifier. Returns True if the pre-roll transcript
    contains the wake word the fired model listens for.

    Order matters: "zen" is a substring of "zendaya", so check zendaya first.
    `\\bzen\\b` accepts a bare "zen" but rejects "zenith"/"frozen"/"present".
    """
    if not transcript:
        return False
    name = (model_name or "").lower()
    if "zendaya" in name:
        return VERIFY_RE_ZENDAYA.search(transcript) is not None
    if "zen" in name:
        return VERIFY_RE_ZEN.search(transcript) is not None
    return VERIFY_RE_HEY_JARVIS.search(transcript) is not None
```

- [ ] **Step 4: Run to verify pass**

Run: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -k verifier -v`
Expected: all verifier tests pass.

- [ ] **Step 5: Commit**
```powershell
git add backend/voice/wake.py backend/tests/test_wake.py
git -c commit.gpgsign=false commit -m "feat(wake): verifier accepts a careful bare 'zen' token" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `WakeEngine` — multi-model load, per-model thresholds, fired-model tracking

**Files:**
- Modify: `backend/voice/wake.py`
- Test: `backend/tests/test_wake.py`

- [ ] **Step 1: Add the failing tests** — append to `backend/tests/test_wake.py`:
```python
class _FakeOWW:
    """Stand-in for openwakeword Model: returns preset scores per predict()."""
    def __init__(self, wakeword_models=None, inference_framework=None):
        self.wakeword_models = wakeword_models
        self._queue = []
    def set_scores(self, *dicts):
        self._queue = list(dicts)
    def predict(self, chunk):
        return self._queue.pop(0) if self._queue else {}


def _engine_with_fake(monkeypatch, models, scores):
    monkeypatch.setattr(wake, "_OWW_AVAILABLE", True)
    fake = _FakeOWW()
    monkeypatch.setattr(wake, "_OWWModel", lambda **kw: fake)
    eng = wake.WakeEngine(models=models)
    fake.set_scores(*scores)
    return eng, fake


def test_model_key_from_path_and_builtin():
    assert wake._model_key(r"C:\x\zendaya.onnx") == "zendaya"
    assert wake._model_key("voice/models/zen.onnx") == "zen"
    assert wake._model_key("hey_jarvis") == "hey_jarvis"


def test_resolve_env_comma_split(monkeypatch):
    monkeypatch.setenv("ZENDAYA_WAKE_MODEL", "a/zendaya.onnx, a/zen.onnx")
    assert wake._resolve_model_entries() == ["a/zendaya.onnx", "a/zen.onnx"]


def test_resolve_fallback_to_hey_jarvis(monkeypatch):
    monkeypatch.delenv("ZENDAYA_WAKE_MODEL", raising=False)
    monkeypatch.setattr(wake.os.path, "isfile", lambda p: False)
    assert wake._resolve_model_entries() == ["hey_jarvis"]


def test_per_model_default_thresholds(monkeypatch):
    monkeypatch.delenv("ZENDAYA_WAKE_THRESHOLD", raising=False)
    eng, _ = _engine_with_fake(monkeypatch, ["m/zendaya.onnx", "m/zen.onnx"], [])
    assert eng.model_keys == ["zendaya", "zen"]
    assert eng.thresholds["zendaya"] == 0.5
    assert eng.thresholds["zen"] == 0.7


def test_push_fires_and_records_model(monkeypatch):
    eng, fake = _engine_with_fake(monkeypatch, ["m/zendaya.onnx", "m/zen.onnx"],
                                  [{"zendaya": 0.9, "zen": 0.0}] * wake.SMOOTH_WINDOW)
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES * wake.SMOOTH_WINDOW, dtype=np.int16)
    assert eng.push(frame) is True
    assert eng.last_fired_model == "zendaya"
    assert eng.last_score >= 0.5


def test_push_respects_zen_higher_threshold(monkeypatch):
    # zen smoothed 0.6 is below zen's 0.7 threshold -> no fire
    eng, fake = _engine_with_fake(monkeypatch, ["m/zen.onnx"],
                                  [{"zen": 0.6}] * wake.SMOOTH_WINDOW)
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES * wake.SMOOTH_WINDOW, dtype=np.int16)
    assert eng.push(frame) is False
    assert eng.last_fired_model is None
```

- [ ] **Step 2: Run to verify failure**

Run: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -k "model_key or resolve or threshold or push" -v`
Expected: FAIL — `_model_key`, `_resolve_model_entries`, `WakeEngine(models=...)`, `last_fired_model` don't exist yet.

- [ ] **Step 3: Implement** — in `backend/voice/wake.py`:

(a) After the constants block (near `COOLDOWN_S`), add:
```python
_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_BUNDLED = ("zendaya", "zen")                       # expected custom model basenames
_DEFAULT_THRESHOLDS = {"zendaya": 0.5, "zen": 0.7, "hey_jarvis": 0.5}


def _model_key(entry: str) -> str:
    """openWakeWord keys a model by its file basename (no ext); builtins by name."""
    if entry.endswith(".onnx") or "/" in entry or "\\" in entry:
        return os.path.splitext(os.path.basename(entry))[0]
    return entry


def _resolve_model_entries() -> list:
    """Resolve the Stage-1 model list: ZENDAYA_WAKE_MODEL (comma-separated paths or
    builtin names) → bundled custom models present on disk → ['hey_jarvis'] fallback
    (so wake still works before the custom models are trained)."""
    env = os.environ.get("ZENDAYA_WAKE_MODEL", "").strip()
    if env:
        return [e.strip() for e in env.split(",") if e.strip()]
    bundled = [os.path.join(_MODELS_DIR, f"{n}.onnx") for n in _BUNDLED]
    present = [p for p in bundled if os.path.isfile(p)]
    return present if present else ["hey_jarvis"]
```

(b) Replace the whole `class WakeEngine` with:
```python
class WakeEngine:
    def __init__(self, models=None, threshold=None, barge_threshold: float = 0.72) -> None:
        entries = _resolve_model_entries() if models is None else models
        if isinstance(entries, str):
            entries = [entries]
        self.entries = list(entries)
        self.model_keys = [_model_key(e) for e in self.entries]
        self.model_name = ",".join(self.model_keys)  # back-compat / diagnostics
        self.barge_threshold = float(barge_threshold)
        env_thr = os.environ.get("ZENDAYA_WAKE_THRESHOLD")
        self.thresholds = {}
        for k in self.model_keys:
            if threshold is not None:
                self.thresholds[k] = float(threshold)
            elif env_thr:
                self.thresholds[k] = float(env_thr)
            else:
                self.thresholds[k] = _DEFAULT_THRESHOLDS.get(k, 0.5)
        self._scores = {k: deque(maxlen=SMOOTH_WINDOW) for k in self.model_keys}
        self._accum = np.zeros(0, dtype=np.int16)
        self._last_fire_ts = 0.0
        self.last_fired_model = None
        self.last_score = 0.0
        self.err = ""
        self._model = None
        if not _OWW_AVAILABLE:
            self.err = f"openwakeword not installed: {_OWW_ERR}"
            return
        try:
            self._model = _OWWModel(wakeword_models=list(self.entries),
                                    inference_framework="onnx")
        except Exception as e:
            self.err = f"openwakeword init failed: {e}"
            self._model = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def _predict(self, chunk_int16: np.ndarray) -> dict:
        if self._model is None:
            return {}
        try:
            return dict(self._model.predict(chunk_int16))
        except Exception:
            return {}

    def push(self, frame_int16: np.ndarray, barge_in: bool = False) -> bool:
        """Push a frame; return True iff any model's smoothed score crosses its
        threshold (records `last_fired_model`/`last_score`)."""
        if self._model is None:
            return False
        self._accum = np.concatenate([self._accum, frame_int16])
        fired = False
        while self._accum.size >= WAKE_CHUNK_SAMPLES:
            chunk = self._accum[:WAKE_CHUNK_SAMPLES]
            self._accum = self._accum[WAKE_CHUNK_SAMPLES:]
            scores = self._predict(chunk)
            for key in self.model_keys:
                dq = self._scores[key]
                dq.append(float(scores.get(key, 0.0)))
                smoothed = sum(dq) / len(dq)
                thresh = self.barge_threshold if barge_in else self.thresholds.get(key, 0.5)
                if smoothed >= thresh and time.time() - self._last_fire_ts > COOLDOWN_S:
                    self._last_fire_ts = time.time()
                    self.last_fired_model = key
                    self.last_score = smoothed
                    for d in self._scores.values():
                        d.clear()
                    fired = True
                    break
            if fired:
                break
        return fired

    def reset(self) -> None:
        self._accum = np.zeros(0, dtype=np.int16)
        for d in self._scores.values():
            d.clear()

    def diagnostics(self) -> str:
        if self._model is not None:
            return (f"wake: openWakeWord ready — models={self.model_keys} "
                    f"thresholds={self.thresholds} barge_thr={self.barge_threshold}")
        return f"wake: OFF — {self.err}"
```

- [ ] **Step 4: Run to verify pass**

Run: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -v`
Expected: all tests pass (verifier + engine).

- [ ] **Step 5: Commit**
```powershell
git add backend/voice/wake.py backend/tests/test_wake.py
git -c commit.gpgsign=false commit -m "feat(wake): multi-model WakeEngine with per-model thresholds + fired-model tracking" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Wire the active listener (`listener_v2`) to the new engine

**Files:**
- Modify: `backend/voice/listener_v2.py` (lines ~606 and ~712)

No automated test (importing the listener pulls audio/runtime deps); verify by syntax-check + the existing suite + a diagnostics print.

- [ ] **Step 1: Default to the custom models** — change line ~606 from:
```python
    _WAKE = WakeEngine(model_name="hey_jarvis", threshold=0.5, barge_threshold=0.72)
```
to:
```python
    _WAKE = WakeEngine(barge_threshold=0.72)  # default models: zendaya.onnx + zen.onnx (fallback hey_jarvis)
```

- [ ] **Step 2: Verify against the model that actually fired** — change line ~712 from:
```python
                        model_name = _WAKE.model_name if _WAKE is not None else "hey_jarvis"
```
to:
```python
                        model_name = (_WAKE.last_fired_model if _WAKE is not None else None) or "zendaya"
```

- [ ] **Step 3: Syntax-check + run the suite (no regressions)**

Run:
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import ast; ast.parse(open(r'backend/voice/listener_v2.py', encoding='utf-8').read()); print('OK')"
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests -q -m "not slow"
```
Expected: `OK`, then the full suite passes (incl. `test_voice_listener_v2.py` and the new `test_wake.py`).

- [ ] **Step 4: Commit**
```powershell
git add backend/voice/listener_v2.py
git -c commit.gpgsign=false commit -m "feat(wake): listener_v2 uses custom wake models + per-fire verifier" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Model directory placeholder

**Files:**
- Create: `backend/voice/models/README.md`

- [ ] **Step 1: Create the placeholder** — `backend/voice/models/README.md`:
```markdown
# Wake-word models

Drop the trained openWakeWord models here:

- `zendaya.onnx`  — primary wake word
- `zen.onnx`      — secondary wake word

`WakeEngine` loads these automatically (see `_resolve_model_entries` in
`../wake.py`). If they're absent it falls back to the built-in `hey_jarvis`
model, so the assistant still wakes during the interim.

Train them with the free Colab guide:
`docs/superpowers/guides/wake-training-colab.md`. Override the path(s) at runtime
with `ZENDAYA_WAKE_MODEL` (comma-separated) and tune with `ZENDAYA_WAKE_THRESHOLD`.
```

- [ ] **Step 2: Verify the fallback works without models present**

Run (from repo root):
```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'backend'); from voice import wake; print(wake._resolve_model_entries())"
```
Expected: `['hey_jarvis']` (no `.onnx` present yet → graceful fallback).

- [ ] **Step 3: Commit**
```powershell
git add backend/voice/models/README.md
git -c commit.gpgsign=false commit -m "chore(wake): add backend/voice/models/ placeholder + fallback" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Mic-free smoke test (runs after the model is trained)

**Files:**
- Modify: `backend/tests/test_wake.py`

- [ ] **Step 1: Add the self-skipping slow test** — append to `backend/tests/test_wake.py`:
```python
import os


@pytest.mark.slow
def test_zendaya_model_fires_on_synth_clip():
    """Mic-free end-to-end check: synthesize 'Zendaya' with Coqui, resample to
    16 kHz, feed it through the real WakeEngine loaded with zendaya.onnx, and
    assert it fires. Self-skips until the trained model is present."""
    model = os.path.join(wake._MODELS_DIR, "zendaya.onnx")
    if not os.path.isfile(model):
        pytest.skip("zendaya.onnx not trained/present yet")
    try:
        from voice import offline_tts
        pcm = offline_tts.synth_to_pcm("Zendaya", target_sr=16000)
    except Exception as e:
        pytest.skip(f"offline TTS unavailable: {e}")
    if not pcm:
        pytest.skip("offline TTS produced no audio")
    samples = np.frombuffer(pcm, dtype="<i2")
    eng = wake.WakeEngine(models=[model])
    if not eng.ready:
        pytest.skip(f"wake engine not ready: {eng.err}")
    fired = False
    for i in range(0, len(samples), wake.WAKE_CHUNK_SAMPLES):
        if eng.push(samples[i:i + wake.WAKE_CHUNK_SAMPLES]):
            fired = True
            break
    assert fired, "trained zendaya.onnx did not fire on a synthesized 'Zendaya' clip"
    assert eng.last_fired_model == "zendaya"
```

- [ ] **Step 2: Run it (self-skips until the model exists)**

Run: `& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -m slow -v`
Expected (now): `1 skipped` ("zendaya.onnx not trained/present yet"). After the user trains + drops the model in, it should pass.

- [ ] **Step 3: Commit**
```powershell
git add backend/tests/test_wake.py
git -c commit.gpgsign=false commit -m "test(wake): mic-free smoke test for the trained zendaya model" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: Colab training guide (the user's one step)

**Files:**
- Create: `docs/superpowers/guides/wake-training-colab.md`

- [ ] **Step 1: Write the guide** — `docs/superpowers/guides/wake-training-colab.md`:
````markdown
# Train your "Zendaya" / "Zen" wake words (free, ~30–60 min)

You don't record your voice and you don't read a script — a free Google Colab
notebook generates thousands of synthetic "Zendaya" clips with AI voices and
trains a small detector on Google's GPU. You just set the word and click Run.

## Steps (do this once per word)

1. Open openWakeWord's automatic training notebook:
   <https://github.com/dscripka/openWakeWord> → README → **"Automatic Model Training (Colab)"**
   (notebook: `notebooks/automatic_model_training.ipynb`). Open it in Colab.
2. In Colab: **Runtime → Change runtime type → GPU → Save**.
3. Find the **`target_word`** cell and set it to:  `Zendaya`
   - Optional quality knobs (recommended): bump `number_of_examples` higher and
     `number_of_training_steps` (more = better, slower).
4. **Runtime → Run all.** It generates positives, downloads negatives, trains,
   and exports an ONNX model. Wait for it to finish (~30–60 min).
5. Download the resulting **`.onnx`** file (Colab's file browser, left panel).
   Rename it to exactly **`zendaya.onnx`**.
6. Repeat steps 3–5 with `target_word = Zen`. **For "Zen" raise the example
   count / steps** (short words need more data) and rename the output to
   **`zen.onnx`**.

## Install the models

Copy both files into:

```
C:\Users\IKA\Zendaya\backend\voice\models\
```

That's it — `WakeEngine` picks them up automatically (no code change). Verify:

```powershell
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -c "import sys; sys.path.insert(0,'backend'); from voice import wake; print(wake._resolve_model_entries())"
```

You should see the two `.onnx` paths. Then run the smoke test:

```powershell
$env:PATH = "C:\Program Files\eSpeak NG;$env:PATH"
& "C:\Users\IKA\Zendaya\venv\Scripts\python.exe" -m pytest backend/tests/test_wake.py -m slow -v
```

Expected: it synthesizes "Zendaya" and confirms the model fires. Finally, start
Zendaya and say **"Zendaya"** once to confirm a live wake.

## Tuning (if needed)

- Too many false wakes (especially "Zen"): raise its threshold —
  `setx ZENDAYA_WAKE_THRESHOLD 0.7` (or edit `_DEFAULT_THRESHOLDS` in `wake.py`).
- Doesn't wake reliably: lower the threshold, or retrain with more examples.
- Use a different model file/location: set `ZENDAYA_WAKE_MODEL` to a
  comma-separated list of `.onnx` paths.
````

- [ ] **Step 2: Commit**
```powershell
git add docs/superpowers/guides/wake-training-colab.md
git -c commit.gpgsign=false commit -m "docs(wake): Colab training guide for Zendaya/Zen wake words" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: Update README + CLAUDE.md wake notes

**Files:**
- Modify: `README.md`, `CLAUDE.md`

- [ ] **Step 1: README** — in the Features list, change the wake bullet from the `hey_jarvis`/openWakeWord wording to:
```markdown
- **Voice in** — custom **"Zendaya"/"Zen"** wake words (openWakeWord, trained via the
  free Colab guide in `docs/superpowers/guides/wake-training-colab.md`) → VAD (Silero) +
  denoise → Whisper STT. Falls back to `hey_jarvis` until the models are trained.
```

- [ ] **Step 2: CLAUDE.md** — under the structure notes, add one line:
```markdown
Wake words are custom openWakeWord models (`zendaya.onnx`/`zen.onnx` in
`backend/voice/models/`, trained via `docs/superpowers/guides/wake-training-colab.md`);
the engine falls back to `hey_jarvis` if they're absent. Tune via `ZENDAYA_WAKE_MODEL` /
`ZENDAYA_WAKE_THRESHOLD`.
```

- [ ] **Step 3: Commit**
```powershell
git add README.md CLAUDE.md
git -c commit.gpgsign=false commit -m "docs(wake): note custom Zendaya/Zen wake words in README + CLAUDE" -m "Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Done when
- `backend/tests/test_wake.py` passes (verifier + engine); the slow smoke test **skips** cleanly until the model exists.
- Full `backend/tests` suite stays green; `listener_v2.py` parses and prints the new wake diagnostics.
- With no `.onnx` present, `_resolve_model_entries()` returns `['hey_jarvis']` (assistant still wakes).
- The user can follow the Colab guide, drop `zendaya.onnx`/`zen.onnx` into `backend/voice/models/`, watch the smoke test pass, and wake on "Zendaya" live.

## Handoff to the user (after the code lands)
1. Follow `docs/superpowers/guides/wake-training-colab.md` → produce `zendaya.onnx` + `zen.onnx`.
2. Drop both into `backend/voice/models/`.
3. Run the slow smoke test (should pass), then say "Zendaya" to Zendaya.
