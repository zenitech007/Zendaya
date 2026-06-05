"""SP-4 — zendaya_launcher supervisor tests (pure: mocked subprocess + health)."""
import zendaya_launcher as L


def test_backend_is_ours_true_on_zendaya(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=2.0: {"ok": True, "name": "Zendaya"})
    assert L.backend_is_ours() is True


def test_backend_is_ours_false_on_wrong_name(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=2.0: {"name": "Other"})
    assert L.backend_is_ours() is False


def test_backend_is_ours_false_when_down(monkeypatch):
    monkeypatch.setattr(L, "_http_get_json", lambda url, timeout=2.0: None)
    assert L.backend_is_ours() is False


def test_pid_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LOG_DIR", tmp_path)
    monkeypatch.setattr(L, "PID_FILE", tmp_path / "launcher.pid")
    L.write_pid(4242)
    assert L.read_pid() == 4242


def test_read_pid_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "PID_FILE", tmp_path / "nope.pid")
    assert L.read_pid() is None


def test_remove_pid_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "LOG_DIR", tmp_path)
    monkeypatch.setattr(L, "PID_FILE", tmp_path / "launcher.pid")
    L.write_pid(99)
    L.remove_pid()
    L.remove_pid()  # second call must not raise
    assert L.read_pid() is None
