"""
zendaya_agent — autonomous plan / act / observe / replan loop.

Given a high-level goal, Gemini emits one action at a time as a JSON object.
Each action is dispatched to existing Zendaya capabilities (system control,
file ops, code execution, web search). The result of each action is fed back
into the next planning prompt, so the agent can recover from failures or
emergent steps without hard-coded recipes.

Public API:
    run_agent(goal, max_steps=8, handle=None) -> str
    new_handle() -> RunHandle                    # per-call cancel token
    is_running() -> bool                         # any agent running globally?
    running_count() -> int
    cancel() -> None                             # cancel ALL active runs (back-compat)

Action schema emitted by Gemini (one per turn):
    {"action": "<one of the keys in ACTIONS>",
     "args":   { ... action-specific ... },
     "why":    "short reason for this step"}

The agent terminates when Gemini emits action="done" (with a summary in args.text),
when max_steps is reached, when the wall-clock cap (5 min) is hit, or when
cancel() is called.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any, Callable, Dict, List, Optional


# ---------------------------------------------------------------------------
# Run-state — per-run cancel tokens (RunHandle), no module-level singleton.
# Multiple agent runs can execute concurrently; each carries its own handle.
# ---------------------------------------------------------------------------


class RunHandle:
    """Per-run state: cancel token + lightweight status."""

    __slots__ = ("cancel_event", "started_at")

    def __init__(self) -> None:
        self.cancel_event = threading.Event()
        self.started_at: Optional[float] = None

    def cancel(self) -> None:
        self.cancel_event.set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()


_ACTIVE_HANDLES: "set[RunHandle]" = set()
_ACTIVE_LOCK = threading.Lock()


def new_handle() -> RunHandle:
    return RunHandle()


def _register(handle: RunHandle) -> None:
    with _ACTIVE_LOCK:
        _ACTIVE_HANDLES.add(handle)


def _unregister(handle: RunHandle) -> None:
    with _ACTIVE_LOCK:
        _ACTIVE_HANDLES.discard(handle)


def running_count() -> int:
    with _ACTIVE_LOCK:
        return len(_ACTIVE_HANDLES)


def is_running() -> bool:
    """True if ANY agent run is currently active (kept for back-compat)."""
    return running_count() > 0


def cancel() -> None:
    """Cancel ALL currently active runs (back-compat shim).

    Prefer calling RunHandle.cancel() on a specific run when you have the
    handle (e.g. from zendaya_jobs).
    """
    with _ACTIVE_LOCK:
        handles = list(_ACTIVE_HANDLES)
    for h in handles:
        h.cancel()


# ---------------------------------------------------------------------------
# Lazy access to Zendaya internals (keep this module importable on its own)
# ---------------------------------------------------------------------------

def _z():
    import zendaya as _zmod
    return _zmod


def _gemini():
    z = _z()
    return getattr(z, "_gemini_client", None), getattr(z, "_GEMINI_READY", False)


def _set_state(name: str, text: str = "") -> None:
    try:
        z = _z()
        if getattr(z, "_state_server", None) is not None:
            z._state_server.set_state(name, text)
    except Exception:
        pass


def _say(text: str) -> None:
    """Use Zendaya's main response channel so voice + face + console all fire."""
    try:
        _z().send_response(text)
    except Exception:
        print(text)


# ---------------------------------------------------------------------------
# Action handlers — every key here is something the planner can emit.
# ---------------------------------------------------------------------------

def _act_system(args: Dict[str, Any]) -> str:
    text = (args.get("text") or args.get("command") or "").strip()
    if not text:
        return "(no command text supplied)"
    try:
        import zendaya_system_access as sa
        result = sa.handle_system_access(text)
        if result is None:
            # Fall back to the broader open/close parser exposed via main module.
            z = _z()
            sysc = z.parse_system_control(text)
            if sysc:
                if sysc["type"] == "open":
                    return z.open_target(sysc["target"])
                if sysc["type"] == "close":
                    return z.close_target(sysc["target"])
            return f"(no system handler matched '{text}')"
        return str(result)
    except Exception as e:
        return f"(system action failed: {e})"


