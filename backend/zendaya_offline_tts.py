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
