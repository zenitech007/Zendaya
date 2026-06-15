"""Unit tests for skills.assistant_features."""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

import pytest


# ─── Skeleton import smoke test ────────────────────────────────────────────


def test_module_imports_and_exposes_public_api(tmp_data_dir):
    import skills.assistant_features as aaf

    assert callable(aaf.set_notifier)
    assert callable(aaf.start)
    assert callable(aaf.stop)
    assert callable(aaf.try_handle)


def test_try_handle_returns_none_for_unrelated_input(tmp_data_dir):
    import skills.assistant_features as aaf

    assert aaf.try_handle("what time is it") is None
    assert aaf.try_handle("") is None


# ─── Storage round-trip ────────────────────────────────────────────────────


def test_state_round_trip(tmp_data_dir):
    import skills.assistant_features as aaf

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
    import skills.assistant_features as aaf

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
    import skills.assistant_features as aaf

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
    import skills.assistant_features as aaf
    assert aaf.parse_timer_command(utterance) is None


def test_create_timer_persists_record(tmp_data_dir):
    import skills.assistant_features as aaf

    reply = aaf._handle_timer("create", {"duration_seconds": 60, "label": "1-minute timer"})
    assert "timer" in reply.lower()

    state = aaf._load_state()
    assert len(state["timers"]) == 1
    rec = state["timers"][0]
    assert rec["id"] == 1
    assert rec["duration_seconds"] == 60
    assert rec["active"] is True


def test_list_timers_with_no_timers(tmp_data_dir):
    import skills.assistant_features as aaf
    reply = aaf._handle_timer("list", {})
    assert "no" in reply.lower() and "timer" in reply.lower()


def test_cancel_timer_by_index(tmp_data_dir):
    import skills.assistant_features as aaf

    aaf._handle_timer("create", {"duration_seconds": 60, "label": "1-min"})
    aaf._handle_timer("create", {"duration_seconds": 120, "label": "2-min"})

    reply = aaf._handle_timer("cancel", {"index": 1})
    assert "cancel" in reply.lower()

    state = aaf._load_state()
    active = [t for t in state["timers"] if t["active"]]
    assert len(active) == 1
    assert active[0]["duration_seconds"] == 120


def test_cancel_timer_out_of_range(tmp_data_dir):
    import skills.assistant_features as aaf
    reply = aaf._handle_timer("cancel", {"index": 5})
    assert "only" in reply.lower() or "no" in reply.lower()


# ─── Alarm family ──────────────────────────────────────────────────────────


def test_parse_alarm_one_shot_simple(tmp_data_dir):
    import skills.assistant_features as aaf
    result = aaf.parse_alarm_command("set an alarm for 7am tomorrow")
    assert result is not None
    action, payload = result
    assert action == "create"
    assert payload["kind"] == "one_shot"
    # trigger is an ISO datetime string in the future
    dt = datetime.fromisoformat(payload["trigger"])
    assert dt > datetime.now()
    assert dt.hour == 7 and dt.minute == 0


@pytest.mark.parametrize("utterance, expected_cron", [
    ("alarm every weekday at 7am",        "0 7 * * 1-5"),
    ("set an alarm every sunday at 9pm",  "0 21 * * 0"),
    ("alarm every 15 minutes",            "*/15 * * * *"),
    ("alarm every monday at 8:30am",      "30 8 * * 1"),
])
def test_parse_alarm_cron_table(utterance, expected_cron, tmp_data_dir):
    import skills.assistant_features as aaf
    result = aaf.parse_alarm_command(utterance)
    assert result is not None, f"expected match for {utterance!r}"
    action, payload = result
    assert action == "create"
    assert payload["kind"] == "cron"
    assert payload["trigger"] == expected_cron


def test_parse_alarm_unrecognised_returns_help(tmp_data_dir):
    import skills.assistant_features as aaf
    result = aaf.parse_alarm_command("set an alarm on the next blue moon")
    assert result is not None
    action, payload = result
    assert action == "error"
    assert "try" in payload["message"].lower()


@pytest.mark.parametrize("utterance", [
    "set timer for 5 minutes",
    "add eggs to shopping",
    "what's the weather",
    "",
])
def test_parse_alarm_negative(utterance, tmp_data_dir):
    import skills.assistant_features as aaf
    assert aaf.parse_alarm_command(utterance) is None


def test_create_one_shot_alarm_persists(tmp_data_dir):
    import skills.assistant_features as aaf
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    reply = aaf._handle_alarm("create", {"kind": "one_shot", "trigger": future, "label": "alarm in 1h"})
    assert "alarm" in reply.lower()
    state = aaf._load_state()
    assert len(state["alarms"]) == 1
    assert state["alarms"][0]["kind"] == "one_shot"