def _act_write_file(args: Dict[str, Any]) -> str:
    desc = (args.get("description") or args.get("spec") or "").strip()
    path = (args.get("path") or "").strip()
    if not desc or not path:
        return "(write_file needs both 'description' and 'path')"
    try:
        import zendaya_coder
        return zendaya_coder.write_file_smart(desc, path)
    except Exception as e:
        return f"(write_file failed: {e})"


def _act_edit_file(args: Dict[str, Any]) -> str:
    path = (args.get("path") or "").strip()
    change = (args.get("change") or args.get("instructions") or "").strip()
    if not path or not change:
        return "(edit_file needs 'path' and 'change')"
    try:
        import zendaya_coder
        # Agent skips per-edit confirm; the goal-level confirm covers the run.
        return zendaya_coder.edit_file_smart(path, change, preview=False)
    except Exception as e:
        return f"(edit_file failed: {e})"


def _act_generate_project(args: Dict[str, Any]) -> str:
    spec = (args.get("spec") or args.get("description") or "").strip()
    root = (args.get("root_dir") or args.get("path") or "").strip()
    if not spec or not root:
        return "(generate_project needs 'spec' and 'root_dir')"
    try:
        import zendaya_coder
        return zendaya_coder.generate_project(spec, root)
    except Exception as e:
        return f"(generate_project failed: {e})"


def _act_run(args: Dict[str, Any]) -> str:
    path = (args.get("path") or "").strip()
    timeout = int(args.get("timeout", 20))
    if not path:
        return "(run needs 'path')"
    try:
        import zendaya_coder
        return zendaya_coder.run_code(path, timeout_s=timeout)
    except Exception as e:
        return f"(run failed: {e})"


def _act_read_file(args: Dict[str, Any]) -> str:
    path = (args.get("path") or "").strip()
    if not path:
        return "(read_file needs 'path')"
    try:
        return _z().read_file_content(path)
    except Exception as e:
        return f"(read_file failed: {e})"


def _act_search(args: Dict[str, Any]) -> str:
    query = (args.get("query") or "").strip()
    if not query:
        return "(search needs 'query')"
    try:
        return _z().tavily_search(query)
    except Exception as e:
        return f"(search failed: {e})"


def _act_say(args: Dict[str, Any]) -> str:
    text = (args.get("text") or "").strip()
    if not text:
        return "(say needs 'text')"
    _say(text)
    return f"(spoke: {text[:100]})"


def _act_remember(args: Dict[str, Any]) -> str:
    fact = (args.get("fact") or args.get("text") or "").strip()
    if not fact:
        return "(remember needs 'fact')"
    try:
        import zendaya_memory_facts as facts
        return facts.remember(fact, tags=args.get("tags") or ["agent"])
    except Exception as e:
        return f"(remember failed: {e})"


def _act_grep(args: Dict[str, Any]) -> str:
    root = (args.get("root") or args.get("path") or "").strip()
    pattern = (args.get("pattern") or args.get("query") or "").strip()
    if not root or not pattern:
        return "(grep needs 'root' and 'pattern')"
    try:
        import zendaya_coder
        return zendaya_coder.grep_files(root, pattern, max_hits=int(args.get("max_hits", 60)))
    except Exception as e:
        return f"(grep failed: {e})"


def _act_list_files(args: Dict[str, Any]) -> str:
    root = (args.get("root") or args.get("path") or "").strip()
    if not root:
        return "(list_files needs 'root')"
    try:
        import zendaya_coder
        return zendaya_coder.list_files(root, max_entries=int(args.get("max_entries", 200)))
    except Exception as e:
        return f"(list_files failed: {e})"


