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


# ── PID file (tracks the supervisor; used by --quit / --status) ──
def write_pid(pid: int | None = None) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid() if pid is None else pid), encoding="utf-8")


def read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def remove_pid() -> None:
    try:
        PID_FILE.unlink()
    except OSError:
        pass


# ── Spawn the backend + wait for it to be healthy ──
def _open_log(path: Path):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return open(path, "a", encoding="utf-8", buffering=1)


def spawn_backend() -> subprocess.Popen:
    """Launch the backend headless (hidden), teeing its output to backend.log."""
    out = _open_log(BACKEND_LOG)
    proc = subprocess.Popen(
        [str(VENV_PYTHONW), "zendaya.py", "--headless"],
        cwd=str(BACKEND_DIR),
        stdout=out,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    log.info("Spawned backend pid=%s", proc.pid)
    return proc


def wait_for_health(timeout: float = HEALTH_TIMEOUT, interval: float = HEALTH_INTERVAL) -> bool:
    """Poll /health until the Zendaya backend answers or the budget elapses."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if backend_is_ours():
            return True
        time.sleep(interval)
    return False


# ── Tauri HUD ──
def find_hud_exe() -> Path | None:
    """Locate the built Tauri HUD .exe; prefer the productName, else any top-level .exe."""
    preferred = RELEASE_DIR / HUD_EXE_NAME
    if preferred.exists():
        return preferred
    if RELEASE_DIR.is_dir():
        exes = sorted(RELEASE_DIR.glob("*.exe"))
        if exes:
            return exes[0]
    return None


def launch_hud() -> bool:
    """Open the Tauri HUD window. Returns False (and logs) if the build is missing."""
    exe = find_hud_exe()
    if exe is None:
        log.error("HUD executable not found in %s — run setup-zendaya.ps1 first.", RELEASE_DIR)
        return False
    subprocess.Popen([str(exe)], cwd=str(exe.parent))
    log.info("Launched HUD: %s", exe)
    return True


# ── Supervision (crash → restart with capped backoff) ──
RESTART_BACKOFF = [1, 2, 4, 8, 16]  # seconds; index clamps to last
MAX_RESTARTS = 5                     # crashes before giving up (avoids hot-loop)


def supervise(proc: subprocess.Popen) -> int:
    """Block on the backend. Exit 0 => intentional quit (stop). Crash => restart with
    capped exponential backoff. Returns the final exit code (0 = clean)."""
    restarts = 0
    while True:
        code = proc.wait()
        if code == 0:
            log.info("Backend exited cleanly (code 0) — shutting down launcher.")
            remove_pid()
            return 0
        log.warning("Backend crashed (code %s).", code)
        if restarts >= MAX_RESTARTS:
            log.error("Backend crashed %s times — giving up.", restarts)
            remove_pid()
            return code
        delay = RESTART_BACKOFF[min(restarts, len(RESTART_BACKOFF) - 1)]
        log.info("Restarting backend in %ss (attempt %s).", delay, restarts + 1)
        time.sleep(delay)
        proc = spawn_backend()
        restarts += 1
