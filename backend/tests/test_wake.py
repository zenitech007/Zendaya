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
