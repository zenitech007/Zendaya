"""SP-4 — clean-quit path: state-server /quit route + on_quit wiring,
and zendaya.request_shutdown(). Left UNCOMMITTED (tests uncommitted backend edits)."""
import server.state_server as ss


def test_quit_route_invokes_callback(monkeypatch):
    fired = []
    monkeypatch.setattr(ss, "_ON_QUIT", lambda: fired.append(True))
    result = ss.quit_zendaya()
    assert fired == [True]
    assert result == {"ok": True, "shutting_down": True}


def test_quit_route_is_safe_without_callback(monkeypatch):
    monkeypatch.setattr(ss, "_ON_QUIT", None)
    # No callback wired yet — must not raise.
    assert ss.quit_zendaya() == {"ok": True, "shutting_down": True}


def test_start_stores_on_quit(monkeypatch):
    # Stub uvicorn so start() doesn't actually bind a port.
    monkeypatch.setattr(ss.uvicorn, "Config", lambda *a, **k: object())

    class _DummyServer:
        def __init__(self, cfg):
            pass

        def run(self):
            pass

    monkeypatch.setattr(ss.uvicorn, "Server", _DummyServer)
    cb = lambda: None
    ss.start(on_quit=cb)
    assert ss._ON_QUIT is cb


def test_request_shutdown_sets_event(monkeypatch):
    import importlib
    z = importlib.import_module("zendaya")
    monkeypatch.setattr(z, "log_event", lambda *a, **k: None)
    z._SHUTDOWN.clear()
    assert z._SHUTDOWN.is_set() is False
    z.request_shutdown()
    assert z._SHUTDOWN.is_set() is True
