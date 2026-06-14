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


class _FakeProc:
    def __init__(self, codes):
        self._codes = list(codes)
        self.pid = 99

    def wait(self):
        return self._codes.pop(0)


def test_supervise_clean_exit_no_restart(monkeypatch):
    monkeypatch.setattr(L, "remove_pid", lambda: None)
    spawned = []
    monkeypatch.setattr(L, "spawn_backend", lambda: spawned.append(1))
    assert L.supervise(_FakeProc([0])) == 0
    assert spawned == []


def test_supervise_restarts_on_crash_then_clean(monkeypatch):
    monkeypatch.setattr(L, "remove_pid", lambda: None)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    monkeypatch.setattr(L, "spawn_backend", lambda: _FakeProc([0]))  # restart exits clean
    assert L.supervise(_FakeProc([1])) == 0


def test_supervise_gives_up_after_max(monkeypatch):
    monkeypatch.setattr(L, "remove_pid", lambda: None)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    monkeypatch.setattr(L, "spawn_backend", lambda: _FakeProc([1]))  # always crash
    assert L.supervise(_FakeProc([1])) == 1


def test_main_quit_calls_request_quit(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    called = []
    monkeypatch.setattr(L, "request_quit", lambda: called.append(True))
    assert L.main(["--quit"]) == 0
    assert called == [True]


def test_main_noop_when_backend_up(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    monkeypatch.setattr(L, "backend_is_ours", lambda: True)
    spawned = []
    monkeypatch.setattr(L, "spawn_backend", lambda: spawned.append(True))
    assert L.main([]) == 0
    assert spawned == []  # did NOT start a second backend


def test_main_full_launch_path(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    monkeypatch.setattr(L, "backend_is_ours", lambda: False)
    monkeypatch.setattr(L, "write_pid", lambda: None)
    sentinel = object()
    monkeypatch.setattr(L, "spawn_backend", lambda: sentinel)
    monkeypatch.setattr(L, "wait_for_health", lambda: True)
    monkeypatch.setattr(L, "supervise", lambda p: 0 if p is sentinel else 99)
    assert L.main([]) == 0


def test_main_aborts_on_health_timeout(monkeypatch):
    monkeypatch.setattr(L, "setup_logging", lambda: None)
    monkeypatch.setattr(L, "backend_is_ours", lambda: False)
    monkeypatch.setattr(L, "write_pid", lambda: None)
    monkeypatch.setattr(L, "spawn_backend", lambda: object())
    monkeypatch.setattr(L, "wait_for_health", lambda: False)
    removed = []
    monkeypatch.setattr(L, "remove_pid", lambda: removed.append(True))
    assert L.main([]) == 1
    assert removed == [True]