def _act_syntax_check(args: Dict[str, Any]) -> str:
    path = (args.get("path") or "").strip()
    if not path:
        return "(syntax_check needs 'path')"
    try:
        import zendaya_coder
        ok, msg = zendaya_coder.syntax_check(path)
        return f"{'✓' if ok else '✗'} {msg}"
    except Exception as e:
        return f"(syntax_check failed: {e})"


def _act_auto_fix(args: Dict[str, Any]) -> str:
    path = (args.get("path") or "").strip()
    attempts = int(args.get("attempts", 3))
    timeout = int(args.get("timeout", 20))
    if not path:
        return "(auto_fix needs 'path')"
    try:
        import zendaya_coder
        return zendaya_coder.run_with_autofix(path, max_attempts=attempts, timeout_s=timeout)
    except Exception as e:
        return f"(auto_fix failed: {e})"


def _act_bash(args: Dict[str, Any]) -> str:
    command = (args.get("command") or args.get("text") or "").strip()
    cwd = (args.get("cwd") or "").strip() or None
    timeout = int(args.get("timeout", 60))
    if not command:
        return "(bash needs 'command')"
    try:
        import zendaya_coder
        return zendaya_coder.safe_shell(command, cwd=cwd, timeout_s=timeout)
    except Exception as e:
        return f"(bash failed: {e})"


def _act_verify(args: Dict[str, Any]) -> str:
    """
    Planner-asserted verification step. The planner emits a path or pattern
    plus the expectation; we mechanically check it.
      - {"check": "exists", "path": "..."}
      - {"check": "syntax", "path": "..."}
      - {"check": "contains", "path": "...", "pattern": "regex"}
      - {"check": "runs", "path": "...", "expect_exit": 0}
    """
    check = (args.get("check") or "").strip().lower()
    path = (args.get("path") or "").strip()
    if not check:
        return "(verify needs 'check')"
    try:
        import zendaya_coder
        if check == "exists":
            import os
            ok = os.path.isfile(zendaya_coder._expand(path)) or os.path.isdir(zendaya_coder._expand(path))
            return f"{'PASS' if ok else 'FAIL'}: exists({path})"
        if check == "syntax":
            ok, msg = zendaya_coder.syntax_check(path)
            return f"{'PASS' if ok else 'FAIL'}: syntax({path}) — {msg}"
        if check == "contains":
            pattern = (args.get("pattern") or "").strip()
            if not pattern:
                return "(verify contains needs 'pattern')"
            try:
                with open(zendaya_coder._expand(path), "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except Exception as e:
                return f"FAIL: contains({path}) — read error: {e}"
            import re as _re
            try:
                hit = bool(_re.search(pattern, text, _re.IGNORECASE))
            except _re.error as e:
                return f"FAIL: contains — bad regex: {e}"
            return f"{'PASS' if hit else 'FAIL'}: contains({path}, /{pattern}/)"
        if check == "runs":
            expect = int(args.get("expect_exit", 0))
            result = zendaya_coder.run_code(path, timeout_s=int(args.get("timeout", 20)))
            import re as _re
            m = _re.search(r"exit=(-?\d+)", result.splitlines()[0] if result else "")
            actual = int(m.group(1)) if m else 1
            return f"{'PASS' if actual == expect else 'FAIL'}: runs({path}) exit={actual} expected={expect}\n{result}"
        return f"(unknown verify check '{check}'. Use one of: exists, syntax, contains, runs)"
    except Exception as e:
        return f"(verify failed: {e})"


def _act_ui_describe(args: Dict[str, Any]) -> str:
    question = (args.get("question") or "Describe what's currently on the screen.").strip()
    try:
        import zendaya_uivision as uiv
        return uiv.describe_screen(question)
    except Exception as e:
        return f"(ui_describe failed: {e})"


def _act_ui_locate(args: Dict[str, Any]) -> str:
    target = (args.get("target") or args.get("target_desc") or "").strip()
    if not target: return "(ui_locate needs 'target')"
    try:
        import zendaya_uivision as uiv
        res = uiv.locate_on_screen(target)
        if isinstance(res, str): return f"(ui_locate failed: {res})"
        return f"Found '{res['label']}' at x={res['x']}, y={res['y']}"
    except Exception as e:
        return f"(ui_locate failed: {e})"


def _act_ui_click(args: Dict[str, Any]) -> str:
    target = (args.get("target") or args.get("target_desc") or "").strip()
    if not target: return "(ui_click needs 'target')"
    try:
        import zendaya_uivision as uiv
        return uiv.agent_click_target(target)
    except Exception as e:
        return f"(ui_click failed: {e})"


def _act_ui_type(args: Dict[str, Any]) -> str:
    text = (args.get("text") or "").strip()
    if not text: return "(ui_type needs 'text')"
    try:
        import zendaya_uivision as uiv
        return uiv.agent_type_text(text)
    except Exception as e:
        return f"(ui_type failed: {e})"


def _act_ui_press(args: Dict[str, Any]) -> str:
    key = (args.get("key") or "").strip()
    if not key: return "(ui_press needs 'key')"
    try:
        import zendaya_uivision as uiv
        return uiv.agent_press_key(key)
    except Exception as e:
        return f"(ui_press failed: {e})"


ACTIONS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    "system": _act_system,
    "write_file": _act_write_file,
    "edit_file": _act_edit_file,
    "generate_project": _act_generate_project,
    "run": _act_run,
    "read_file": _act_read_file,
    "search": _act_search,
    "say": _act_say,
    "remember": _act_remember,
    "grep": _act_grep,
    "list_files": _act_list_files,
    "syntax_check": _act_syntax_check,
    "auto_fix": _act_auto_fix,
    "bash": _act_bash,
    "verify": _act_verify,
    "ui_describe": _act_ui_describe,
    "ui_locate": _act_ui_locate,
    "ui_click": _act_ui_click,
    "ui_type": _act_ui_type,
    "ui_press": _act_ui_press,
}


