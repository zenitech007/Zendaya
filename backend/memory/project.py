"""
memory.project — per-project memory + current-project pointer.

Persists a small registry to ``zendaya_data/projects.json`` so voice-coding
commands ("run the tests", "commit this", "resume") know *which* repo they
target. Doubles as the project registry.

Pure-ish: every read/write funnels through ``memory.data_store`` and the
stdlib. No knowledge of shells or speech — that lives in ``skills.dev_voice``.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from memory import data_store

_STORE = "projects"  # -> zendaya_data/projects.json

# The Zendaya repo root: backend/memory/project.py -> backend -> repo root.
_ZENDAYA_ROOT = str(Path(__file__).resolve().parent.parent.parent)
_ZENDAYA_TEST_CMD = 'pytest backend/tests -q -m "not slow"'

_RECENT_CAP = 10


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _norm(path: str) -> str:
    """Canonical key for a project root (absolute, real, no trailing slash)."""
    try:
        return os.path.normcase(os.path.realpath(os.path.expanduser(path)))
    except Exception:
        return os.path.normcase(path)


def _load() -> Dict[str, Any]:
    """Load the registry; tolerate missing/corrupt files (re-seed default)."""
    data = data_store.load(_STORE, default={})
    if not isinstance(data, dict):
        data = {}
    data.setdefault("current", None)
    projects = data.get("projects")
    if not isinstance(projects, dict):
        projects = {}
    data["projects"] = projects
    # Always ensure the Zendaya repo is a known project so the very first
    # "run the tests" works without setup.
    zkey = _norm(_ZENDAYA_ROOT)
    if zkey not in projects:
        projects[zkey] = _new_profile(_ZENDAYA_ROOT, test_cmd=_ZENDAYA_TEST_CMD)
    return data


def _save(data: Dict[str, Any]) -> None:
    data_store.save(_STORE, data)


def _new_profile(root: str, test_cmd: Optional[str] = None) -> Dict[str, Any]:
    return {
        "name": os.path.basename(os.path.normpath(root)) or root,
        "root": root,
        "test_cmd": test_cmd or default_test_cmd(root),
        "run_cmd": None,
        "last_task": None,
        "recent_files": [],
        "updated_at": _now(),
    }


# ---------------------------------------------------------------------------
# Heuristics
# ---------------------------------------------------------------------------

def default_test_cmd(root: str) -> str:
    """Guess a test command from what's on disk.

    The Zendaya root seeds its known-good command; a ``package.json`` (without
    Python test config) suggests ``npm test``; everything else defaults to
    ``pytest -q``.
    """
    rp = os.path.realpath(os.path.expanduser(root))
    if _norm(rp) == _norm(_ZENDAYA_ROOT):
        return _ZENDAYA_TEST_CMD

    def _exists(*names: str) -> bool:
        return any(os.path.exists(os.path.join(rp, n)) for n in names)

    has_py = _exists("pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini") or os.path.isdir(
        os.path.join(rp, "tests")
    )
    if has_py:
        return "pytest -q"
    if _exists("package.json"):
        return "npm test"
    return "pytest -q"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_profile(root: str) -> Dict[str, Any]:
    """Profile for a root, creating a default (and persisting) if unseen."""
    data = _load()
    key = _norm(root)
    profiles = data["projects"]
    if key not in profiles:
        profiles[key] = _new_profile(os.path.realpath(os.path.expanduser(root)))
        _save(data)
    return profiles[key]


def current() -> Optional[Dict[str, Any]]:
    """The active project profile, or None if nothing has been set."""
    data = _load()
    cur = data.get("current")
    if not cur:
        return None
    return data["projects"].get(_norm(cur))


def current_root() -> str:
    """Active root, defaulting to the Zendaya repo when nothing is set yet."""
    cur = current()
    if cur and cur.get("root"):
        return cur["root"]
    return _ZENDAYA_ROOT


def set_current(name_or_path: str) -> Optional[Dict[str, Any]]:
    """Set the active project from a spoken name or a filesystem path.

    Resolution order: case-insensitive match against known project ``name``s,
    then a filesystem path (registering it on first sight). Returns the active
    profile, or None if it couldn't be resolved (caller asks the user to
    repeat).
    """
    if not name_or_path or not name_or_path.strip():
        return None
    raw = name_or_path.strip().strip("'\"")
    data = _load()
    profiles = data["projects"]

    # 1) Exact-ish name match (case-insensitive) against known projects.
    matches = [k for k, p in profiles.items() if (p.get("name") or "").lower() == raw.lower()]
    if len(matches) == 1:
        data["current"] = matches[0]
        _save(data)
        return profiles[matches[0]]

    # 2) Filesystem path (existing directory) — register on first sight.
    expanded = os.path.expanduser(raw)
    if os.path.isdir(expanded):
        root = os.path.realpath(expanded)
        key = _norm(root)
        if key not in profiles:
            profiles[key] = _new_profile(root)
        data["current"] = key
        _save(data)
        return profiles[key]

    # 3) Ambiguous or unknown — let the caller prompt the user.
    return None


def update_profile(root: str, **fields: Any) -> Dict[str, Any]:
    """Merge fields into a project profile, stamp updated_at, persist."""
    data = _load()
    key = _norm(root)
    profiles = data["projects"]
    if key not in profiles:
        profiles[key] = _new_profile(os.path.realpath(os.path.expanduser(root)))
    profile = profiles[key]
    for k, v in fields.items():
        profile[k] = v
    profile["updated_at"] = _now()
    _save(data)
    return profile


def note_files(root: str, paths: List[str]) -> Dict[str, Any]:
    """Push paths onto recent_files (most-recent first, dedup, capped)."""
    data = _load()
    key = _norm(root)
    profiles = data["projects"]
    if key not in profiles:
        profiles[key] = _new_profile(os.path.realpath(os.path.expanduser(root)))
    profile = profiles[key]
    recent: List[str] = list(profile.get("recent_files") or [])
    for p in paths:
        if not p:
            continue
        if p in recent:
            recent.remove(p)
        recent.insert(0, p)
    profile["recent_files"] = recent[:_RECENT_CAP]
    profile["updated_at"] = _now()
    _save(data)
    return profile


def list_projects() -> List[Dict[str, Any]]:
    """All known project profiles (for 'what projects do you know')."""
    data = _load()
    return list(data["projects"].values())
