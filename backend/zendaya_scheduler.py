"""
zendaya_scheduler — durable Windows Task Scheduler wrapper.

A natural-language schedule like "every morning at 8" or "at 14:30 today" is
turned into a `schtasks /Create` invocation that runs a chosen command on the
local machine. Tasks are namespaced under `\\Zendaya\\` so we don't collide
with whatever else lives in Task Scheduler.

Public API:
    schedule_command(name, command, when) -> str   # stages confirm
    list_tasks()                          -> str
    delete_task(name)                     -> str   # stages confirm
    run_task_now(name)                    -> str

`when` accepts:
    "daily 08:00"
    "weekly mon 09:30"
    "once 2026-05-08 14:30"
    "every 30 minutes"
    "every hour"
    "startup"
    "logon"

Linux/macOS support is intentionally out of scope here — Zendaya runs on
Windows. The functions return a clear error on other platforms.
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import time
from datetime import datetime
from typing import Dict, Optional, Tuple

_TASK_PREFIX = r"\Zendaya"


def _is_windows() -> bool:
    return platform.system() == "Windows"


def _schtasks() -> Optional[str]:
    return shutil.which("schtasks") or "schtasks"


def _mem() -> Optional[dict]:
    try:
        import zendaya as _z
        return getattr(_z, "MEM", None)
    except Exception:
        return None


def _full_name(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._\- ]+", "_", name).strip()
    return f"{_TASK_PREFIX}\\{safe or 'task'}"


def _parse_when(when: str) -> Tuple[list, str]:
    """Translate a natural schedule string into schtasks /SC ... flags."""
    s = when.strip().lower()

    # daily HH:MM
    m = re.match(r"^daily\s+(\d{1,2}):(\d{2})$", s)
    if m:
        return ["/SC", "DAILY", "/ST", f"{int(m.group(1)):02d}:{m.group(2)}"], f"daily at {m.group(1)}:{m.group(2)}"

    # weekly mon|tue|... HH:MM
    m = re.match(r"^weekly\s+(mon|tue|wed|thu|fri|sat|sun)[a-z]*\s+(\d{1,2}):(\d{2})$", s)
    if m:
        day_map = {"mon": "MON", "tue": "TUE", "wed": "WED", "thu": "THU", "fri": "FRI", "sat": "SAT", "sun": "SUN"}
        d = day_map[m.group(1)]
        return (
            ["/SC", "WEEKLY", "/D", d, "/ST", f"{int(m.group(2)):02d}:{m.group(3)}"],
            f"every {d} at {m.group(2)}:{m.group(3)}",
        )

    # once YYYY-MM-DD HH:MM
    m = re.match(r"^once\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})$", s)
    if m:
        try:
            datetime.strptime(f"{m.group(1)} {int(m.group(2)):02d}:{m.group(3)}", "%Y-%m-%d %H:%M")
        except ValueError:
            return [], "Bad once date — use 'once YYYY-MM-DD HH:MM'."
        return (
            ["/SC", "ONCE", "/SD", m.group(1), "/ST", f"{int(m.group(2)):02d}:{m.group(3)}"],
            f"once on {m.group(1)} at {m.group(2)}:{m.group(3)}",
        )

    # every N minutes / every hour
    m = re.match(r"^every\s+(\d+)\s+minutes?$", s)
    if m:
        n = max(1, min(int(m.group(1)), 1439))
        return ["/SC", "MINUTE", "/MO", str(n)], f"every {n} minutes"
    if s == "every hour":
        return ["/SC", "HOURLY"], "every hour"

    if s == "startup":
        return ["/SC", "ONSTART"], "at system startup"
    if s == "logon":
        return ["/SC", "ONLOGON"], "at user logon"

    return [], f"I didn't understand schedule: {when!r}. Try 'daily 08:00' or 'every 30 minutes'."


def schedule_command(name: str, command: str, when: str) -> str:
    if not _is_windows():
        return "Scheduling is only wired up for Windows."
    if not name or not command or not when:
        return "I need a task name, a command, and a schedule."
    flags, human = _parse_when(when)
    if not flags:
        return human
    full = _full_name(name)

    mem = _mem()
    if mem is None:
        return "Memory isn't available — can't stage the task."

    mem["pending_confirm"] = {
        "action": "schedule_task",
        "name": full,
        "human": human,
        "command": command,
        "flags": flags,
        "ts": time.time(),
    }
    return (
        f"Ready to schedule **{full}** to run «{command}» {human}. "
        "Say yes to create the task, or no to cancel."
    )


def confirm_schedule(pending: Dict) -> str:
    full = pending.get("name") or ""
    command = pending.get("command") or ""
    flags = pending.get("flags") or []
    if not full or not command or not flags:
        return "Lost the schedule details."
    schtasks = _schtasks()
    args = [schtasks, "/Create", "/TN", full, "/TR", command, "/F", *flags]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30, shell=False)
    except Exception as e:
        return f"schtasks failed: {e}"
    if proc.returncode != 0:
        return f"Couldn't create task: {(proc.stderr or proc.stdout).strip()[:1200]}"
    return f"✅ Scheduled {full}."


def list_tasks() -> str:
    if not _is_windows():
        return "Scheduling is only wired up for Windows."
    schtasks = _schtasks()
    try:
        proc = subprocess.run(
            [schtasks, "/Query", "/FO", "LIST", "/V"],
            capture_output=True, text=True, timeout=30, shell=False,
        )
    except Exception as e:
        return f"schtasks failed: {e}"
    if proc.returncode != 0:
        return f"schtasks error: {(proc.stderr or '').strip()[:600]}"

    lines = proc.stdout.splitlines()
    blocks: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if not line.strip():
            if cur:
                blocks.append(cur)
                cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)

    ours = []
    for block in blocks:
        joined = "\n".join(block)
        if _TASK_PREFIX.lower() in joined.lower():
            name = next((l.split(":", 1)[1].strip() for l in block if l.lower().startswith("taskname:")), "?")
            nxt = next((l.split(":", 1)[1].strip() for l in block if l.lower().startswith("next run time:")), "?")
            cmd = next((l.split(":", 1)[1].strip() for l in block if l.lower().startswith("task to run:")), "?")
            ours.append(f"- {name}  →  next: {nxt}  ({cmd})")
    if not ours:
        return f"No Zendaya tasks scheduled (looking under {_TASK_PREFIX}\\)."
    return "\n".join(ours)


def delete_task(name: str) -> str:
    if not _is_windows():
        return "Scheduling is only wired up for Windows."
    full = _full_name(name) if not name.startswith(_TASK_PREFIX) else name
    mem = _mem()
    if mem is None:
        return "Memory isn't available — can't stage the deletion."
    mem["pending_confirm"] = {
        "action": "schedule_delete",
        "name": full,
        "ts": time.time(),
    }
    return f"Ready to delete scheduled task **{full}**. Say yes to confirm."


def confirm_delete(pending: Dict) -> str:
    full = pending.get("name") or ""
    if not full:
        return "Lost the task name."
    schtasks = _schtasks()
    try:
        proc = subprocess.run(
            [schtasks, "/Delete", "/TN", full, "/F"],
            capture_output=True, text=True, timeout=30, shell=False,
        )
    except Exception as e:
        return f"schtasks failed: {e}"
    if proc.returncode != 0:
        return f"Couldn't delete: {(proc.stderr or proc.stdout).strip()[:600]}"
    return f"Deleted {full}."


def run_task_now(name: str) -> str:
    if not _is_windows():
        return "Scheduling is only wired up for Windows."
    full = _full_name(name) if not name.startswith(_TASK_PREFIX) else name
    schtasks = _schtasks()
    try:
        proc = subprocess.run(
            [schtasks, "/Run", "/TN", full],
            capture_output=True, text=True, timeout=30, shell=False,
        )
    except Exception as e:
        return f"schtasks failed: {e}"
    if proc.returncode != 0:
        return f"Couldn't run: {(proc.stderr or proc.stdout).strip()[:600]}"
    return f"Triggered {full}."
