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


def test_find_hud_exe_prefers_product_name(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "RELEASE_DIR", tmp_path)
    monkeypatch.setattr(L, "HUD_EXE_NAME", "Zendaya HUD.exe")
    (tmp_path / "Zendaya HUD.exe").write_text("x")
    (tmp_path / "zzz.exe").write_text("x")
    assert L.find_hud_exe() == tmp_path / "Zendaya HUD.exe"


def test_find_hud_exe_glob_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "RELEASE_DIR", tmp_path)
    monkeypatch.setattr(L, "HUD_EXE_NAME", "Missing.exe")
    (tmp_path / "app.exe").write_text("x")
    assert L.find_hud_exe() == tmp_path / "app.exe"


def test_find_hud_exe_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(L, "RELEASE_DIR", tmp_path / "does-not-exist")
    monkeypatch.setattr(L, "HUD_EXE_NAME", "Missing.exe")
    assert L.find_hud_exe() is None


def test_launch_hud_returns_false_when_missing(monkeypatch):
    monkeypatch.setattr(L, "find_hud_exe", lambda: None)
    called = []
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: called.append(a))
    assert L.launch_hud() is False
    assert called == []


def test_launch_hud_starts_exe_when_present(tmp_path, monkeypatch):
    exe = tmp_path / "Zendaya HUD.exe"
    exe.write_text("x")
    monkeypatch.setattr(L, "find_hud_exe", lambda: exe)
    started = []
    monkeypatch.setattr(L.subprocess, "Popen", lambda *a, **k: started.append((a, k)))
    assert L.launch_hud() is True
    assert started and started[0][0][0] == [str(exe)]


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
