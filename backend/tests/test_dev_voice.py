"""Tests for skills.dev_voice — voice-coding orchestration + commit safety."""
from __future__ import annotations

import types

import pytest

import skills.dev_voice as dv


# ---------------------------------------------------------------------------
# Pure parsers
# ---------------------------------------------------------------------------

def test_parse_pytest_all_pass():
    r = dv._parse_pytest("============ 214 passed in 5.21s ============")
    assert r["passed"] == 214
    assert r["failed"] == 0
    assert r["first_failure"] is None
    assert r["parsed"] is True


def test_parse_pytest_failures_with_first():
    out = (
        "FAILED backend/tests/test_wake.py::test_wake_smoothing - AssertionError: values differ\n"
        "FAILED backend/tests/test_wake.py::test_other - ValueError\n"
        "=========== 2 failed, 212 passed in 3.40s ==========="
    )
    r = dv._parse_pytest(out)
    assert r["failed"] == 2
    assert r["passed"] == 212
    assert r["first_failure"]["name"] == "test_wake_smoothing"
    assert r["first_failure"]["error"] == "AssertionError"


def test_parse_pytest_errors():
    out = "ERROR backend/tests/test_x.py::test_boom - ImportError\n=== 1 error in 0.1s ==="
    r = dv._parse_pytest(out)
    assert r["errors"] == 1
    assert r["first_failure"]["name"] == "test_boom"


def test_parse_pytest_garbage_safe_fallback():
    r = dv._parse_pytest("totally unrelated output\nno summary here")
    assert r["parsed"] is False
    assert r["passed"] == r["failed"] == r["errors"] == 0


def test_parse_git_status_clean():
    r = dv._parse_git_status("")
    assert r["clean"] is True
    assert r["tracked_modified"] == []


def test_parse_git_status_mixed():
    out = " M backend/voice/wake.py\nM  staged_one.py\n?? brand_new.py\nA  added.py"
    r = dv._parse_git_status(out)
    assert "backend/voice/wake.py" in r["tracked_modified"]
    assert "brand_new.py" in r["untracked"]
    assert "staged_one.py" in r["staged"]
    assert "added.py" in r["staged"]
    assert r["clean"] is False


# ---------------------------------------------------------------------------
# Fake coder for orchestration tests
# ---------------------------------------------------------------------------

def _wrap(command, stdout="", stderr="", code=0):
    """Build a safe_shell-style formatted string."""
    parts = [f"$ {command}", f"exit={code}, elapsed=0.1s"]
    if stdout:
        parts.append(f"--- stdout ---\n{stdout}")
    if stderr:
        parts.append(f"--- stderr ---\n{stderr}")
    return "\n".join(parts)


class FakeCoder:
    """Records every safe_shell call and replays scripted responses."""

    def __init__(self, responses=None, gen_text="feat(x): scripted message"):
        self.calls = []
        self.responses = responses or {}
        self.gen_text = gen_text
        self.gen_raises = False

    def safe_shell(self, command, cwd=None, timeout_s=60):
        self.calls.append(command)
        for key, resp in self.responses.items():
            if command.startswith(key):
                return resp
        return _wrap(command, stdout="", code=0)

    def _gen(self, prompt, system=None):
        if self.gen_raises:
            raise RuntimeError("gemini offline")
        return self.gen_text


@pytest.fixture()
def fake_project(monkeypatch, tmp_path):
    """Stub memory.project so dev_voice has a stable root + no disk writes."""
    root = str(tmp_path)
    updates = []
    fake = types.SimpleNamespace(
        current_root=lambda: root,
        get_profile=lambda r: {"name": "Test", "root": r, "test_cmd": 'pytest -q',
                               "last_task": "earlier work", "recent_files": ["a.py", "b.py"]},
        default_test_cmd=lambda r: "pytest -q",
        update_profile=lambda r, **kw: updates.append((r, kw)),
        list_projects=lambda: [{"name": "Test"}],
    )
    monkeypatch.setattr(dv, "project", fake)
    return root, updates


def test_pytest_brief_speaks_triage_and_updates(monkeypatch, fake_project):
    root, updates = fake_project
    out = "=========== 2 failed, 212 passed in 3.4s ===========\nFAILED t.py::test_a - AssertionError"
    fc = FakeCoder(responses={"pytest": _wrap("pytest -q", stdout=out, code=1)})
    monkeypatch.setattr(dv, "_coder", lambda: fc)

    spoken = dv.pytest_brief(root)
    assert "2 failed" in spoken and "212 passed" in spoken
    assert "test_a" in spoken
    assert updates  # last_task was updated


