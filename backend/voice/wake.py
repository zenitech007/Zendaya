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


class WakeEngine:
    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.6,
        barge_threshold: float = 0.72,
    ) -> None:
        self.model_name = os.environ.get("ZENDAYA_WAKE_MODEL", model_name)
        self.threshold = float(os.environ.get("ZENDAYA_WAKE_THRESHOLD", str(threshold)))
        self.barge_threshold = float(barge_threshold)
        self._model = None
        self._accum = np.zeros(0, dtype=np.int16)
        self._scores: deque = deque(maxlen=SMOOTH_WINDOW)
        self._last_fire_ts = 0.0
        self.err = ""
        self.last_score = 0.0
        if not _OWW_AVAILABLE:
            self.err = f"openwakeword not installed: {_OWW_ERR}"
            return
        try:
            self._model = _OWWModel(
                wakeword_models=[self.model_name],
                inference_framework="onnx",
            )
        except Exception as e:
            self.err = f"openwakeword init failed: {e}"
            self._model = None

    @property
    def ready(self) -> bool:
        return self._model is not None

    def _predict(self, chunk_int16: np.ndarray) -> float:
        if self._model is None:
            return 0.0
        try:
            scores = self._model.predict(chunk_int16)
        except Exception:
            return 0.0
        if not scores:
            return 0.0
        return float(max(scores.values()))

    def push(self, frame_int16: np.ndarray, barge_in: bool = False) -> bool:
        """Push a frame; return True iff (smoothed) wake fires above threshold.

        barge_in=True uses the stricter `barge_threshold` (for use while TTS
        is playing, where TTS audio can bleed into the mic).
        """
        if self._model is None:
            return False
        self._accum = np.concatenate([self._accum, frame_int16])
        fired = False
        while self._accum.size >= WAKE_CHUNK_SAMPLES:
            chunk = self._accum[:WAKE_CHUNK_SAMPLES]
            self._accum = self._accum[WAKE_CHUNK_SAMPLES:]
            score = self._predict(chunk)
            self.last_score = score
            self._scores.append(score)
            smoothed = sum(self._scores) / len(self._scores)
            thresh = self.barge_threshold if barge_in else self.threshold
            if (
                smoothed >= thresh
                and time.time() - self._last_fire_ts > COOLDOWN_S
            ):
                self._last_fire_ts = time.time()
                self._scores.clear()
                fired = True
        return fired

    def reset(self) -> None:
        self._accum = np.zeros(0, dtype=np.int16)
        self._scores.clear()

    def diagnostics(self) -> str:
        if self._model is not None:
            return (
                f"wake: openWakeWord ready — model={self.model_name!r} "
                f"thr={self.threshold} barge_thr={self.barge_threshold}"
            )
        return f"wake: OFF — {self.err}"
