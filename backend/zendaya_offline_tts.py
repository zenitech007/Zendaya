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