def test_pytest_brief_all_pass(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={"pytest": _wrap("pytest -q", stdout="=== 50 passed in 1s ===", code=0)})
    monkeypatch.setattr(dv, "_coder", lambda: fc)
    assert dv.pytest_brief(root) == "All 50 passed."


def test_git_brief_one_sentence(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={
        "git status": _wrap("git status --short", stdout=" M a.py\n M b.py", code=0),
        "git diff": _wrap("git diff --stat", stdout=" a.py | 2 +-\n b.py | 1 +", code=0),
    }, gen_text="Tweaked two files.")
    monkeypatch.setattr(dv, "_coder", lambda: fc)
    assert dv.git_brief(root) == "Tweaked two files."


def test_git_brief_template_fallback_when_gen_raises(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={
        "git status": _wrap("git status --short", stdout=" M a.py\n M b.py", code=0),
        "git diff": _wrap("git diff --stat", stdout=" a.py | 2 +-", code=0),
    })
    fc.gen_raises = True
    monkeypatch.setattr(dv, "_coder", lambda: fc)
    spoken = dv.git_brief(root)
    assert "2 modified" in spoken


def test_smart_commit_does_not_commit(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={
        "git status": _wrap("git status --short", stdout=" M a.py", code=0),
        "git diff": _wrap("git diff", stdout="diff --git a/a.py...", code=0),
    }, gen_text="fix(core): tweak a")
    monkeypatch.setattr(dv, "_coder", lambda: fc)

    prep = dv.smart_commit(root)
    assert prep["confirm"] is True
    assert prep["message"] == "fix(core): tweak a"
    assert prep["files"] == ["a.py"]
    # Crucially: only read-only git status/diff ran — NO add / commit.
    assert all(c.startswith("git status") or c.startswith("git diff") for c in fc.calls), fc.calls
    assert not any("add" in c or "commit" in c for c in fc.calls)


def test_smart_commit_nothing_when_only_untracked(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={
        "git status": _wrap("git status --short", stdout="?? new.py", code=0),
    })
    monkeypatch.setattr(dv, "_coder", lambda: fc)
    prep = dv.smart_commit(root)
    assert prep["confirm"] is False
    assert "untracked" in prep["message"]


def test_do_commit_safety(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={
        "git add -u": _wrap("git add -u", code=0),
        "git -c commit.gpgsign=false commit": _wrap(
            "git commit", stdout="[main a1b2c3d] fix(core): tweak a\n 1 file changed", code=0),
    })
    monkeypatch.setattr(dv, "_coder", lambda: fc)

    spoken = dv.do_commit(root, "fix(core): tweak a")
    assert "a1b2c3d" in spoken

    # Hard safety assertions on the exact shell calls made:
    assert any(c == "git add -u" for c in fc.calls)
    assert not any("add -A" in c or "add ." in c for c in fc.calls)
    assert any(c.startswith("git -c commit.gpgsign=false commit") for c in fc.calls)
    assert not any("push" in c for c in fc.calls)
    # include_untracked defaults False -> no per-file `git add <file>` of new files.
    assert not any(c.startswith("git add ") and c != "git add -u" for c in fc.calls)


def test_do_commit_include_untracked_stages_by_path(monkeypatch, fake_project):
    root, _ = fake_project
    fc = FakeCoder(responses={
        "git add": _wrap("git add", code=0),
        "git -c commit.gpgsign=false commit": _wrap(
            "git commit", stdout="[main deadbee] chore: add", code=0),
    })
    monkeypatch.setattr(dv, "_coder", lambda: fc)

    dv.do_commit(root, "chore: add new", include_untracked=True, new_files=["new.py"])
    assert "git add -u" in fc.calls
    assert "git add new.py" in fc.calls
    assert not any("add -A" in c or "add ." in c for c in fc.calls)
    assert not any("push" in c for c in fc.calls)


def test_resume_brief_from_profile_no_shell(monkeypatch, fake_project):
    root, _ = fake_project
    # No coder set — resume_brief must not touch the shell.
    monkeypatch.setattr(dv, "_coder", lambda: (_ for _ in ()).throw(AssertionError("shell used")))
    spoken = dv.resume_brief(root)
    assert "Working on Test" in spoken
    assert "earlier work" in spoken
