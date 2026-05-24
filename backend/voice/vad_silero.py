"""Silero VAD wrapper presenting a webrtcvad-compatible 30 ms frame API.

Silero natively chunks audio in 512-sample blocks at 16 kHz (32 ms). We accept
30 ms (480 samples) frames from the rest of the listener and accumulate into
512-sample windows internally — the caller never has to know.

Falls back to a simple RMS gate if silero-vad isn't installed, so the rest of
the pipeline still functions.
"""
from __future__ import annotations

import numpy as np

try:
    from silero_vad import load_silero_vad  # type: ignore
    import torch  # type: ignore
    _SILERO_AVAILABLE = True
    _SILERO_ERR = ""
except Exception as _e:
    _SILERO_AVAILABLE = False
    _SILERO_ERR = str(_e)


SAMPLE_RATE = 16000
SILERO_CHUNK = 512  # samples (32 ms at 16k)
RMS_FALLBACK_THRESHOLD = 380.0


class SileroVAD:
    def __init__(self, threshold: float = 0.5) -> None:
        self.threshold = float(threshold)
        self._model = None
        self._buf = np.zeros(0, dtype=np.float32)
        self._last_prob = 0.0
        self.err = ""
        if _SILERO_AVAILABLE:
            try:
                self._model = load_silero_vad(onnx=True)
            except Exception as e:
                self.err = f"silero init failed: {e}"
                self._model = None
        else:
            self.err = f"silero-vad not installed: {_SILERO_ERR}"

    @property
    def ready(self) -> bool:
        return self._model is not None

    def is_speech(self, frame_int16: np.ndarray) -> bool:
        """Push a 30 ms (480 samples) frame, return whether speech is present."""
        if self._model is None:
            rms = float(np.sqrt(np.mean(frame_int16.astype(np.float32) ** 2)))
            return rms > RMS_FALLBACK_THRESHOLD
        f32 = frame_int16.astype(np.float32) / 32768.0
        self._buf = np.concatenate([self._buf, f32])
        any_speech = False
        while self._buf.size >= SILERO_CHUNK:
            chunk = self._buf[:SILERO_CHUNK]
            self._buf = self._buf[SILERO_CHUNK:]
            try:
                tensor = torch.from_numpy(chunk).float()
                prob = float(self._model(tensor, SAMPLE_RATE).item())
            except Exception:
                prob = 0.0
            self._last_prob = prob
            if prob >= self.threshold:
                any_speech = True
        return any_speech

    def last_prob(self) -> float:
        return self._last_prob

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.float32)
        if self._model is not None and hasattr(self._model, "reset_states"):
            try:
                self._model.reset_states()
            except Exception:
                pass

    def diagnostics(self) -> str:
        if self._model is not None:
            return "vad: Silero (ONNX) ready"
        return f"vad: RMS fallback — {self.err}"
