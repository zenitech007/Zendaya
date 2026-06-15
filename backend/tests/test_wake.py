"""Wake-word verifier + engine tests (openWakeWord mocked; no real ONNX)."""
from __future__ import annotations

import numpy as np
import pytest

from voice import wake


@pytest.mark.parametrize("transcript,ok", [
    ("zendaya", True), ("Zendaya, what's the weather", True),
    ("zen daya", True), ("sendaya", True),
    ("zen", False), ("hello there", False),
])
def test_verifier_zendaya_model(transcript, ok):
    assert wake.verifier_passes_for_model("zendaya", transcript) is ok


@pytest.mark.parametrize("transcript,ok", [
    ("zen", True), ("hey zen", True), ("Zen, play music", True),
    ("zenith", False), ("frozen yogurt", False), ("present", False),
    ("zendaya", False),
])
def test_verifier_zen_model(transcript, ok):
    assert wake.verifier_passes_for_model("zen", transcript) is ok


def test_verifier_empty_transcript_false():
    assert wake.verifier_passes_for_model("zendaya", "") is False


def test_verifier_jarvis_still_accepts_jarvis_or_zendaya():
    assert wake.verifier_passes_for_model("hey_jarvis", "jarvis") is True
    assert wake.verifier_passes_for_model("hey_jarvis", "zendaya") is True


class _FakeOWW:
    """Stand-in for openwakeword Model: returns preset scores per predict()."""
    def __init__(self, wakeword_models=None, inference_framework=None):
        self.wakeword_models = wakeword_models
        self._queue = []
    def set_scores(self, *dicts):
        self._queue = list(dicts)
    def predict(self, chunk):
        return self._queue.pop(0) if self._queue else {}


def _engine_with_fake(monkeypatch, models, scores):
    monkeypatch.setattr(wake, "_OWW_AVAILABLE", True)
    fake = _FakeOWW()
    monkeypatch.setattr(wake, "_OWWModel", lambda **kw: fake)
    eng = wake.WakeEngine(models=models)
    fake.set_scores(*scores)
    return eng, fake


def test_model_key_from_path_and_builtin():
    assert wake._model_key(r"C:\x\zendaya.onnx") == "zendaya"
    assert wake._model_key("voice/models/zen.onnx") == "zen"
    assert wake._model_key("hey_jarvis") == "hey_jarvis"


def test_resolve_env_comma_split(monkeypatch):
    monkeypatch.setenv("ZENDAYA_WAKE_MODEL", "a/zendaya.onnx, a/zen.onnx")
    assert wake._resolve_model_entries() == ["a/zendaya.onnx", "a/zen.onnx"]


def test_resolve_fallback_to_hey_jarvis(monkeypatch):
    monkeypatch.delenv("ZENDAYA_WAKE_MODEL", raising=False)
    monkeypatch.setattr(wake.os.path, "isfile", lambda p: False)
    assert wake._resolve_model_entries() == ["hey_jarvis"]


def test_per_model_default_thresholds(monkeypatch):
    monkeypatch.delenv("ZENDAYA_WAKE_THRESHOLD", raising=False)
    eng, _ = _engine_with_fake(monkeypatch, ["m/zendaya.onnx", "m/zen.onnx"], [])
    assert eng.model_keys == ["zendaya", "zen"]
    assert eng.thresholds["zendaya"] == 0.5
    assert eng.thresholds["zen"] == 0.7


def test_push_fires_and_records_model(monkeypatch):
    eng, fake = _engine_with_fake(monkeypatch, ["m/zendaya.onnx", "m/zen.onnx"],
                                  [{"zendaya": 0.9, "zen": 0.0}] * wake.SMOOTH_WINDOW)
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES * wake.SMOOTH_WINDOW, dtype=np.int16)
    assert eng.push(frame) is True
    assert eng.last_fired_model == "zendaya"
    assert eng.last_score >= 0.5


def test_push_respects_zen_higher_threshold(monkeypatch):
    # zen smoothed 0.6 is below zen's 0.7 threshold -> no fire
    eng, fake = _engine_with_fake(monkeypatch, ["m/zen.onnx"],
                                  [{"zen": 0.6}] * wake.SMOOTH_WINDOW)
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES * wake.SMOOTH_WINDOW, dtype=np.int16)
    assert eng.push(frame) is False
    assert eng.last_fired_model is None


def test_push_barge_in_uses_stricter_threshold(monkeypatch):
    # zendaya smoothed 0.6 >= normal 0.5 but < barge 0.72
    eng, fake = _engine_with_fake(monkeypatch, ["m/zendaya.onnx"],
                                  [{"zendaya": 0.6}] * wake.SMOOTH_WINDOW)
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES * wake.SMOOTH_WINDOW, dtype=np.int16)
    assert eng.push(frame, barge_in=True) is False


def test_push_cooldown_blocks_second_fire(monkeypatch):
    eng, fake = _engine_with_fake(monkeypatch, ["m/zendaya.onnx"], [{"zendaya": 0.9}])
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES, dtype=np.int16)
    assert eng.push(frame) is True            # first fire
    fake.set_scores({"zendaya": 0.9})
    assert eng.push(frame) is False           # within COOLDOWN_S -> blocked


def test_push_second_model_fires_and_is_recorded(monkeypatch):
    eng, fake = _engine_with_fake(monkeypatch, ["m/zendaya.onnx", "m/zen.onnx"],
                                  [{"zendaya": 0.0, "zen": 0.9}])
    frame = np.zeros(wake.WAKE_CHUNK_SAMPLES, dtype=np.int16)
    assert eng.push(frame) is True
    assert eng.last_fired_model == "zen"


import os


@pytest.mark.slow
def test_zendaya_model_fires_on_synth_clip():
    """Mic-free end-to-end check: synthesize 'Zendaya' with Coqui, resample to
    16 kHz, feed it through the real WakeEngine loaded with zendaya.onnx, and
    assert it fires. Self-skips until the trained model is present."""
    model = os.path.join(wake._MODELS_DIR, "zendaya.onnx")
    if not os.path.isfile(model):
        pytest.skip("zendaya.onnx not trained/present yet")
    try:
        from voice import offline_tts
        pcm = offline_tts.synth_to_pcm("Zendaya", target_sr=16000)
    except Exception as e:
        pytest.skip(f"offline TTS unavailable: {e}")
    if not pcm:
        pytest.skip("offline TTS produced no audio")
    samples = np.frombuffer(pcm, dtype="<i2")
    eng = wake.WakeEngine(models=[model])
    if not eng.ready:
        pytest.skip(f"wake engine not ready: {eng.err}")
    fired = False
    for i in range(0, len(samples), wake.WAKE_CHUNK_SAMPLES):
        if eng.push(samples[i:i + wake.WAKE_CHUNK_SAMPLES]):
            fired = True
            break
    assert fired, "trained zendaya.onnx did not fire on a synthesized 'Zendaya' clip"
    assert eng.last_fired_model == "zendaya"
