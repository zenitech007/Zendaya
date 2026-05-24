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
from __future__ import annotations

import numpy as np

try:
    import noisereduce as nr  # type: ignore
    _NR_AVAILABLE = True
    _NR_ERR = ""
except Exception as _e:
    _NR_AVAILABLE = False
    _NR_ERR = str(_e)


SR = 16000


class Denoiser:
    def __init__(self, enabled: bool = True) -> None:
        self.enabled = bool(enabled) and _NR_AVAILABLE
        self.err = "" if _NR_AVAILABLE else f"noisereduce missing: {_NR_ERR}"

    @property
    def ready(self) -> bool:
        return self.enabled

    def process(self, frame_int16: np.ndarray) -> np.ndarray:
        """Per-frame passthrough — denoising happens on the full utterance."""
        return frame_int16

    def process_utterance(self, audio_int16: np.ndarray) -> np.ndarray:
        """Spectral-subtraction denoise a full utterance just before STT.

        Uses stationary mode so the noise profile is estimated from quiet
        segments of the same clip — works well for club/cafe ambient noise
        that doesn't fluctuate too fast.
        """
        if not self.enabled or audio_int16.size == 0:
            return audio_int16
        try:
            f32 = audio_int16.astype(np.float32) / 32768.0
            cleaned = nr.reduce_noise(
                y=f32,
                sr=SR,
                stationary=True,
                prop_decrease=0.85,
            )
            cleaned = np.clip(cleaned, -1.0, 1.0)
            return (cleaned * 32767.0).astype(np.int16)
        except Exception:
            return audio_int16

    def diagnostics(self) -> str:
        if self.enabled:
            return "denoise: noisereduce (stationary, utterance-level)"
        return f"denoise: OFF — {self.err}"
