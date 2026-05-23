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


# ─── Timer family ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("utterance, expected_seconds", [
    ("set a timer for 10 minutes", 600),
    ("set timer for 5 min", 300),
    ("timer 90 seconds", 90),
    ("set a timer for 2 hours", 7200),
    ("timer 1 hr", 3600),
])
def test_parse_timer_command_positive(utterance, expected_seconds, tmp_data_dir):
    import zendaya_assistant_features as aaf

    action, payload = aaf.parse_timer_command(utterance)
    assert action == "create"
    assert payload["duration_seconds"] == expected_seconds


@pytest.mark.parametrize("utterance", [
    "what time is it",
    "set an alarm for 7am",
    "add milk to shopping",
    "",
])
def test_parse_timer_command_negative(utterance, tmp_data_dir):
    import zendaya_assistant_features as aaf
    assert aaf.parse_timer_command(utterance) is None


def test_create_timer_persists_record(tmp_data_dir):
    import zendaya_assistant_features as aaf

    reply = aaf._handle_timer("create", {"duration_seconds": 60, "label": "1-minute timer"})
    assert "timer" in reply.lower()

    state = aaf._load_state()
    assert len(state["timers"]) == 1
    rec = state["timers"][0]
    assert rec["id"] == 1
    assert rec["duration_seconds"] == 60
    assert rec["active"] is True


def test_list_timers_with_no_timers(tmp_data_dir):
    import zendaya_assistant_features as aaf
    reply = aaf._handle_timer("list", {})
    assert "no" in reply.lower() and "timer" in reply.lower()


def test_cancel_timer_by_index(tmp_data_dir):
    import zendaya_assistant_features as aaf

    aaf._handle_timer("create", {"duration_seconds": 60, "label": "1-min"})
    aaf._handle_timer("create", {"duration_seconds": 120, "label": "2-min"})

    reply = aaf._handle_timer("cancel", {"index": 1})
    assert "cancel" in reply.lower()

    state = aaf._load_state()
    active = [t for t in state["timers"] if t["active"]]
    assert len(active) == 1
    assert active[0]["duration_seconds"] == 120


def test_cancel_timer_out_of_range(tmp_data_dir):
    import zendaya_assistant_features as aaf
    reply = aaf._handle_timer("cancel", {"index": 5})
    assert "only" in reply.lower() or "no" in reply.lower()
