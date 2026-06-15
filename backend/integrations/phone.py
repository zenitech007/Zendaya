"""
integrations.phone.py
================
Phone bridge via KDE Connect. Wraps `kdeconnect-cli` for SMS, ring, clipboard,
file sharing, and notifications.

Install KDE Connect on Windows: https://kdeconnect.kde.org/download.html
Pair your phone (Android: KDE Connect app) and Zendaya auto-discovers it.
"""

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from dotenv import load_dotenv

from memory.data_store import load as ds_load, save as ds_save

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

KDEC_OVERRIDE_ID = os.getenv("KDE_CONNECT_DEVICE_ID") or ""

_AVAIL_CACHE: Dict[str, float] = {"checked_at": 0.0, "ok": 0.0}
_AVAIL_TTL = 60.0

_CLI_CANDIDATES = [
    "kdeconnect-cli",
    "kdeconnect-cli.exe",
    r"C:\Program Files\KDE Connect\bin\kdeconnect-cli.exe",
    r"C:\Program Files (x86)\KDE Connect\bin\kdeconnect-cli.exe",
]


def _find_cli() -> Optional[str]:
    """Locate kdeconnect-cli executable, or None if not installed."""
    cached = ds_load("kde_cli_path", default={}).get("path")
    if cached and os.path.isfile(cached):
        return cached
    found = shutil.which("kdeconnect-cli") or shutil.which("kdeconnect-cli.exe")
    if not found:
        for cand in _CLI_CANDIDATES:
            if os.path.isfile(cand):
                found = cand
                break
    if found:
        ds_save("kde_cli_path", {"path": found})
    return found


