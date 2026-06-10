"""Unit tests for Zendaya's offline Coqui TTS engine (Coqui mocked for speed)."""
from __future__ import annotations

import numpy as np
import pytest


def test_default_voice_engine_is_offline(tmp_data_dir):
    import zendaya_offline_tts as ot
    assert ot.get_voice_engine() == "offline"


def test_set_and_get_voice_engine_roundtrip(tmp_data_dir):
    import zendaya_offline_tts as ot
    assert ot.set_voice_engine("elevenlabs") == "elevenlabs"
    assert ot.get_voice_engine() == "elevenlabs"
    assert ot.set_voice_engine("offline") == "offline"
    assert ot.get_voice_engine() == "offline"


def test_set_voice_engine_rejects_unknown(tmp_data_dir):
    import zendaya_offline_tts as ot
    with pytest.raises(ValueError):
        ot.set_voice_engine("bogus")


def test_get_voice_engine_falls_back_on_corrupt_file(tmp_data_dir):
    import zendaya_offline_tts as ot
    (tmp_data_dir / "voice_engine.json").write_text("not json", encoding="utf-8")
    assert ot.get_voice_engine() == "offline"
