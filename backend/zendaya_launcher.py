"""zendaya_launcher.py — supervises the Zendaya backend + launches the Tauri HUD.

Run by launch-zendaya.ps1 (hidden). Spawns the backend headless, waits for the
state server's /health, opens the HUD, and restarts the backend if it crashes.
A second launch re-attaches a HUD to the already-running backend. `--quit` shuts
everything down cleanly. Console is hidden, so all diagnostics go to
zendaya_logs/launcher.log.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from logging.handlers import RotatingFileHandler
from pathlib import Path

# ── Paths ───────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
LOG_DIR = REPO_ROOT / "zendaya_logs"
PID_FILE = LOG_DIR / "launcher.pid"
LAUNCHER_LOG = LOG_DIR / "launcher.log"
BACKEND_LOG = LOG_DIR / "backend.log"
VENV_PYTHONW = REPO_ROOT / "venv" / "Scripts" / "pythonw.exe"
RELEASE_DIR = REPO_ROOT / "zendaya-hud-react" / "src-tauri" / "target" / "release"
HUD_EXE_NAME = "Zendaya HUD.exe"

HEALTH_URL = "http://127.0.0.1:7475/health"
QUIT_URL = "http://127.0.0.1:7475/quit"
HEALTH_TIMEOUT = 60.0
HEALTH_INTERVAL = 0.5

CREATE_NO_WINDOW = 0x08000000  # Windows: spawn the child with no console window

log = logging.getLogger("zendaya.launcher")


def setup_logging() -> None:
    """Attach a rotating file handler once (the console is hidden)."""
    if log.handlers:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(LAUNCHER_LOG, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


def _http_get_json(url: str, timeout: float = 2.0):
    """GET a URL and parse JSON. Returns None on any error (connection, status, parse)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


def backend_is_ours() -> bool:
    """True only when /health responds 200 with the Zendaya identity marker.
    Guards against latching onto an unrelated process holding port 7475."""
    data = _http_get_json(HEALTH_URL)
    return bool(data) and data.get("name") == "Zendaya"
