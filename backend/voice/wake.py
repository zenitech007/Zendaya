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


class WakeEngine:
    def __init__(
        self,
        model_name: str = "hey_jarvis",
        threshold: float = 0.5,
        barge_threshold: float = 0.7,
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
