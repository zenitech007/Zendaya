import json
import datetime
from pathlib import Path

LOG_DIR = Path("zendaya_logs")
LOG_FILE = LOG_DIR / "assistant_history.json"

def log_event(event_type: str, message: str, data: dict = None):
    """
    Appends an event to Zendaya's persistent history log.
    :param event_type: e.g., "greeting", "recovery", "emotion", "system_check"
    :param message: Human-readable summary
    :param data: Optional structured metadata
    """
    try:
        LOG_DIR.mkdir(exist_ok=True)
        history = []

        if LOG_FILE.exists():
            history = json.loads(LOG_FILE.read_text(encoding="utf-8"))

        entry = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": event_type,
            "message": message,
            "data": data or {},
        }

        history.append(entry)
        LOG_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"⚠️ Log write failed: {e}")

def get_recent_logs(limit: int = 5):
    """Retrieve the last N events for review."""
    if not LOG_FILE.exists():
        return []
    try:
        data = json.loads(LOG_FILE.read_text(encoding="utf-8"))
        return data[-limit:]
    except Exception:
        return []
