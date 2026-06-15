"""
memory.data_store.py
=====================
Atomic JSON persistence for Zendaya's user data:
alarms, timers, lists, routines, smart-device cache.

Files live in C:\\Users\\IKA\\Zendaya\\zendaya_data\\
"""

import json
import os
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).parent.parent / "zendaya_data"
DATA_DIR.mkdir(exist_ok=True)


def _path(name: str) -> Path:
    if not name.endswith(".json"):
        name = name + ".json"
    return DATA_DIR / name


def load(name: str, default: Any = None) -> Any:
    p = _path(name)
    if not p.exists():
        return default if default is not None else {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"(data_store: failed to load {name}: {e})")
        return default if default is not None else {}


def save(name: str, obj: Any) -> bool:
    p = _path(name)
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, p)
        return True
    except Exception as e:
        print(f"(data_store: failed to save {name}: {e})")
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False