# ---------------------------------------------------------------------------
# Planner prompts
# ---------------------------------------------------------------------------

_PLANNER_SYSTEM = (
    "You are BONSAI, the autonomous coding core of a desktop AI assistant. Senior software engineer "
    "discipline: read before edit, verify before declaring done, syntax-check after every write. "
    "You work by emitting exactly ONE action per step.\n\n"
    "Available actions and their args:\n"
    '  - {"action": "system", "args": {"text": "natural-language system command"}}    # open/close apps, files, folders, volume, brightness, screenshots, email\n'
    '  - {"action": "write_file", "args": {"description": "...", "path": "absolute or ~ path"}}\n'
    '  - {"action": "edit_file", "args": {"path": "...", "change": "instruction"}}\n'
    '  - {"action": "generate_project", "args": {"spec": "...", "root_dir": "..."}}    # multi-file project (2–12 files)\n'
    '  - {"action": "read_file", "args": {"path": "..."}}                              # READ before EDIT\n'
    '  - {"action": "list_files", "args": {"root": "..."}}                             # walk a folder, see what is there\n'
    '  - {"action": "grep", "args": {"root": "...", "pattern": "regex"}}               # search text inside a project\n'
    '  - {"action": "syntax_check", "args": {"path": "..."}}                           # py_compile / node --check / json / tsc\n'
    '  - {"action": "run", "args": {"path": "script path", "timeout": 20}}             # python/node/sh/ps1 only, inside safe roots\n'
    '  - {"action": "auto_fix", "args": {"path": "...", "attempts": 3}}                # run + observe + patch + retry loop\n'
    '  - {"action": "bash", "args": {"command": "pip install foo", "cwd": "..."}}      # allowlisted: pip/python/node/npm/npx/yarn/pnpm/git/tsc/eslint/prettier/pytest/ruff/black/mypy/flake8/go/cargo/rustc — no shell metacharacters\n'
    '  - {"action": "search", "args": {"query": "..."}}                                # web search via Tavily\n'
    '  - {"action": "verify", "args": {"check": "exists|syntax|contains|runs", ...}}   # MECHANICAL verification — use before "done"\n'
    '  - {"action": "ui_describe", "args": {"question": "what is on screen?"}}         # takes a screenshot, asks Gemini Vision\n'
    '  - {"action": "ui_locate", "args": {"target": "search bar"}}                     # finds X,Y coordinates of an element\n'
    '  - {"action": "ui_click", "args": {"target": "submit button"}}                   # instantly locates and clicks a target\n'
    '  - {"action": "ui_type", "args": {"text": "hello world"}}                        # types text into the active field\n'
    '  - {"action": "ui_press", "args": {"key": "enter"}}                              # presses a hotkey (e.g., enter, ctrl+c)\n'
    '  - {"action": "say", "args": {"text": "progress update spoken to user"}}\n'
    '  - {"action": "remember", "args": {"fact": "...", "tags": ["..."]}}              # save a durable fact\n'
    '  - {"action": "done", "args": {"text": "final summary for the user"}}            # END the run\n\n'
    "Rules:\n"
    "- Output ONLY a single JSON object. No markdown fences. No prose.\n"
    "- Include a short 'why' field at the top level explaining THIS step's reasoning.\n"
    "- READ-BEFORE-EDIT: for any edit_file on a non-trivial change, emit read_file or grep first to ground the patch.\n"
    "- WRITE → SYNTAX_CHECK: after write_file/edit_file on .py/.js/.ts/.json, the observation already includes a [syntax] line. If it shows ✗, fix it before continuing.\n"
    "- VERIFY-BEFORE-DONE: before emitting 'done', emit at least one verify or syntax_check or run that mechanically confirms the goal.\n"
    "- NO REPEATS: never re-issue the exact same action+args that just failed. Try a different approach.\n"
    "- Be concrete: real, fully-qualified paths. Use ~ for the user's home when path is unknown.\n"
    "- For multi-file work, prefer generate_project once over many write_file calls.\n"
    "- If you need a third-party package, use bash with `pip install <pkg>` (or `npm install <pkg>`) before importing it.\n"
    "- If a verify step FAILs, do NOT emit done with a success summary — fix it or report the failure honestly.\n"
)


