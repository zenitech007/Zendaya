"""Simple automatic gain control.

Targets -3 dBFS peak with a slow attack and slower release so Whisper sees
audio in a consistent loudness band — both whispered and shouted speech come
out near the same level by the time it reaches STT.
"""
from __future__ import annotations

import numpy as np


TARGET_PEAK = 0.70           # ~-3 dBFS in float32 (-1..1)
MIN_GAIN = 0.5
MAX_GAIN = 8.0
ATTACK = 0.08                # how fast gain drops on loud peaks
RELEASE = 0.005              # how fast gain creeps up on quiet audio
NOISE_FLOOR_PEAK = 0.008     # don't amplify pure silence (would boost hiss)


class AGC:
    def __init__(self) -> None:
        self._gain = 1.0

    def process(self, frame_int16: np.ndarray) -> np.ndarray:
        if frame_int16.size == 0:
            return frame_int16
        f32 = frame_int16.astype(np.float32) / 32768.0
        peak = float(np.max(np.abs(f32)))
        if peak < NOISE_FLOOR_PEAK:
            target_gain = self._gain  # hold
        else:
            target_gain = TARGET_PEAK / max(peak, 1e-4)
            target_gain = float(np.clip(target_gain, MIN_GAIN, MAX_GAIN))
        coef = ATTACK if target_gain < self._gain else RELEASE
        self._gain += coef * (target_gain - self._gain)
        out = np.clip(f32 * self._gain, -1.0, 1.0)
        return (out * 32767.0).astype(np.int16)

    def reset(self) -> None:
        self._gain = 1.0
