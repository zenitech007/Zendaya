"""
zendaya_installer — package installs and sandboxed downloads.

Two responsibilities:
    * install_package(name)  — auto-detect pip / npm / winget / choco and
      stage a confirmation in MEM["pending_confirm"] before running anything.
    * download_file(url)     — fetch a binary into ~/Zendaya/downloads/, hash
      it (SHA-256), optional Defender scan, and stage a confirmation before
      anyone calls run_installer() on it.

Both paths route through the existing yes/no flow in zendaya.py:confirm_dangerous.
Nothing in this module executes a package manager or installer without an
explicit MEM["pending_confirm"] handshake.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Optional


# ---------------------------------------------------------------------------
# Paths and small helpers
# ---------------------------------------------------------------------------

_DOWNLOADS = Path(os.path.expanduser("~/Zendaya/downloads"))
_DOWNLOADS.mkdir(parents=True, exist_ok=True)

_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._@\-+/]{1,80}$")
_INSTALLABLE_EXTS = {".exe", ".msi", ".msix", ".bat", ".ps1"}
_MAX_DOWNLOAD_BYTES = 250 * 1024 * 1024  # 250 MB hard cap


def _mem() -> Optional[dict]:
    """Lazy access to the main brain's MEM dict so we can stage confirmations."""
    try:
        import zendaya as _z
        return getattr(_z, "MEM", None)
    except Exception:
        return None


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------

# Manager-specific hints; the first match wins.
_PIP_HINTS = re.compile(r"^(py|python|pip)[-_:]", re.I)
_NPM_HINTS = re.compile(r"^(@|node[-_:]|npm[-_:])|(\.js|\.ts)$", re.I)


def _pick_manager(name: str, override: Optional[str]) -> str:
    """Return one of: pip, npm, winget, choco. Override wins if installed."""
    if override:
        override = override.lower().strip()
        if override in {"pip", "npm", "winget", "choco"}:
            return override
    n = name.strip()
    if _PIP_HINTS.search(n) and _has("pip"):
        return "pip"
    if _NPM_HINTS.search(n) and _has("npm"):
        return "npm"
    if _has("winget"):
        return "winget"
    if _has("choco"):
        return "choco"
    if _has("pip"):
        return "pip"
    if _has("npm"):
        return "npm"
    return "winget"  # last-resort label; will fail clearly if missing


def _build_install_cmd(manager: str, name: str) -> list[str]:
    if manager == "pip":
        return [shutil.which("pip") or "pip", "install", "--user", name]
    if manager == "npm":
        return [shutil.which("npm") or "npm", "install", "-g", name]
    if manager == "winget":
        return [
            shutil.which("winget") or "winget",
            "install",
            "--id",
            name,
            "--accept-package-agreements",
            "--accept-source-agreements",
            "-h",
        ]
    if manager == "choco":
        return [shutil.which("choco") or "choco", "install", name, "-y"]
    return [name]


# ---------------------------------------------------------------------------
# install_package — staged behind MEM["pending_confirm"]
# ---------------------------------------------------------------------------

def install_package(name: str, manager: Optional[str] = None) -> str:
    """Stage a package install. Returns a question for the user; runs after yes."""
    if not name or not _SAFE_NAME_RE.match(name):
        return "That package name has characters I don't recognise — say it again with letters, digits, dots, dashes, or `@scope/name`."
    chosen = _pick_manager(name, manager)
    if not _has(chosen.split()[0]):
        return f"I can't run {chosen} — it isn't installed on this machine."
    cmd = _build_install_cmd(chosen, name)
    pretty = " ".join(cmd)

    mem = _mem()
    if mem is None:
        return "Memory isn't available right now, so I can't stage a confirmation. Try again in a moment."

    mem["pending_confirm"] = {
        "action": "install_package",
        "manager": chosen,
        "name": name,
        "cmd": cmd,
        "ts": time.time(),
    }
    return f"I'd like to run `{pretty}` to install **{name}** via {chosen}. Say yes to go ahead, or no to cancel."


def _execute_install(cmd: list[str], manager: str, name: str) -> str:
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"{manager} install of {name} timed out after 10 minutes."
    except FileNotFoundError as e:
        return f"{manager} isn't on PATH: {e}"
    except Exception as e:
        return f"Install failed before it ran: {e}"
    elapsed = time.time() - started
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    tail_out = out[-1200:] if out else ""
    tail_err = err[-800:] if err else ""
    head = f"{manager} install of {name}: exit={proc.returncode}, elapsed={elapsed:.1f}s"
    parts = [head]
    if tail_out:
        parts.append(f"--- stdout ---\n{tail_out}")
    if tail_err:
        parts.append(f"--- stderr ---\n{tail_err}")
    return "\n".join(parts)


def confirm_install(pending: Dict) -> str:
    """Called from confirm_dangerous when the user says yes."""
    cmd = pending.get("cmd") or []
    manager = pending.get("manager") or "?"
    name = pending.get("name") or "?"
    if not cmd:
        return "I lost the install command — try asking again."
    return _execute_install(cmd, manager, name)


