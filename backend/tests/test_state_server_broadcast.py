"""Unit tests for the broadcast loop and decimation logic in server.state_server."""
from __future__ import annotations

import time

import pytest


@pytest.fixture(autouse=True)
def _reset_state_server():
    """Reset module-level state between tests."""
    import server.state_server as ss

    ss._MOUTH = {"level": 0.0, "ts": 0.0}
    ss._VISEMES = {"weights": {"aa": 0, "ih": 0, "ee": 0, "oh": 0, "ou": 0}, "ts": 0.0}
    ss._BODY = {"action": "", "ts": 0.0}
    if hasattr(ss, "_BROADCAST_LAST_SENT"):
        ss._BROADCAST_LAST_SENT.clear()
    yield


def test_collect_tick_includes_amplitude_when_changed():
    import server.state_server as ss

    ss.set_amplitude(0.42)
    tick = ss._collect_tick()
    assert any("amplitude" in m for m in tick), f"expected amplitude in {tick}"
    sent = next(m for m in tick if "amplitude" in m)
    assert sent["amplitude"] == pytest.approx(0.42, abs=0.001)


def test_collect_tick_decimates_unchanged_amplitude():
    import server.state_server as ss

    ss.set_amplitude(0.5)
    _ = ss._collect_tick()  # marks 0.5 as sent
    ss.set_amplitude(0.503)  # within 0.005 delta
    tick = ss._collect_tick()
    assert not any("amplitude" in m for m in tick), f"amplitude should be decimated; got {tick}"


def test_collect_tick_includes_visemes_when_changed():
    import server.state_server as ss

    ss.set_visemes({"aa": 0.5, "ih": 0, "ee": 0, "oh": 0, "ou": 0})
    tick = ss._collect_tick()
    assert any("visemes" in m for m in tick)
    sent = next(m for m in tick if "visemes" in m)
    assert sent["visemes"]["aa"] == pytest.approx(0.5)


def test_collect_tick_decimates_unchanged_visemes():
    import server.state_server as ss

    ss.set_visemes({"aa": 0.5, "ih": 0, "ee": 0, "oh": 0, "ou": 0})
    _ = ss._collect_tick()
    ss.set_visemes({"aa": 0.505, "ih": 0, "ee": 0, "oh": 0, "ou": 0})  # within 0.01
    tick = ss._collect_tick()
    assert not any("visemes" in m for m in tick)


def test_collect_tick_includes_telemetry_with_provider():
    import server.state_server as ss

    fake = {"cpu": 21.4, "mem": 58.2, "mic_level": 0.0, "mood": "neutral",
            "vision_active": False, "gestures_active": False,
            "hud_enabled": True, "online": True,
            "user_name": "Ikenna", "language": "english",
            "last_gesture": {"name": "none", "ts": 0.0}}
    ss.set_telemetry_provider(lambda: dict(fake))
    tick = ss._collect_tick()
    assert any("telemetry" in m for m in tick)
    sent = next(m for m in tick if "telemetry" in m)
    assert sent["telemetry"]["cpu"] == pytest.approx(21.4)
    assert sent["telemetry"]["mood"] == "neutral"


def test_collect_tick_telemetry_null_on_provider_exception():
    import server.state_server as ss

    def boom():
        raise RuntimeError("intentional")
    ss.set_telemetry_provider(boom)
    tick = ss._collect_tick()
    assert any("telemetry" in m for m in tick)
    sent = next(m for m in tick if "telemetry" in m)
    assert sent["telemetry"] is None


def test_set_body_action_valid_value_broadcasts_then_resets():
    import server.state_server as ss

    ss.set_body_action("nod")
    tick = ss._collect_tick()
    assert any("body_action" in m for m in tick)
    sent = next(m for m in tick if "body_action" in m)
    assert sent["body_action"] == "nod"
    # After collect, in-memory value is "" so a fresh nod is broadcast as a fresh event
    assert ss._BODY["action"] == ""


def test_set_body_action_unknown_becomes_empty():
    import server.state_server as ss

    ss.set_body_action("garbage")
    assert ss._BODY["action"] == ""
    tick = ss._collect_tick()
    assert not any("body_action" in m for m in tick)


def test_collect_tick_handles_provider_value_then_recovers():
    """After a provider exception, subsequent successful ticks resume normally."""
    import server.state_server as ss

    state = {"raise": True}

    def flaky():
        if state["raise"]:
            raise RuntimeError("intentional")
        return {"cpu": 10.0, "mem": 20.0, "mic_level": 0.0, "mood": "ok",
                "vision_active": False, "gestures_active": False,
                "hud_enabled": True, "online": True,
                "user_name": "", "language": "english",
                "last_gesture": {"name": "none", "ts": 0.0}}

    ss.set_telemetry_provider(flaky)
    t1 = ss._collect_tick()
    assert any("telemetry" in m and m["telemetry"] is None for m in t1)
    state["raise"] = False
    t2 = ss._collect_tick()
    sent = next(m for m in t2 if "telemetry" in m)
    assert sent["telemetry"] is not None
    assert sent["telemetry"]["cpu"] == 10.0


def test_collect_tick_skips_telemetry_provider_when_not_included():
    """include_telemetry=False must not invoke the (expensive) provider at all."""
    import server.state_server as ss

    calls = {"n": 0}

    def counting():
        calls["n"] += 1
        return {"cpu": 1.0}

    ss.set_telemetry_provider(counting)
    try:
        tick = ss._collect_tick(include_telemetry=False)
        assert calls["n"] == 0, "provider must not be called when telemetry excluded"
        assert not any("telemetry" in m for m in tick), f"no telemetry expected; got {tick}"
        # And it still fires when included.
        tick2 = ss._collect_tick(include_telemetry=True)
        assert calls["n"] == 1
        assert any("telemetry" in m for m in tick2)
    finally:
        ss._TELEMETRY_PROVIDER = None