def test_create_cron_alarm_persists(tmp_data_dir):
    import skills.assistant_features as aaf
    reply = aaf._handle_alarm("create", {"kind": "cron", "trigger": "0 7 * * 1-5", "label": "weekday 7am"})
    assert "alarm" in reply.lower()
    state = aaf._load_state()
    assert state["alarms"][0]["kind"] == "cron"
    assert state["alarms"][0]["trigger"] == "0 7 * * 1-5"


def test_list_alarms_includes_both_kinds(tmp_data_dir):
    import skills.assistant_features as aaf
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    aaf._handle_alarm("create", {"kind": "one_shot", "trigger": future, "label": "one-shot"})
    aaf._handle_alarm("create", {"kind": "cron", "trigger": "0 7 * * 1-5", "label": "weekday 7am"})
    reply = aaf._handle_alarm("list", {})
    assert "1." in reply and "2." in reply


def test_cancel_alarm_by_index(tmp_data_dir):
    import skills.assistant_features as aaf
    future = (datetime.now() + timedelta(hours=1)).isoformat()
    aaf._handle_alarm("create", {"kind": "one_shot", "trigger": future, "label": "one-shot"})
    aaf._handle_alarm("create", {"kind": "cron", "trigger": "0 7 * * 1-5", "label": "weekday"})
    aaf._handle_alarm("cancel", {"index": 1})
    state = aaf._load_state()
    active = [a for a in state["alarms"] if a["active"]]
    assert len(active) == 1 and active[0]["kind"] == "cron"


# ─── List family ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("utterance, expected_list, expected_item", [
    ("add milk to shopping list",            "shopping", "milk"),
    ("add eggs to the shopping list",        "shopping", "eggs"),
    ("put bread on my groceries list",       "groceries", "bread"),
    ("add finish the report to my todo list", "todo", "finish the report"),
])
def test_parse_list_add_explicit(utterance, expected_list, expected_item, tmp_data_dir):
    import skills.assistant_features as aaf
    result = aaf.parse_list_command(utterance)
    assert result is not None
    action, payload = result
    assert action == "add"
    assert payload["list_name"] == expected_list
    assert payload["item"].strip() == expected_item


@pytest.mark.parametrize("utterance, expected_list", [
    ("add milk",                "shopping"),    # grocery keyword
    ("add eggs",                "shopping"),
    ("add finish the report",   "todo"),
    ("add call mom",            "todo"),
])
def test_parse_list_add_default(utterance, expected_list, tmp_data_dir):
    import skills.assistant_features as aaf
    action, payload = aaf.parse_list_command(utterance)
    assert action == "add"
    assert payload["list_name"] == expected_list


@pytest.mark.parametrize("utterance, expected_list", [
    ("what's on my shopping list", "shopping"),
    ("read my todo list",          "todo"),
    ("show me my packing list",    "packing"),
])
def test_parse_list_read(utterance, expected_list, tmp_data_dir):
    import skills.assistant_features as aaf
    action, payload = aaf.parse_list_command(utterance)
    assert action == "read"
    assert payload["list_name"] == expected_list


def test_parse_list_remove(tmp_data_dir):
    import skills.assistant_features as aaf
    action, payload = aaf.parse_list_command("remove milk from shopping list")
    assert action == "remove"
    assert payload["list_name"] == "shopping"
    assert payload["item"] == "milk"


def test_parse_list_mark_done(tmp_data_dir):
    import skills.assistant_features as aaf
    action, payload = aaf.parse_list_command("mark milk done on shopping list")
    assert action == "mark_done"
    assert payload["list_name"] == "shopping"
    assert payload["item"] == "milk"


def test_parse_list_negative(tmp_data_dir):
    import skills.assistant_features as aaf
    assert aaf.parse_list_command("set alarm 7am") is None
    assert aaf.parse_list_command("what time is it") is None
    assert aaf.parse_list_command("") is None


def test_list_handler_round_trip(tmp_data_dir):
    import skills.assistant_features as aaf
    aaf._handle_list("add", {"list_name": "shopping", "item": "milk"})
    aaf._handle_list("add", {"list_name": "shopping", "item": "eggs"})

    reply = aaf._handle_list("read", {"list_name": "shopping"})
    assert "milk" in reply and "eggs" in reply

    aaf._handle_list("mark_done", {"list_name": "shopping", "item": "milk"})
    state = aaf._load_state()
    items = state["lists"]["shopping"]
    milk = next(i for i in items if i["text"] == "milk")
    assert milk["done"] is True

    aaf._handle_list("remove", {"list_name": "shopping", "item": "eggs"})
    state = aaf._load_state()
    texts = [i["text"] for i in state["lists"]["shopping"]]
    assert "eggs" not in texts


def test_list_remove_nonexistent_item_is_friendly(tmp_data_dir):
    import skills.assistant_features as aaf
    aaf._handle_list("add", {"list_name": "shopping", "item": "milk"})
    reply = aaf._handle_list("remove", {"list_name": "shopping", "item": "spaghetti"})
    assert "couldn't find" in reply.lower() or "not on" in reply.lower()