def _run(args: List[str], timeout: float = 8.0) -> Tuple[int, str, str]:
    cli = _find_cli()
    if not cli:
        return 127, "", "kdeconnect-cli not found"
    try:
        proc = subprocess.run(
            [cli] + args,
            capture_output=True, text=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def kdec_installed() -> bool:
    return _find_cli() is not None


def kdec_available() -> bool:
    """Return True if KDE Connect is installed AND a paired reachable device exists."""
    now = time.time()
    if now - _AVAIL_CACHE["checked_at"] < _AVAIL_TTL:
        return bool(_AVAIL_CACHE["ok"])
    ok = bool(kdec_paired_device())
    _AVAIL_CACHE["checked_at"] = now
    _AVAIL_CACHE["ok"] = 1.0 if ok else 0.0
    return ok


def kdec_unavailable_message() -> str:
    if not kdec_installed():
        return (
            "KDE Connect isn't installed on this machine yet. Grab it from "
            "https://kdeconnect.kde.org/download.html, install KDE Connect on "
            "your phone too, and pair them. I'll handle the rest."
        )
    return (
        "I see KDE Connect is installed but no paired phone is reachable right "
        "now. Open KDE Connect on this PC and your phone, accept the pairing, "
        "then ask me to ring it again."
    )


def kdec_list_devices() -> List[Dict[str, str]]:
    """Return [{id, name, reachable, paired}, ...]."""
    rc, out, _ = _run(["--list-devices"])
    if rc != 0 or not out:
        return []
    devices = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^-\s*(.+?):\s*([0-9a-f_]+)\s*\((paired and reachable|paired|reachable)\)\s*$", line, re.I)
        if not m:
            m = re.match(r"^(.+?):\s*([0-9a-f_]+)\s*\((paired and reachable|paired|reachable)\)\s*$", line, re.I)
        if m:
            status = m.group(3).lower()
            devices.append({
                "name": m.group(1).strip(),
                "id": m.group(2).strip(),
                "paired": "paired" in status,
                "reachable": "reachable" in status,
            })
    return devices


def kdec_paired_device() -> Optional[str]:
    """Return a paired+reachable device ID, preferring KDE_CONNECT_DEVICE_ID env override."""
    if KDEC_OVERRIDE_ID:
        return KDEC_OVERRIDE_ID
    cached = ds_load("kde_device", default={}).get("id")
    devs = kdec_list_devices()
    for d in devs:
        if d["paired"] and d["reachable"]:
            ds_save("kde_device", {"id": d["id"], "name": d["name"]})
            return d["id"]
    if cached:
        return cached
    return None


def kdec_ring() -> str:
    if not kdec_installed():
        return kdec_unavailable_message()
    dev = kdec_paired_device()
    if not dev:
        return kdec_unavailable_message()
    rc, out, err = _run(["-d", dev, "--ring"])
    if rc == 0:
        info = ds_load("kde_device", default={})
        name = info.get("name") or "your phone"
        return f"Ringing {name} now."
    return f"Couldn't ring it: {err or out or 'unknown error'}"


def kdec_send_sms(number: str, body: str) -> str:
    if not kdec_installed():
        return kdec_unavailable_message()
    dev = kdec_paired_device()
    if not dev:
        return kdec_unavailable_message()
    rc, out, err = _run(["-d", dev, "--send-sms", body, "--destination", number])
    if rc == 0:
        return f"SMS to {number} sent."
    return f"Couldn't send SMS: {err or out or 'unknown error'}"


def kdec_send_clipboard(text: str) -> str:
    if not kdec_installed():
        return kdec_unavailable_message()
    dev = kdec_paired_device()
    if not dev:
        return kdec_unavailable_message()
    rc, out, err = _run(["-d", dev, "--send-text", text])
    if rc == 0:
        return "Pushed to your phone's clipboard."
    return f"Couldn't push clipboard: {err or out or 'unknown error'}"


def kdec_share_file(path: str) -> str:
    if not kdec_installed():
        return kdec_unavailable_message()
    dev = kdec_paired_device()
    if not dev:
        return kdec_unavailable_message()
    if not os.path.isfile(path):
        return f"File not found: {path}"
    rc, out, err = _run(["-d", dev, "--share", path], timeout=30)
    if rc == 0:
        return f"Sent {os.path.basename(path)} to your phone."
    return f"Couldn't send file: {err or out or 'unknown error'}"


def kdec_status() -> str:
    if not kdec_installed():
        return kdec_unavailable_message()
    devs = kdec_list_devices()
    if not devs:
        return "KDE Connect is installed but I see no devices yet. Pair your phone first."
    lines = ["KDE Connect devices:"]
    for d in devs:
        flags = []
        if d["paired"]: flags.append("paired")
        if d["reachable"]: flags.append("reachable")
        lines.append(f"  - {d['name']} ({', '.join(flags) or 'unpaired/offline'})")
    return "\n".join(lines)


def _resolve_contact(phrase: str) -> Optional[str]:
    """Look up a contact name -> phone number via memory.data_store 'contacts'."""
    contacts = ds_load("contacts", default={})
    if phrase in contacts:
        return contacts[phrase]
    lower = phrase.lower().strip()
    for name, num in contacts.items():
        if name.lower() == lower:
            return num
    return None


def kdec_command(user_text: str) -> Optional[str]:
    """Parse 'ring my phone', 'find my phone', 'text X Y', etc. Return None if not a phone command."""
    lt = user_text.lower().strip()

    if re.search(r"\b(ring|find|locate|where\s+is)\s+my\s+phone\b", lt) or re.fullmatch(r"\s*ring\s+phone\s*", lt):
        return kdec_ring()

    if re.search(r"\b(?:show|list|status\s+of)\s+(?:my\s+)?(?:kde\s*connect|paired\s+devices|phone\s+devices)\b", lt) or re.fullmatch(r"\s*kde\s*connect\s+status\s*", lt):
        return kdec_status()

    m_clip = re.search(r"^(?:send|push|share)\s+(?:this\s+|that\s+)?(?:to\s+)?(?:my\s+)?phone(?:\s+clipboard)?\s*[:\-]?\s*(.*)$", lt)
    if m_clip:
        text_to_send = m_clip.group(1).strip() or _last_clipboard_text()
        if not text_to_send:
            return "What should I send to your phone?"
        return kdec_send_clipboard(text_to_send)

    m_text = re.search(
        r"^(?:text|message|sms)\s+(.+?)\s+(?:saying\s+|that\s+|telling\s+(?:them|him|her)\s+(?:that\s+)?)?[\"']?(.+?)[\"']?\s*$",
        lt,
    )
    if m_text:
        recipient_phrase, body = m_text.group(1).strip(), m_text.group(2).strip()
        number = _resolve_contact(recipient_phrase)
        if not number:
            return (
                f"I don't have a number for '{recipient_phrase}'. Add it first: "
                f"open zendaya_data\\contacts.json and add \"{recipient_phrase}\": \"+1234567890\"."
            )
        return kdec_send_sms(number, body)

    m_share = re.search(r"^(?:share|send)\s+(?:the\s+file\s+)?[\"']?([A-Za-z]:\\[^\"']+|/[^\"']+)[\"']?\s+(?:to\s+)?(?:my\s+)?phone\s*$", user_text, re.I)
    if m_share:
        return kdec_share_file(m_share.group(1).strip())

    return None


def _last_clipboard_text() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or ""
    except Exception:
        return ""