def _build_plan_prompt(goal: str, observations: List[Dict[str, str]], step_num: int, max_steps: int) -> str:
    parts = [
        _PLANNER_SYSTEM,
        f"\nGOAL: {goal}\n",
        f"Step {step_num} of at most {max_steps}.",
    ]
    if observations:
        parts.append("\nHistory so far:")
        for obs in observations[-18:]:  # cap context
            act = obs.get("action", "?")
            args = obs.get("args", {})
            res = obs.get("result", "")
            if len(res) > 1500:
                res = res[:1500] + " ...(truncated)"
            parts.append(f'> action={act}  args={json.dumps(args, ensure_ascii=False)[:300]}\n  result: {res}')
    else:
        parts.append("\nNo actions taken yet. Emit your FIRST action now.")
    parts.append("\nYour next action (JSON only):")
    return "\n".join(parts)


def _ask_planner(goal: str, observations: List[Dict[str, str]], step_num: int, max_steps: int) -> Dict[str, Any]:
    client, ready = _gemini()
    if not ready or client is None:
        return {"action": "done", "args": {"text": "Gemini is offline — can't plan further."}, "why": "no LLM"}
    prompt = _build_plan_prompt(goal, observations, step_num, max_steps)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt],
        )
        raw = (response.text or "").strip()
    except Exception as e:
        return {"action": "done", "args": {"text": f"Planner call failed: {e}"}, "why": "planner error"}

    parsed = _extract_json(raw)
    if not isinstance(parsed, dict) or "action" not in parsed:
        return {"action": "done", "args": {"text": "Planner returned an unparseable response."}, "why": "bad planner output"}
    return parsed


