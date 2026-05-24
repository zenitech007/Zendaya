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
