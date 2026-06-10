"""
zendaya_face_modes — switch between Zendaya's frontends on command.

Modes:
    pet       — current Tauri 3D VRM pet (default Zendaya.vrm)
    anime     — Tauri pet using the orange/anime VRM (Zendaya-orange.vrm)
    hud       — single-file HTML HUD at zendaya_ui.html (served from /ui)
    minimize  — small/tray-style window; keeps audio + state alive but hides face

Mode is persisted in MEM["face_mode"]. The actual launching/closing of
windows is handled by per-mode hooks (because the Tauri pet is an external
process and the HUD is a browser window).

Public API:
    current() -> str
    set_mode(name: str) -> str
    parse_face_command(user_text: str) -> Optional[dict]
    handle_face_command(parsed: dict) -> str
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, Optional


VALID_MODES = {"pet", "anime", "hud", "minimize"}
DEFAULT_MODE = "pet"

_BACKEND_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _BACKEND_DIR.parent
_TAURI_PET_DIR = _PROJECT_ROOT / "zendaya-pet-template"  # see project_zendaya memory
_REACT_HUD_DIR = _PROJECT_ROOT / "zendaya-hud-react"
# Tauri-wrapped HUD (built artifact lives under src-tauri/target/...)
_HUD_EXE_CANDIDATES = [
    _REACT_HUD_DIR / "src-tauri" / "target" / "release" / "zendaya-hud.exe",
    _REACT_HUD_DIR / "src-tauri" / "target" / "debug" / "zendaya-hud.exe",
    # Legacy locations kept for back-compat with older builds.
    _PROJECT_ROOT / "zendaya-hud" / "src-tauri" / "target" / "release" / "zendaya-hud.exe",
    _PROJECT_ROOT / "zendaya-hud" / "src-tauri" / "target" / "debug" / "zendaya-hud.exe",
]
_VRM_ASSETS = _BACKEND_DIR / "assets"
_VRM_DEFAULT = _VRM_ASSETS / "Zendaya.vrm"
_VRM_ANIME = _VRM_ASSETS / "Zendaya-orange.vrm"

# Track child processes we spawned so we can stop them.
_CHILDREN: Dict[str, subprocess.Popen] = {}
_LOCK = threading.Lock()


def _z():
    import zendaya as _zmod
    return _zmod


def _mem() -> dict:
    return _z().MEM


def _save() -> None:
    z = _z()
    try:
        z.save_memory(z.MEM)
    except Exception:
        pass


def current() -> str:
    return str(_mem().get("face_mode", DEFAULT_MODE))


def _stop_child(key: str) -> None:
    proc = _CHILDREN.pop(key, None)
    if proc is None:
        return
    try:
        proc.terminate()
    except Exception:
        pass


def _swap_active_vrm(target: Path) -> bool:
    """Copy the requested VRM to the slot the pet auto-loads (`Zendaya.vrm`).

    The Tauri/Godot pet imports a fixed filename, so swapping = copy-on-top.
    Returns True if the swap (or no-op) happened cleanly.
    """
    if not target.is_file():
        return False
    if not _VRM_DEFAULT.is_file():
        # Nothing to swap with; just let the pet start with whatever is there.
        return False
    try:
        if target.resolve() == _VRM_DEFAULT.resolve():
            return True
        import shutil
        shutil.copy2(target, _VRM_DEFAULT)
        return True
    except Exception:
        return False


def _launch_tauri_pet() -> Optional[str]:
    """Best-effort launcher. Returns a status string or None on success."""
    if not _TAURI_PET_DIR.is_dir():
        return f"Tauri pet folder not found at {_TAURI_PET_DIR}."
    if "tauri_pet" in _CHILDREN and _CHILDREN["tauri_pet"].poll() is None:
        return None  # already running
    npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
    try:
        proc = subprocess.Popen(
            [npm, "run", "dev:app"],
            cwd=str(_TAURI_PET_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
        _CHILDREN["tauri_pet"] = proc
        return None
    except FileNotFoundError:
        return "npm not found on PATH — couldn't launch Tauri pet."
    except Exception as e:
        return f"Failed to launch Tauri pet: {e}"


def _launch_hud() -> Optional[str]:
    """Launch the HUD as a standalone desktop app.

    Order:
      1. Built standalone .exe (zendaya-hud-react/src-tauri/target/release|debug).
      2. `npm run dev:app` in zendaya-hud-react/ — Tauri dev window with bundled WebView2.

    No browser fallback: HUD mode is desktop-only by design.
    """
    if "tauri_hud" in _CHILDREN and _CHILDREN["tauri_hud"].poll() is None:
        return None  # already running

    for exe in _HUD_EXE_CANDIDATES:
        if exe.is_file():
            try:
                proc = subprocess.Popen(
                    [str(exe)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                )
                _CHILDREN["tauri_hud"] = proc
                return None
            except Exception as e:
                print(f"(face_modes: HUD exe launch failed: {e})")
                break

    if _REACT_HUD_DIR.is_dir():
        npm = "npm.cmd" if sys.platform.startswith("win") else "npm"
        try:
            proc = subprocess.Popen(
                [npm, "run", "dev:app"],
                cwd=str(_REACT_HUD_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
            _CHILDREN["tauri_hud"] = proc
            return None
        except FileNotFoundError:
            return "npm not on PATH — can't launch HUD dev app. Build it with `npm run build:app` in zendaya-hud-react/."
        except Exception as e:
            return f"Failed to launch HUD dev app: {e}"

    return f"HUD frontend not found at {_REACT_HUD_DIR}."


def set_mode(name: str) -> str:
    name = (name or "").strip().lower()
    if name not in VALID_MODES:
        return f"Unknown face mode: {name!r}. Valid: {', '.join(sorted(VALID_MODES))}."
    prev = current()
    if name == prev:
        return f"Already in {name} mode."
    with _LOCK:
        _mem()["face_mode"] = name
        _save()

        if name == "pet":
            _swap_active_vrm(_VRM_DEFAULT)
            err = _launch_tauri_pet()
            if err:
                return f"Switched to pet (note: {err})."
            return "Switched to pet mode."

        if name == "anime":
            ok = _swap_active_vrm(_VRM_ANIME)
            err = _launch_tauri_pet()
            note = "" if ok else " (anime VRM not found, using default)"
            if err:
                return f"Switched to anime{note} — {err}"
            return f"Switched to anime mode{note}."

        if name == "hud":
            err = _launch_hud()
            if err:
                return f"Switched to HUD (note: {err})."
            return "Switched to HUD mode — opening desktop app."

        if name == "minimize":
            # We don't kill the pet — it self-handles minimize via the window watcher.
            # We just record the mode so callers (and the Tauri side, which polls
            # /face_mode) know to render small / hide face.
            return "Minimized — running in the background."

    return f"Switched to {name}."


# ───────────────────────────────────────────────────────────────────────
# Parser
# ───────────────────────────────────────────────────────────────────────

_SWITCH_RE = re.compile(
    r"\b(?:switch|change|go|turn)\s+(?:to\s+|into\s+)?(?P<mode>pet|anime|hud|minimi[sz]ed?|tray|small)\b",
    re.IGNORECASE,
)
_BARE_RE = re.compile(
    r"^\s*(?:minimi[sz]e|tray\s*mode|go\s+small|hud\s*mode|anime\s*mode|pet\s*mode|"
    r"face\s*mode|what\s+(?:face|mode)\s+are\s+you\s+in)\s*\??\s*$",
    re.IGNORECASE,
)
_LIST_RE = re.compile(r"^\s*(?:list|show)\s+(?:face\s+)?modes?\s*$", re.IGNORECASE)


def _normalize(token: str) -> str:
    t = token.lower().strip()
    if t in ("minimised", "minimized", "minimise", "minimize", "tray", "small", "tray mode", "go small"):
        return "minimize"
    if t in ("pet", "pet mode"):
        return "pet"
    if t in ("anime", "anime mode"):
        return "anime"
    if t in ("hud", "hud mode"):
        return "hud"
    return t


def parse_face_command(user_text: str) -> Optional[Dict[str, Any]]:
    if not user_text:
        return None
    t = user_text.strip()

    if _LIST_RE.match(t):
        return {"op": "list"}

    if re.match(r"^(?:what\s+(?:face|mode)\s+are\s+you\s+in|face\s*mode)\s*\??$", t, re.IGNORECASE):
        return {"op": "current"}

    m = _SWITCH_RE.search(t)
    if m:
        return {"op": "set", "mode": _normalize(m.group("mode"))}

    m = _BARE_RE.match(t)
    if m:
        # Take the first word as the target.
        first = t.split()[0].lower()
        return {"op": "set", "mode": _normalize(first)}

    return None


def handle_face_command(parsed: Dict[str, Any]) -> str:
    op = parsed.get("op")
    if op == "list":
        return "Face modes: " + ", ".join(sorted(VALID_MODES)) + f" (currently: {current()})."
    if op == "current":
        return f"Current face: {current()}."
    if op == "set":
        return set_mode(parsed.get("mode", ""))
    return f"Unknown face op: {op}"