def _extract_json(text: str) -> Optional[dict]:
    if not text:
        return None
    s = text.strip()
    if s.startswith("```"):
        # Drop fences.
        lines = s.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def run_agent(
    goal: str,
    max_steps: int = 16,
    wall_clock_s: int = 600,
    handle: Optional[RunHandle] = None,
) -> str:
    """Run the agent on `goal`. Blocking. Returns the final summary string.

    Pass a `handle` (from `new_handle()`) for per-run cancellation. If omitted,
    a fresh handle is created internally.
    """
    if not goal or not goal.strip():
        return "I need a goal to work on."

    if handle is None:
        handle = new_handle()
    handle.started_at = time.time()
    _register(handle)

    _set_state("thinking", f"Agent starting: {goal[:80]}")
    _say(f"Agent mode: working on '{goal.strip()[:120]}'.")

    started = handle.started_at
    observations: List[Dict[str, str]] = []
    final_text = "Agent finished without a summary."
    _verification_nudge_used = False
    _VERIFY_ACTIONS = {"verify", "syntax_check", "run", "auto_fix"}
    _CODE_PRODUCING = {"write_file", "edit_file", "generate_project"}

    try:
        for step in range(1, max_steps + 1):
            if handle.is_cancelled():
                final_text = "Agent cancelled by user."
                break
            if time.time() - started > wall_clock_s:
                final_text = f"Agent stopped: hit the {wall_clock_s}s wall-clock cap."
                break

            _set_state("thinking", f"Planning step {step}/{max_steps}")
            plan = _ask_planner(goal, observations, step, max_steps)
            action = (plan.get("action") or "").strip().lower()
            args = plan.get("args") or {}
            why = (plan.get("why") or "").strip()

            if action == "done":
                # BONSAI verify-before-done: if the agent produced/modified code but
                # never verified it, push back ONCE with a synthetic observation
                # asking for verification. The planner gets one chance to comply.
                wrote_code = any(o.get("action") in _CODE_PRODUCING for o in observations)
                ran_check = any(o.get("action") in _VERIFY_ACTIONS for o in observations)
                if wrote_code and not ran_check and not _verification_nudge_used:
                    _verification_nudge_used = True
                    observations.append({
                        "action": "(planner nudge)",
                        "args": {},
                        "result": (
                            "BLOCKED: you wrote/edited code but emitted 'done' without verification. "
                            "Emit a verify / syntax_check / run / auto_fix action first to prove the goal works, "
                            "then emit done. If the code can't be verified, say so explicitly in the done summary."
                        ),
                    })
                    continue
                final_text = (args.get("text") or "Done.").strip()
                break

            handler = ACTIONS.get(action)
            if handler is None:
                observations.append({
                    "action": action or "(missing)",
                    "args": args,
                    "result": f"(unknown action '{action}' — pick from {sorted(ACTIONS.keys()) + ['done']})",
                })
                continue

            # Status line for the human.
            label = f"[step {step}] {action}"
            if why:
                label += f" — {why[:120]}"
            try:
                z = _z()
                z.stream_print(label)
            except Exception:
                print(label)

            _set_state("thinking", label[:120])
            try:
                result = handler(args)
            except Exception as e:
                result = f"(handler crashed: {e})"
            if not isinstance(result, str):
                result = str(result)
            observations.append({"action": action, "args": args, "result": result})
        else:
            final_text = f"Reached the {max_steps}-step cap before finishing."
    finally:
        _unregister(handle)
        _set_state("talking", final_text[:120])

    # Persist a short outcome to the durable fact store.
    try:
        import zendaya_memory_facts as facts
        summary_fact = f"Agent run on '{goal.strip()[:140]}': {final_text[:280]}"
        facts.remember(summary_fact, tags=["agent-result"])
    except Exception:
        pass

    _say(final_text)
    return final_text


# ---------------------------------------------------------------------------
# Convenience entry for the parser branch in zendaya.py
# ---------------------------------------------------------------------------

