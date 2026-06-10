"""
zendaya_journal — daily activity log + AI-summarized day.

Polls a small set of "watched" folders, writes one append-only JSON file per
day at zendaya_logs/journal/YYYY-MM-DD.json with file-touch events. Asks
Gemini to turn the day's events + git status into prose on demand.

Default watched roots: ~/Desktop, ~/Documents, ~/Zendaya  (each capped by depth + size).

Public API:
    start() -> None
    stop()  -> None
    record(kind, text, meta=None) -> None         # generic event hook
    today_path() -> Path
    summarize_today() -> str
    summarize_range(days_back=1) -> str
    parse_journal_command(user_text) -> Optional[dict]
    handle_journal_command(parsed) -> str
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


_BACKEND_DIR = Path(__file__).resolve().parent
_LOGS_DIR = _BACKEND_DIR.parent / "zendaya_logs" / "journal"
_LOGS_DIR.mkdir(parents=True, exist_ok=True)

_HOME = Path(os.path.expanduser("~"))
_WATCH_ROOTS: List[Path] = [
    _HOME / "Desktop",
    _HOME / "Documents",
    _HOME / "Zendaya",
]

_TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".json",
    ".md", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".sh", ".bat",
    ".rs", ".go", ".rb", ".php", ".java", ".cpp", ".c", ".h", ".hpp",
    ".xml", ".sql",
}
_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", "dist", "build",
    ".next", ".cache", ".idea", ".vscode", "target", "zendaya_logs",
}
_MAX_DEPTH = 6
_POLL_S = 30.0  # journal cadence — 30s is plenty for "what did I do today"

_LOCK = threading.Lock()
_THREAD: Optional[threading.Thread] = None
_STOP = threading.Event()
_LAST_SEEN: Dict[str, float] = {}    # absolute path → mtime last logged
_FIRST_PASS = True                    # don't log every existing file as "touched"


def _z():
    import zendaya as _zmod
    return _zmod


def _today() -> date:
    return datetime.now().date()


def today_path() -> Path:
    return _LOGS_DIR / f"{_today().isoformat()}.json"


def _path_for(d: date) -> Path:
    return _LOGS_DIR / f"{d.isoformat()}.json"


def _append(event: Dict[str, Any]) -> None:
    p = today_path()
    try:
        existing: List[Dict[str, Any]] = []
        if p.is_file():
            try:
                existing = json.loads(p.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
            except Exception:
                existing = []
        existing.append(event)
        p.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[journal] couldn't append: {e}")


def record(kind: str, text: str, meta: Optional[Dict[str, Any]] = None) -> None:
    _append({"kind": kind, "text": text, "meta": meta or {}, "ts": time.time()})


# ---------------------------------------------------------------------------
# File walker — coarse, polling-based
# ---------------------------------------------------------------------------

def _walk(root: Path, max_depth: int) -> List[Path]:
    found: List[Path] = []
    if not root.is_dir():
        return found
    root_str = str(root)
    base_depth = root_str.count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count(os.sep) - base_depth
        if depth > max_depth:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in _TEXT_EXTS:
                continue
            full = Path(dirpath) / name
            try:
                st = full.stat()
            except OSError:
                continue
            if st.st_size > 1_500_000:
                continue
            found.append(full)
    return found


def _scan_once() -> int:
    global _FIRST_PASS
    n_logged = 0
    for root in _WATCH_ROOTS:
        for full in _walk(root, _MAX_DEPTH):
            try:
                m = full.stat().st_mtime
            except OSError:
                continue
            key = str(full)
            prev = _LAST_SEEN.get(key)
            _LAST_SEEN[key] = m
            if _FIRST_PASS:
                # Initial pass: prime the table without flooding the journal.
                continue
            if prev is None:
                # New file appeared.
                record("file_created", str(full))
                n_logged += 1
            elif m - prev > 1.0:
                record("file_modified", str(full))
                n_logged += 1
    _FIRST_PASS = False
    return n_logged


def _loop() -> None:
    while not _STOP.is_set():
        try:
            _scan_once()
        except Exception as e:
            print(f"[journal] scan error: {e}")
        _STOP.wait(_POLL_S)


def start() -> Optional[threading.Thread]:
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return _THREAD
    _STOP.clear()
    _THREAD = threading.Thread(target=_loop, daemon=True, name="zendaya-journal")
    _THREAD.start()
    return _THREAD


def stop() -> None:
    _STOP.set()


# ---------------------------------------------------------------------------
# Read + summarize
# ---------------------------------------------------------------------------

def load_day(d: date) -> List[Dict[str, Any]]:
    p = _path_for(d)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _condense(events: List[Dict[str, Any]], max_paths: int = 30) -> Dict[str, Any]:
    """Reduce raw events to a compact bag for the LLM."""
    file_events: Dict[str, int] = {}
    other: List[str] = []
    for e in events:
        kind = e.get("kind", "")
        text = e.get("text", "")
        if kind in ("file_modified", "file_created"):
            file_events[text] = file_events.get(text, 0) + 1
        else:
            other.append(f"{kind}: {text[:200]}")
    # Top edited files by frequency.
    top = sorted(file_events.items(), key=lambda kv: kv[1], reverse=True)[:max_paths]
    return {
        "edited_files": [{"path": p, "edits": n} for p, n in top],
        "total_file_events": sum(file_events.values()),
        "other_events": other[:40],
    }


def summarize_today() -> str:
    return summarize_range(days_back=0)


def summarize_range(days_back: int = 0) -> str:
    d = _today() - timedelta(days=days_back)
    events = load_day(d)
    if not events:
        return f"Journal for {d.isoformat()} is empty."
    summary = _condense(events)
    if summary["total_file_events"] == 0 and not summary["other_events"]:
        return f"Quiet day on {d.isoformat()} — no tracked activity."

    # Lazy Gemini — degrade to bullet listing if offline.
    try:
        z = _z()
        client = getattr(z, "_gemini_client", None)
        ready = getattr(z, "_GEMINI_READY", False)
    except Exception:
        client, ready = None, False

    if not (ready and client is not None):
        # Fallback: bullet listing.
        lines = [f"Journal for {d.isoformat()} (offline summary):"]
        lines.append(f"- Touched {summary['total_file_events']} file events across {len(summary['edited_files'])} files.")
        for ent in summary["edited_files"][:10]:
            lines.append(f"  - {ent['path']} ({ent['edits']} edits)")
        if summary["other_events"]:
            lines.append("- Other events:")
            for ev in summary["other_events"][:10]:
                lines.append(f"  - {ev}")
        return "\n".join(lines)

    prompt = (
        "You are summarizing the user's work day from a structured activity log. "
        "Output 3–6 short bullet points capturing what they likely worked on, in plain prose. "
        "Group related files (e.g. 'pet animation work in zendaya-pet/src/'). "
        "Don't list every file. Don't include a preamble or sign-off.\n\n"
        f"Date: {d.isoformat()}\n"
        f"Activity summary JSON:\n{json.dumps(summary, ensure_ascii=False, indent=2)}\n"
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        return f"Journal for {d.isoformat()}:\n{(response.text or '').strip()}"
    except Exception as e:
        return f"Journal for {d.isoformat()}: couldn't reach Gemini ({e})."


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

_TODAY_RE = re.compile(
    r"\b(?:what\s+(?:did|was)\s+i\s+(?:do|work|working)(?:\s+on)?\s+today|"
    r"summari[sz]e\s+(?:my\s+)?(?:day|today)|"
    r"daily\s+summary|"
    r"journal(?:\s+today)?)\b",
    re.IGNORECASE,
)
_YESTERDAY_RE = re.compile(
    r"\b(?:what\s+(?:did|was)\s+i\s+(?:do|work|working)\s+yesterday|"
    r"summari[sz]e\s+yesterday|"
    r"yesterday'?s?\s+journal)\b",
    re.IGNORECASE,
)


def parse_journal_command(user_text: str) -> Optional[Dict[str, Any]]:
    if not user_text:
        return None
    if _YESTERDAY_RE.search(user_text):
        return {"op": "summarize", "days_back": 1}
    if _TODAY_RE.search(user_text):
        return {"op": "summarize", "days_back": 0}
    return None


def handle_journal_command(parsed: Dict[str, Any]) -> str:
    if parsed.get("op") == "summarize":
        return summarize_range(days_back=int(parsed.get("days_back", 0)))
    return f"Unknown journal op: {parsed.get('op')}"