def test_list_read_empty_list_is_friendly(tmp_data_dir):
    import skills.assistant_features as aaf
    reply = aaf._handle_list("read", {"list_name": "nonexistent"})
    assert "empty" in reply.lower() or "no items" in reply.lower()


# ─── Scheduler + dispatcher ────────────────────────────────────────────────


def test_start_prunes_expired_one_shots(tmp_data_dir):
    import skills.assistant_features as aaf
    state = aaf._load_state()
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    state["alarms"].append({
        "id": 1, "kind": "one_shot", "trigger": past,
        "label": "stale", "created_at": 0.0, "active": True,
    })
    state["next_alarm_id"] = 2
    aaf._save_state(state)

    aaf.start()
    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is False
    aaf.stop()


def test_start_keeps_active_cron_alarms(tmp_data_dir):
    import skills.assistant_features as aaf
    state = aaf._load_state()
    state["alarms"].append({
        "id": 1, "kind": "cron", "trigger": "0 7 * * 1-5",
        "label": "weekday 7am", "created_at": time.time(), "active": True,
    })
    state["next_alarm_id"] = 2
    aaf._save_state(state)

    aaf.start()
    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is True
    aaf.stop()


def test_fire_alarm_calls_notifier_and_deactivates_one_shot(tmp_data_dir, fake_notifier):
    import skills.assistant_features as aaf
    speak, toast, calls = fake_notifier
    aaf.set_notifier(speak, toast)

    state = aaf._load_state()
    rec = {
        "id": 1, "kind": "one_shot", "trigger": datetime.now().isoformat(),
        "label": "test alarm", "created_at": time.time(), "active": True,
    }
    state["alarms"].append(rec)
    aaf._save_state(state)

    aaf._fire_alarm(rec["id"])

    assert len(calls["speak"]) == 1 and "test alarm" in calls["speak"][0]
    assert len(calls["toast"]) == 1
    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is False


def test_fire_cron_alarm_keeps_active(tmp_data_dir, fake_notifier):
    import skills.assistant_features as aaf
    speak, toast, calls = fake_notifier
    aaf.set_notifier(speak, toast)

    state = aaf._load_state()
    state["alarms"].append({
        "id": 1, "kind": "cron", "trigger": "0 7 * * 1-5",
        "label": "cron", "created_at": time.time(), "active": True,
    })
    aaf._save_state(state)

    aaf._fire_alarm(1)

    reloaded = aaf._load_state()
    assert reloaded["alarms"][0]["active"] is True


def test_fire_timer_deactivates(tmp_data_dir, fake_notifier):
    import skills.assistant_features as aaf
    speak, toast, calls = fake_notifier
    aaf.set_notifier(speak, toast)

    state = aaf._load_state()
    state["timers"].append({
        "id": 1, "fire_at": datetime.now().isoformat(),
        "duration_seconds": 60, "label": "1-min timer",
        "created_at": time.time(), "active": True,
    })
    aaf._save_state(state)

    aaf._fire_timer(1)

    reloaded = aaf._load_state()
    assert reloaded["timers"][0]["active"] is False
    assert "1-min timer" in calls["speak"][0]


def test_fire_handles_missing_record_silently(tmp_data_dir, fake_notifier):
    """If a record was cancelled mid-flight, the fire callback must not crash."""
    import skills.assistant_features as aaf
    speak, toast, _ = fake_notifier
    aaf.set_notifier(speak, toast)
    # No record with id=999 — should be a no-op, not an exception.
    aaf._fire_alarm(999)
    aaf._fire_timer(999)


def test_pruning_drops_old_completed_list_items(tmp_data_dir):
    import skills.assistant_features as aaf
    old_ts = time.time() - (31 * 24 * 3600)
    state = aaf._load_state()
    state["lists"]["shopping"] = [
        {"text": "old done milk", "done": True, "added_at": old_ts},
        {"text": "fresh active eggs", "done": False, "added_at": time.time()},
    ]
    aaf._save_state(state)

    aaf.start()
    reloaded = aaf._load_state()
    texts = [i["text"] for i in reloaded["lists"]["shopping"]]
    assert "old done milk" not in texts
    assert "fresh active eggs" in texts
    aaf.stop()


def test_try_handle_routes_to_correct_family(tmp_data_dir, fake_notifier):
    import skills.assistant_features as aaf
    speak, toast, _ = fake_notifier
    aaf.set_notifier(speak, toast)

    assert aaf.try_handle("set timer for 5 minutes") is not None
    assert aaf.try_handle("set an alarm for 7am tomorrow") is not None
    assert aaf.try_handle("add milk to shopping") is not None
    assert aaf.try_handle("what time is it") is None