def request_run_with_confirmation(goal: str) -> str:
    """
    Stage an agent run behind the existing pending_confirm gate.

    Stores a pending_confirm record so the user can say 'confirm agent' before
    the multi-step loop actually starts. Returns the prompt the user should see.
    """
    try:
        z = _z()
        z.MEM["pending_confirm"] = {"action": "agent_plan", "goal": goal.strip()}
        z.save_memory(z.MEM)
        return (
            f"BONSAI agent plan: «{goal.strip()}». I'll run a multi-step loop with up to 16 actions "
            f"(syntax-check, run, verify before done). Say 'confirm agent' to start, or 'cancel' to drop it."
        )
    except Exception as e:
        # If the brain isn't available for some reason, just run inline.
        return run_agent(goal)


# ---------------------------------------------------------------------------
# Self-modification — edit zendaya_*.py, smoke-test the import, hot-reload.
# ---------------------------------------------------------------------------

import importlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_SELF_EDIT_ALLOWLIST = {
    "zendaya_coder",
    "zendaya_agent",
    "zendaya_installer",
    "zendaya_memory_facts",
    "zendaya_system_access",
}


def _module_path(module_name: str) -> Optional[Path]:
    if not re.match(r"^zendaya_[a-z_]+$", module_name):
        return None
    if module_name not in _SELF_EDIT_ALLOWLIST:
        return None
    p = _BACKEND_DIR / f"{module_name}.py"
    return p if p.is_file() else None


def stage_self_edit(module_name: str, change: str) -> str:
    """Stage an edit to one of Zendaya's own modules behind pending_confirm."""
    p = _module_path(module_name)
    if p is None:
        return (
            f"I can only self-edit my own modules: {sorted(_SELF_EDIT_ALLOWLIST)}. "
            f"Got: {module_name!r}."
        )
    try:
        z = _z()
        z.MEM["pending_confirm"] = {
            "action": "self_edit",
            "module": module_name,
            "path": str(p),
            "change": change.strip(),
            "ts": time.time(),
        }
        z.save_memory(z.MEM)
    except Exception as e:
        return f"Couldn't stage the self-edit: {e}"
    return (
        f"Self-edit queued for **{module_name}**: «{change.strip()}». "
        f"Say yes to apply (with backup + smoke test + hot-reload), or no to cancel."
    )


def confirm_self_edit(pending: Dict[str, Any]) -> str:
    """Apply a staged self-edit, smoke-test it, and reload on success."""
    module_name = pending.get("module") or ""
    path = pending.get("path") or ""
    change = pending.get("change") or ""
    p = _module_path(module_name)
    if p is None or str(p) != path or not p.is_file():
        return "Self-edit target is gone or not allowed — cancelled."

    try:
        import zendaya_coder
    except Exception as e:
        return f"Coder module unavailable, can't self-edit: {e}"

    backup = p.with_suffix(p.suffix + ".bak")
    try:
        shutil.copy2(p, backup)
    except Exception as e:
        return f"Couldn't back up {p.name}: {e}"

    try:
        outcome = zendaya_coder.edit_file_smart(str(p), change, preview=False)
    except Exception as e:
        return f"Edit failed: {e}"

    smoke = subprocess.run(
        [sys.executable, "-c", f"import {module_name}"],
        capture_output=True,
        text=True,
        cwd=str(_BACKEND_DIR),
        timeout=20,
        shell=False,
    )
    if smoke.returncode != 0:
        try:
            shutil.copy2(backup, p)
        except Exception:
            pass
        return (
            f"Self-edit reverted — import smoke test failed:\n"
            f"{(smoke.stderr or smoke.stdout).strip()[-1200:]}"
        )

    try:
        if module_name in sys.modules:
            importlib.reload(sys.modules[module_name])
        else:
            importlib.import_module(module_name)
    except Exception as e:
        try:
            shutil.copy2(backup, p)
        except Exception:
            pass
        return f"Self-edit reverted — hot reload raised {e!r}."

    return f"✅ {module_name} edited and reloaded. ({outcome})"


if __name__ == "__main__":
    print("zendaya_agent loaded. Available actions:", sorted(ACTIONS.keys()))
