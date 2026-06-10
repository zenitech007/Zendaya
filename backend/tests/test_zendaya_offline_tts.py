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


def test_split_sentences_basic():
    import zendaya_offline_tts as ot
    assert ot._split_sentences("Hello there. How are you?") == ["Hello there.", "How are you?"]


def test_split_sentences_empty():
    import zendaya_offline_tts as ot
    assert ot._split_sentences("   ") == []


def test_split_sentences_no_terminator_returns_whole():
    import zendaya_offline_tts as ot
    assert ot._split_sentences("just a clause") == ["just a clause"]


def test_wave_to_pcm16_dtype_and_range():
    import zendaya_offline_tts as ot
    wav = np.array([0.0, 1.0, -1.0, 0.5], dtype=np.float32)
    pcm = ot._wave_to_pcm16(wav, 22050, 22050)
    arr = np.frombuffer(pcm, dtype="<i2")
    assert arr.dtype == np.int16
    assert arr[0] == 0
    assert arr[1] == 32767
    assert arr[2] == -32767


def test_wave_to_pcm16_resamples_length():
    import zendaya_offline_tts as ot
    wav = np.zeros(48000, dtype=np.float32)
    pcm = ot._wave_to_pcm16(wav, 48000, 22050)
    arr = np.frombuffer(pcm, dtype="<i2")
    assert abs(len(arr) - 22050) <= 2


def test_pcm_bytes_response_chunks_exactly():
    import zendaya_offline_tts as ot
    data = bytes(range(10))
    r = ot.PcmBytesResponse(data)
    chunks = list(r.iter_content(chunk_size=4))
    assert chunks == [bytes(range(0, 4)), bytes(range(4, 8)), bytes(range(8, 10))]
    assert b"".join(chunks) == data