# ---------------------------------------------------------------------------
# download_file — fetch into ~/Zendaya/downloads/ with SHA-256 and optional scan
# ---------------------------------------------------------------------------

def _safe_dest_name(url: str, override: Optional[str]) -> str:
    if override:
        base = os.path.basename(override.strip())
    else:
        parsed = urllib.parse.urlparse(url)
        base = os.path.basename(parsed.path) or "download.bin"
    base = re.sub(r"[^A-Za-z0-9._\-]+", "_", base).strip("_") or "download.bin"
    return base


def download_file(url: str, dest_name: Optional[str] = None, scan: bool = True) -> str:
    """Fetch URL → ~/Zendaya/downloads/<name>. Returns a summary with the SHA-256."""
    if not url or not re.match(r"^https?://", url, re.I):
        return "I only download over http/https."
    dest = _DOWNLOADS / _safe_dest_name(url, dest_name)
    if dest.exists():
        stem, ext = os.path.splitext(dest.name)
        dest = _DOWNLOADS / f"{stem}-{int(time.time())}{ext}"

    req = urllib.request.Request(url, headers={"User-Agent": "Zendaya/1.0"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            length = int(resp.headers.get("Content-Length") or 0)
            if length and length > _MAX_DOWNLOAD_BYTES:
                return f"That file is {length / 1e6:.1f} MB — over my 250 MB safety cap."
            written = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > _MAX_DOWNLOAD_BYTES:
                        f.close()
                        try:
                            dest.unlink()
                        except Exception:
                            pass
                        return "Aborted — the download went past my 250 MB safety cap."
                    f.write(chunk)
    except Exception as e:
        try:
            if dest.exists():
                dest.unlink()
        except Exception:
            pass
        return f"Download failed: {e}"
    elapsed = time.time() - started
    digest = _sha256(dest)
    size_mb = dest.stat().st_size / 1e6

    scan_line = ""
    if scan:
        scan_line = "\n" + _defender_scan(dest)

    return (
        f"Downloaded {dest.name} ({size_mb:.2f} MB in {elapsed:.1f}s)\n"
        f"Path: {dest}\n"
        f"SHA-256: {digest}"
        f"{scan_line}"
    )


def _defender_scan(path: Path) -> str:
    """Best-effort Windows Defender scan. Returns a one-line status."""
    mp = shutil.which("MpCmdRun.exe") or r"C:\\Program Files\\Windows Defender\\MpCmdRun.exe"
    if not os.path.isfile(mp):
        return "Defender scan: MpCmdRun.exe not found, skipped."
    try:
        proc = subprocess.run(
            [mp, "-Scan", "-ScanType", "3", "-File", str(path), "-DisableRemediation"],
            capture_output=True,
            text=True,
            timeout=180,
            shell=False,
        )
    except Exception as e:
        return f"Defender scan: failed to run ({e})."
    if proc.returncode == 0:
        return "Defender scan: clean."
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    last = tail[-1] if tail else "(no output)"
    return f"Defender scan: exit={proc.returncode} — {last}"


# ---------------------------------------------------------------------------
# run_installer — only after explicit confirmation
# ---------------------------------------------------------------------------

def run_installer(path: str) -> str:
    """Stage execution of a downloaded installer. Confirmation required."""
    if not path:
        return "I need a path to run."
    p = Path(os.path.expanduser(path))
    try:
        p.resolve().relative_to(_DOWNLOADS.resolve())
    except ValueError:
        return f"For safety I only run installers from {_DOWNLOADS}. That path is elsewhere."
    if not p.is_file():
        return f"No such file: {p}"
    ext = p.suffix.lower()
    if ext not in _INSTALLABLE_EXTS:
        return f"I won't execute {ext or '(no extension)'} as an installer. Allowed: {sorted(_INSTALLABLE_EXTS)}"

    mem = _mem()
    if mem is None:
        return "Memory isn't available — can't stage a confirmation right now."

    digest = _sha256(p)
    mem["pending_confirm"] = {
        "action": "run_installer",
        "path": str(p),
        "ext": ext,
        "sha256": digest,
        "ts": time.time(),
    }
    return (
        f"Ready to run installer **{p.name}** (SHA-256 {digest[:16]}…). "
        "Say yes to execute, or no to cancel."
    )


def confirm_run_installer(pending: Dict) -> str:
    path = pending.get("path") or ""
    ext = (pending.get("ext") or "").lower()
    if not path or not os.path.isfile(path):
        return "The installer file is gone — try downloading it again."
    if ext == ".msi":
        cmd = ["msiexec", "/i", path, "/passive", "/norestart"]
    elif ext == ".ps1":
        cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path]
    elif ext == ".bat":
        cmd = ["cmd.exe", "/c", path]
    else:
        cmd = [path]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return "Installer ran past 15 minutes and was killed."
    except Exception as e:
        return f"Installer failed to start: {e}"
    out = (proc.stdout or "").strip()[-1000:]
    err = (proc.stderr or "").strip()[-800:]
    parts = [f"installer exit={proc.returncode}"]
    if out:
        parts.append(f"--- stdout ---\n{out}")
    if err:
        parts.append(f"--- stderr ---\n{err}")
    return "\n".join(parts)
