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


class _FakePopen:
    last = None

    def __init__(self, args, cwd=None, stdout=None, stderr=None, creationflags=0):
        self.args = args
        self.cwd = cwd
        self.creationflags = creationflags
        self.pid = 1234
        _FakePopen.last = self


def test_spawn_backend_runs_headless(monkeypatch):
    monkeypatch.setattr(L, "_open_log", lambda p: None)
    monkeypatch.setattr(L.subprocess, "Popen", _FakePopen)
    proc = L.spawn_backend()
    assert proc.args[0] == str(L.VENV_PYTHONW)
    assert proc.args[-2:] == ["zendaya.py", "--headless"]
    assert proc.cwd == str(L.BACKEND_DIR)
    assert proc.creationflags == L.CREATE_NO_WINDOW


def test_wait_for_health_true_when_healthy(monkeypatch):
    monkeypatch.setattr(L, "backend_is_ours", lambda: True)
    assert L.wait_for_health(timeout=1, interval=0.01) is True


def test_wait_for_health_times_out(monkeypatch):
    monkeypatch.setattr(L, "backend_is_ours", lambda: False)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    assert L.wait_for_health(timeout=0.05, interval=0.01) is False
