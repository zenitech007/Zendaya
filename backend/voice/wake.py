"""openWakeWord wrapper with smoothing, cooldown, and Stage-2 verifier hook.

The raw single-frame openWakeWord score is jumpy; we apply a short moving
average to suppress single-frame false fires while keeping latency low.

Stage 2 (Whisper verifier) is run by the caller — this module just provides
the regex that decides whether a 1.2 s pre-roll transcript looks like the
user actually said the wake word.
"""
from __future__ import annotations

import os
import re
import time
from collections import deque

import numpy as np

try:
    from openwakeword.model import Model as _OWWModel  # type: ignore
    _OWW_AVAILABLE = True
    _OWW_ERR = ""
except Exception as _e:
    _OWW_AVAILABLE = False
    _OWW_ERR = str(_e)


WAKE_CHUNK_SAMPLES = 1280              # 80 ms at 16 kHz — openWakeWord native
SMOOTH_WINDOW = 5                      # ~400 ms of scores
COOLDOWN_S = 1.5                       # don't fire twice within this window

_MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
_BUNDLED = ("hey_zendaya", "zendaya", "zen")        # expected custom model basenames
_DEFAULT_THRESHOLDS = {"hey_zendaya": 0.5, "zendaya": 0.5, "zen": 0.7, "hey_jarvis": 0.5}


def _model_key(entry: str) -> str:
    """openWakeWord keys a model by its file basename (no ext); builtins by name."""
    # Only `.onnx` file paths and builtin model names are supported here.
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
VERIFY_RE_ZEN = re.compile(r"\bzen\b", re.IGNORECASE)
VERIFY_RE = VERIFY_RE_HEY_JARVIS  # kept for back-compat with any external import

VERIFIER_SKIP_THRESHOLD = 0.85  # Wakes scoring >= this skip Stage-2 verifier.


def verifier_passes(transcript: str) -> bool:
    """Back-compat: assume hey_jarvis model (which also accepts zendaya)."""
    return verifier_passes_for_model("hey_jarvis", transcript)


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
        threshold. Records `last_fired_model` and `last_score` (the *smoothed*
        score at fire time, not a raw single-frame score)."""
        if self._model is None:
            return False
        self._accum = np.concatenate([self._accum, frame_int16])
        fired = False
        while self._accum.size >= WAKE_CHUNK_SAMPLES:
            chunk = self._accum[:WAKE_CHUNK_SAMPLES]
            self._accum = self._accum[WAKE_CHUNK_SAMPLES:]
            scores = self._predict(chunk)
            # Append this chunk's score for EVERY model before evaluating fires,
            # so an earlier model firing (which clears the deques) can't rob a
            # later model of this chunk's sample (order-independent smoothing).
            for key in self.model_keys:
                self._scores[key].append(float(scores.get(key, 0.0)))
            for key in self.model_keys:
                dq = self._scores[key]
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
