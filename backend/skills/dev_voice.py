"""
skills.dev_voice — voice-coding orchestration (test / git / commit / resume).

Built on ``skills.coder`` primitives (``safe_shell`` containment + ``_gen``
brain) and ``memory.project`` (current-project + per-project profiles). Each
public function targets a ``root`` (defaulting to the current project), returns
a **short, spoken-friendly string** (or a confirm dict for commits), and updates
the project profile as a side effect. None of these call ``send_response`` — the
spoken output + commit confirm gate live in ``zendaya.py``.

Safety (hard rules, see the Pack B design doc §7):
  * commits require an explicit spoken "yes" (the dispatcher's pending-action gate),
  * staging is ``git add -u`` only — never ``git add -A`` / ``git add .``,
  * untracked files staged only on the explicit "including new files" variant,
    and then by explicit per-file path,
  * never ``git push``.
"""

from __future__ import annotations

import os
import re
import tempfile
from typing import Any, Dict, List, Optional

from memory import project

# coder is imported lazily so this module stays importable for unit tests even
# if the heavier coder deps are missing; tests monkeypatch ``_coder()``.
try:  # pragma: no cover - trivial import guard
    from skills import coder as _coder_mod
except Exception:  # pragma: no cover
    _coder_mod = None


def _coder():
    if _coder_mod is None:
        raise RuntimeError("coder module unavailable")
    return _coder_mod


# Stash of the most recent test run so a following "fix it" can route to autofix.
_LAST_TEST: Dict[str, Any] = {}


# ---------------------------------------------------------------------------
# safe_shell output unwrapping
# ---------------------------------------------------------------------------

def _unwrap(shell_text: str) -> Dict[str, Any]:
    """Pull exit code + stdout + stderr out of coder.safe_shell's formatted text.

    safe_shell returns:
        $ <command>
        exit=<n>, elapsed=<t>s
        --- stdout ---
        <stdout>
        --- stderr ---
        <stderr>
    A refusal (metacharacters / allowlist / cwd) has no ``exit=`` line — we flag
    it via ``refused`` so callers can speak a graceful message.
    """
    text = shell_text or ""
    exit_m = re.search(r"^exit=(-?\d+)", text, re.MULTILINE)
    refused = exit_m is None
    code = int(exit_m.group(1)) if exit_m else -1

    def _section(name: str) -> str:
        m = re.search(rf"--- {name} ---\n(.*?)(?=\n--- (?:stdout|stderr) ---|\Z)", text, re.DOTALL)
        return (m.group(1).rstrip() if m else "")

    return {
        "code": code,
        "refused": refused,
        "stdout": _section("stdout"),
        "stderr": _section("stderr"),
        "raw": text,
    }


# ---------------------------------------------------------------------------
# Pure parsers (the unit-test surface)
# ---------------------------------------------------------------------------

def _parse_pytest(output: str) -> Dict[str, Any]:
    """pytest tail -> {passed, failed, errors, first_failure}.

    ``first_failure`` is ``{"name": str, "error": str|None}`` or None. On
    unparseable input every count is 0 and ``parsed`` is False so callers can
    fall back to a raw-tail message.
    """
    result: Dict[str, Any] = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "first_failure": None,
        "parsed": False,
    }
    if not output:
        return result

    # Count keywords on the summary line(s): "2 failed, 212 passed in 3.4s".
    for kw, key in (("passed", "passed"), ("failed", "failed"), ("error", "errors")):
        m = re.search(rf"(\d+)\s+{kw}s?\b", output)
        if m:
            result[key] = int(m.group(1))
            result["parsed"] = True

    # First failure: "FAILED path::test_name - ExcType: message"
    fm = re.search(r"^(?:FAILED|ERROR)\s+(\S+?)(?:\s+-\s+(.*))?$", output, re.MULTILINE)
    if fm:
        raw_name = fm.group(1)
        # Speak just the test id (after the last "::"), not the full path.
        name = raw_name.split("::")[-1] if "::" in raw_name else raw_name
        err = (fm.group(2) or "").strip() or None
        if err:
            # Keep just the exception type / first clause, drop long messages.
            err = err.split(":")[0].strip() if ":" in err else err
        result["first_failure"] = {"name": name, "error": err}
        result["parsed"] = True

    return result


