"""Pytest fixtures for the assistant-features test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the backend/ directory importable for `import skills.assistant_features` etc.
_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture()
def tmp_data_dir(tmp_path, monkeypatch):
    """Point memory.data_store at a fresh tmp directory for this test only."""
    import memory.data_store

    monkeypatch.setattr(memory.data_store, "DATA_DIR", tmp_path)
    return tmp_path


@pytest.fixture()
def fake_notifier():
    """Records every notify call so tests can assert on what was spoken/toasted."""
    calls = {"speak": [], "toast": []}

    def speak(text: str) -> None:
        calls["speak"].append(text)

    def toast(title: str, body: str, duration: int = 10) -> None:
        calls["toast"].append((title, body, duration))

    return speak, toast, calls
