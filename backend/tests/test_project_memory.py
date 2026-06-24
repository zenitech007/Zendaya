"""Tests for memory.project — the per-project registry + current-project pointer."""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def project_mod(tmp_data_dir, monkeypatch):
    """Fresh memory.project bound to a tmp data dir each test."""
    import memory.data_store
    import memory.project as project
    importlib.reload(project)
    # data_store.DATA_DIR was already monkeypatched by tmp_data_dir.
    return project


def test_zendaya_seeded_and_default_root(project_mod):
    # With nothing set, current() is None but current_root() defaults to the repo.
    assert project_mod.current() is None
    root = project_mod.current_root()
    assert root.endswith("Zendaya")
    # The Zendaya project is pre-registered with its known-good test command.
    names = [p["name"] for p in project_mod.list_projects()]
    assert "Zendaya" in names


def test_set_current_by_name_round_trips(project_mod, monkeypatch):
    p = project_mod.set_current("Zendaya")
    assert p is not None
    assert p["name"] == "Zendaya"
    cur = project_mod.current()
    assert cur is not None and cur["name"] == "Zendaya"
    # Persists across a reload (re-read from disk).
    importlib.reload(project_mod)
    assert project_mod.current()["name"] == "Zendaya"


def test_set_current_by_path_registers_unseen(project_mod, tmp_path):
    new_proj = tmp_path / "MyApp"
    (new_proj).mkdir()
    (new_proj / "package.json").write_text("{}", encoding="utf-8")
    p = project_mod.set_current(str(new_proj))
    assert p is not None
    assert p["name"] == "MyApp"
    assert p["test_cmd"] == "npm test"  # heuristic picked up package.json
    assert project_mod.current_root().endswith("MyApp")


def test_set_current_unknown_returns_none(project_mod):
    assert project_mod.set_current("does-not-exist-anywhere") is None


def test_default_test_cmd_heuristics(project_mod, tmp_path):
    py = tmp_path / "pyproj"
    py.mkdir()
    (py / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    assert project_mod.default_test_cmd(str(py)) == "pytest -q"

    js = tmp_path / "jsproj"
    js.mkdir()
    (js / "package.json").write_text("{}", encoding="utf-8")
    assert project_mod.default_test_cmd(str(js)) == "npm test"

    bare = tmp_path / "bare"
    bare.mkdir()
    assert project_mod.default_test_cmd(str(bare)) == "pytest -q"


def test_update_profile_and_note_files_cap(project_mod, tmp_path):
    proj = tmp_path / "Capped"
    proj.mkdir()
    root = str(proj)
    project_mod.set_current(root)
    project_mod.update_profile(root, last_task="did a thing")
    assert project_mod.get_profile(root)["last_task"] == "did a thing"

    # note_files dedups and caps at 10, most-recent-first.
    for i in range(15):
        project_mod.note_files(root, [f"file_{i}.py"])
    recent = project_mod.get_profile(root)["recent_files"]
    assert len(recent) == 10
    assert recent[0] == "file_14.py"  # most recent first
    # Re-noting an existing file moves it to the front without duplicating.
    project_mod.note_files(root, ["file_10.py"])
    recent2 = project_mod.get_profile(root)["recent_files"]
    assert recent2[0] == "file_10.py"
    assert recent2.count("file_10.py") == 1
