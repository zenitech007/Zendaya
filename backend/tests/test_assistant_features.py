"""Unit tests for zendaya_assistant_features."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest


# ─── Skeleton import smoke test ────────────────────────────────────────────


def test_module_imports_and_exposes_public_api(tmp_data_dir):
    import zendaya_assistant_features as aaf

    assert callable(aaf.set_notifier)
    assert callable(aaf.start)
    assert callable(aaf.stop)
    assert callable(aaf.try_handle)


def test_try_handle_returns_none_for_unrelated_input(tmp_data_dir):
    import zendaya_assistant_features as aaf

    assert aaf.try_handle("what time is it") is None
    assert aaf.try_handle("") is None


# ─── Storage round-trip ────────────────────────────────────────────────────


def test_state_round_trip(tmp_data_dir):
    import zendaya_assistant_features as aaf

    state = aaf._load_state()
    assert state == {"alarms": [], "timers": [], "lists": {}, "next_alarm_id": 1, "next_timer_id": 1}

    state["alarms"].append({"id": 1, "kind": "one_shot", "trigger": "2030-01-01T07:00:00",
                            "label": "alarm", "created_at": 0.0, "active": True})
    state["next_alarm_id"] = 2
    aaf._save_state(state)

    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["id"] == 1
    assert reloaded["next_alarm_id"] == 2


def test_corrupt_state_file_is_renamed_and_default_returned(tmp_data_dir):
    import zendaya_assistant_features as aaf

    (tmp_data_dir / "aaf_state.json").write_text("{not valid json", encoding="utf-8")

    state = aaf._load_state()
    assert state == {"alarms": [], "timers": [], "lists": {}, "next_alarm_id": 1, "next_timer_id": 1}

    bad_files = list(tmp_data_dir.glob("aaf_state.bad-*.json"))
    assert len(bad_files) == 1, f"expected one .bad-* file, got {bad_files}"