def _parse_git_status(output: str) -> Dict[str, Any]:
    """`git status --short` -> tracked-modified / untracked / staged file lists.

    Porcelain short format: two status columns ``XY`` then a space then the path.
    X = index (staged), Y = worktree. ``??`` = untracked.
    """
    tracked_modified: List[str] = []
    untracked: List[str] = []
    staged: List[str] = []
    for line in (output or "").splitlines():
        if len(line) < 4:
            continue
        x, y = line[0], line[1]
        path = line[3:].strip()
        if not path:
            continue
        # Renames show as "old -> new"; keep the new path.
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if x == "?" and y == "?":
            untracked.append(path)
            continue
        if x not in (" ", "?"):
            staged.append(path)
        if y not in (" ", "?"):
            tracked_modified.append(path)
    return {
        "tracked_modified": tracked_modified,
        "untracked": untracked,
        "staged": staged,
        "clean": not (tracked_modified or untracked or staged),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _resolve_root(root: Optional[str]) -> str:
    return root or project.current_root()


def pytest_brief(root: Optional[str] = None, test_cmd: Optional[str] = None) -> str:
    """Run the project's tests and speak a short triage."""
    root = _resolve_root(root)
    profile = project.get_profile(root)
    cmd = test_cmd or profile.get("test_cmd") or project.default_test_cmd(root)

    shell_out = _coder().safe_shell(cmd, cwd=root, timeout_s=300)
    res = _unwrap(shell_out)
    if res["refused"]:
        return f"I couldn't run the tests there — {res['raw'].strip().splitlines()[0] if res['raw'].strip() else 'command refused'}."

    combined = (res["stdout"] + "\n" + res["stderr"]).strip()
    parsed = _parse_pytest(combined)

    _LAST_TEST.clear()
    _LAST_TEST.update({"root": root, "test_cmd": cmd, "output": combined, "parsed": parsed})

    if not parsed["parsed"]:
        tail = combined.splitlines()[-1] if combined else "no output"
        spoken = f"I ran the tests but couldn't parse the result. Last line: {tail}"
    elif parsed["failed"] == 0 and parsed["errors"] == 0:
        spoken = f"All {parsed['passed']} passed."
    else:
        bits = []
        if parsed["failed"]:
            bits.append(f"{parsed['failed']} failed")
        if parsed["errors"]:
            bits.append(f"{parsed['errors']} errored")
        if parsed["passed"]:
            bits.append(f"{parsed['passed']} passed")
        spoken = ", ".join(bits) + "."
        ff = parsed["first_failure"]
        if ff:
            err = f" — {ff['error']}" if ff.get("error") else ""
            spoken += f" First: {ff['name']}{err}. Say 'fix it' to try an auto-fix."

    project.update_profile(root, last_task=f"ran tests: {spoken}")
    return spoken


def git_brief(root: Optional[str] = None) -> str:
    """One spoken sentence summarizing the working-tree diff."""
    root = _resolve_root(root)
    status_out = _unwrap(_coder().safe_shell("git status --short", cwd=root))
    if status_out["refused"]:
        return "I couldn't read git status there."
    parsed = _parse_git_status(status_out["stdout"])
    if parsed["clean"]:
        return "Nothing to commit — the working tree is clean."

    n_mod = len(parsed["tracked_modified"])
    n_new = len(parsed["untracked"])
    n_staged = len(parsed["staged"])

    # Try a one-sentence AI summary of the diff stat; fall back to a template.
    try:
        stat = _unwrap(_coder().safe_shell("git diff --stat", cwd=root))
        diff_stat = stat["stdout"].strip()
        if diff_stat:
            summary = _coder()._gen(
                "Summarize this git diff --stat in ONE short spoken sentence "
                "(no markdown, no file list longer than 3 names):\n\n" + diff_stat,
                system="You are a terse release engineer. Reply with one sentence only.",
            ).strip()
            if summary:
                return summary
    except Exception:
        pass

    parts = []
    if n_mod:
        parts.append(f"{n_mod} modified")
    if n_staged:
        parts.append(f"{n_staged} staged")
    if n_new:
        parts.append(f"{n_new} new")
    return ", ".join(parts) + "."


def smart_commit(root: Optional[str] = None, message: Optional[str] = None,
                 include_untracked: bool = False) -> Dict[str, Any]:
    """Prepare a commit. Returns a confirm dict — does NOT commit yet.

    The spoken confirmation + the actual ``do_commit`` happen in the dispatcher
    so the verbal yes/no gate lives at the command layer.
    """
    root = _resolve_root(root)
    status_out = _unwrap(_coder().safe_shell("git status --short", cwd=root))
    if status_out["refused"]:
        return {"confirm": False, "message": "I couldn't read git status there.", "root": root}
    parsed = _parse_git_status(status_out["stdout"])

    tracked = parsed["tracked_modified"]
    if not tracked and not parsed["staged"]:
        n_new = len(parsed["untracked"])
        if n_new and not include_untracked:
            return {
                "confirm": False,
                "root": root,
                "message": f"Nothing to commit — {n_new} untracked file"
                f"{'s' if n_new != 1 else ''}. Say 'commit including new files' to add those too.",
            }
        if not n_new:
            return {"confirm": False, "root": root, "message": "Nothing to commit — the working tree is clean."}

    # Generate a Conventional-Commits one-liner from the diff; template fallback.
    if not message:
        try:
            diff = _unwrap(_coder().safe_shell("git diff", cwd=root))
            diff_text = diff["stdout"].strip()[:6000]
            message = _coder()._gen(
                "Write ONE Conventional Commits message line (e.g. 'fix(voice): ...') "
                "for this diff. Output only the single line, no body, no quotes:\n\n" + diff_text,
                system="You write terse Conventional Commits subject lines.",
            ).strip().splitlines()[0].strip()
        except Exception:
            message = None
    if not message:
        n = len(tracked) + (len(parsed["untracked"]) if include_untracked else 0)
        message = f"chore: update {n} file{'s' if n != 1 else ''}"

    new_files = parsed["untracked"] if include_untracked else []
    return {
        "confirm": True,
        "root": root,
        "message": message,
        "files": tracked,
        "new_files": new_files,
        "include_untracked": include_untracked,
    }


def do_commit(root: str, message: str, include_untracked: bool = False,
              new_files: Optional[List[str]] = None) -> str:
    """Stage tracked modifications (and explicitly-listed new files) and commit.

    Hard safety rules enforced here:
      * staging is ``git add -u`` (tracked only); never ``-A`` / ``.``,
      * untracked staged only when ``include_untracked`` and only by explicit path,
      * commit message passed via ``-F <tempfile>`` (avoids safe_shell's
        metacharacter rejection of ``( )`` in scopes like ``feat(voice):``),
      * never ``git push``.
    """
    coder = _coder()

    stage = _unwrap(coder.safe_shell("git add -u", cwd=root))
    if stage["refused"] or stage["code"] != 0:
        return "I couldn't stage the changes."

    if include_untracked and new_files:
        for f in new_files:
            # Explicit per-file path — never a wildcard.
            add_one = _unwrap(coder.safe_shell(f"git add {f}", cwd=root))
            if add_one["refused"]:
                return f"I couldn't stage the new file {f}."

    # Write the message to a temp file and commit with -F (no shell metachars).
    fd, msg_path = tempfile.mkstemp(prefix="zendaya-commit-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(message.strip() + "\n")
        commit = _unwrap(
            coder.safe_shell(f"git -c commit.gpgsign=false commit -F {msg_path}", cwd=root)
        )
    finally:
        try:
            os.remove(msg_path)
        except OSError:
            pass

    if commit["refused"]:
        return "The commit command was refused."
    if commit["code"] != 0:
        tail = (commit["stdout"] or commit["stderr"]).strip().splitlines()
        return f"Commit failed: {tail[-1] if tail else 'unknown error'}."

    # Pull the short SHA from the commit output, e.g. "[main a1b2c3d] subject".
    sha = ""
    sm = re.search(r"\[[^\]]*\s+([0-9a-f]{7,})\]", commit["stdout"])
    if sm:
        sha = sm.group(1)
    subject = message.strip().splitlines()[0]
    project.update_profile(root, last_task=f"committed: {subject}")
    if sha:
        return f"Committed {sha}: {subject}."
    return f"Committed: {subject}."


def resume_brief(root: Optional[str] = None) -> str:
    """Spoken briefing from the project profile (no shell)."""
    root = _resolve_root(root)
    profile = project.get_profile(root)
    name = profile.get("name") or os.path.basename(root)
    parts = [f"Working on {name}."]
    if profile.get("test_cmd"):
        parts.append(f"Tests run with {profile['test_cmd']}.")
    if profile.get("last_task"):
        parts.append(f"Last time: {profile['last_task']}.")
    recent = profile.get("recent_files") or []
    if recent:
        names = ", ".join(os.path.basename(p) for p in recent[:3])
        parts.append(f"Recent files: {names}.")
    return " ".join(parts)


def list_projects_brief() -> str:
    """Spoken list of known projects."""
    projs = project.list_projects()
    if not projs:
        return "I don't know any projects yet. Say 'work on' and a path to add one."
    names = ", ".join(p.get("name", "?") for p in projs)
    return f"I know {len(projs)} project{'s' if len(projs) != 1 else ''}: {names}."
