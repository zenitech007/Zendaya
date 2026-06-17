# Pack B — Coding by Voice — Design

- **Date:** 2026-06-16
- **Status:** Draft for review
- **Topic:** Let Zendaya drive a coding workflow by voice — run tests with spoken failure triage, speak git status + smart-commit, and remember each project so you can "resume where we left off."

## 1. Goal

Three voice-coding upgrades, building on the existing `skills/coder.py` primitives:

1. **Voice test-runner** — "run the tests" → runs the current project's test command, then **speaks** a short triage ("2 failed: `test_wake_smoothing`, AssertionError"), and offers to auto-fix.
2. **Spoken git status + smart commit** — "what changed" → one spoken sentence summarizing the diff; "commit this" → an AI-written commit message spoken for confirmation, then a **safe** commit on a verbal "yes".
3. **Per-project memory** — a current-project concept that persists, remembers each project's test command + last task + recently-touched files, and gives a spoken "resume" briefing when you switch to a project.

Stay offline-first in spirit (the only network call is the existing Gemini brain for summaries/commit messages), reuse the coder safety containment, and add **no new dependencies**.

## 2. Background — what already exists

`backend/skills/coder.py` is the primitives layer (≈875 lines):
- `safe_shell(command, cwd, timeout_s)` — runs an **argv-split** command whose program is on `_SHELL_ALLOWLIST` (includes `git`, `pytest`, `ruff`, `python`, `npm`, …), `shell=False`, inside `_is_under_safe_root(workdir)`. Returns combined stdout/stderr text.
- `run_with_autofix(path, max_attempts, timeout_s)` — run a script, detect errors (`_looks_like_error`), ask Gemini to patch, retry.
- `read_project_context(root_dir, …)` — packs a project's text files for prompt context.
- `_summarise_diff(a, b, name, max_lines)` — compact unified-diff-ish summary of two strings.
- `_gen(prompt, system)` — one-shot Gemini call (the brain) used by the smart helpers.
- `_is_under_safe_root(path)` / `_SAFE_ROOTS` — containment so commands can't run anywhere on disk.
- `grep_files`, `list_files`, `syntax_check`, `write_file_smart`, `edit_file_smart`, `generate_project`, `edit_in_project`, `run_code`.

`backend/zendaya.py` routes coder voice commands through `parse_coder_request(user_text)` (line ~1585) → a dict with a `type`, dispatched at lines ~3369-3382 (`generate_project` / `edit_in_project` / `run_code` / `run_with_autofix`). `send_response(text)` is the single spoken-output chokepoint.

`backend/memory/` holds `data_store` (JSON persistence under `zendaya_data/`, same pattern used by `voice_engine.json`, `aaf_state.json`), `facts`, and optional `vector` (Chroma).

**Gap:** every coder function takes an **explicit path**. Voice commands like "run the tests" / "commit this" have no notion of *which* repo they target. Pack B introduces a **current-project** concept to fill that gap, and the per-project memory doubles as the project registry.

## 3. Decisions (from brainstorming)

- **Target project = a settable, remembered current-project** (chosen over "always the Zendaya repo" and "infer from the foreground window"). "work on Zendaya" / "switch to `<path>`" sets it; it persists; all coding commands default to it. The per-project memory is the registry.
- **Code location = two new focused modules** rather than growing `coder.py`:
  - `memory/project.py` — registry + current-project pointer + per-project profile.
  - `skills/dev_voice.py` — the voice-coding orchestration (test/git/commit/resume), built on `coder` primitives + Gemini.
  `coder.py` stays the primitives layer; `zendaya.py` only gains parse + dispatch wiring.
- **Commit safety is a hard rule, not a preference** (see §7): voice-confirm required; stage **tracked modified files only** (`git add -u`); **never** `git add -A`/`git add .`; **never** auto-stage untracked/new files; **never** `git push`.

## 4. Components

### 4.1 `memory/project.py` (new) — per-project memory + current project — effort M

Persists to `zendaya_data/projects.json`:
```json
{
  "current": "C:\\Users\\IKA\\Zendaya",
  "projects": {
    "C:\\Users\\IKA\\Zendaya": {
      "name": "Zendaya",
      "root": "C:\\Users\\IKA\\Zendaya",
      "test_cmd": "pytest backend/tests -q -m \"not slow\"",
      "run_cmd": null,
      "last_task": "wake-word verifier handoff",
      "recent_files": ["backend/voice/wake.py", "backend/voice/listener_v2.py"],
      "updated_at": "2026-06-16T10:30:00"
    }
  }
}
```
API (pure-ish, all persistence funnels through `data_store`):
- `current() -> dict | None` — the active project profile (None if unset).
- `current_root() -> str` — active root, defaulting to the **Zendaya repo root** when nothing is set yet (so the very first "run the tests" works without setup).
- `set_current(name_or_path) -> dict` — resolve a spoken name (case-insensitive match against known `name`s) **or** a filesystem path to a registered project; register it on first sight (auto-detect `name` from the dir, default `test_cmd` per project type — see below); persist `current`; return the profile.
- `get_profile(root) -> dict` — profile for a root (creates a default if unseen).
- `update_profile(root, **fields) -> dict` — merge fields (e.g. `last_task`, `recent_files`, `test_cmd`), stamp `updated_at`, persist.
- `list_projects() -> list[dict]` — for "what projects do you know".
- `note_files(root, paths)` — convenience: push onto `recent_files` (dedup, cap ~10).
- `default_test_cmd(root) -> str` — heuristic: `pytest -q` if a `tests/` or `pytest.ini`/`pyproject` exists; `npm test` if `package.json`; else `pytest -q`. The Zendaya root seeds the known-good `pytest backend/tests -q -m "not slow"`.

`updated_at` uses the assistant's existing time source (no new dep). All writes go through `data_store` so there's one persistence path.

### 4.2 `skills/dev_voice.py` (new) — voice-coding orchestration — effort M

Each function targets a `root` (defaults to `project.current_root()`), returns a **short spoken-friendly string**, and updates the project profile as a side effect. All shell work goes through `coder.safe_shell` (so allowlist + `_is_under_safe_root` containment apply).

- `pytest_brief(root=None, test_cmd=None) -> str`
  - Resolve `test_cmd` (arg → profile `test_cmd` → `project.default_test_cmd`).
  - `coder.safe_shell(test_cmd, cwd=root)`; parse the pytest tail with `_parse_pytest(output)` → `{passed, failed, errors, first_failure}`.
  - Speak e.g. *"All 214 passed."* or *"2 failed, 212 passed. First: `test_wake_smoothing` — AssertionError."*
  - `update_profile(root, last_task=…)`; return the spoken line. Stash the raw failure + `test_cmd` so a following "fix it" can route to `run_with_autofix`/`edit_in_project`.
- `git_brief(root=None) -> str`
  - `coder.safe_shell("git status --short", cwd=root)` + `git diff --stat`; `_parse_git_status` → counts + file list.
  - If non-trivial, `coder._gen(...)` turns the stat into **one sentence**; else a templated line ("nothing to commit" / "3 files changed: …"). Speak it.
- `smart_commit(root=None, message=None) -> dict`
  - Gather `git status --short` + `git diff` (tracked changes). If nothing staged-able (no tracked modifications), return *"Nothing to commit — N untracked files, say 'commit including new files' if you want those too."* (untracked handled only on the explicit variant, still never `-A`).
  - `message = message or coder._gen(commit-msg prompt over the diff)` → a Conventional-Commits one-liner.
  - Return `{"confirm": True, "message": msg, "files": tracked_modified, "root": root}` — **does not commit yet**. The spoken confirm + the actual commit happen in the dispatcher (§5) so the verbal "yes/no" gate lives at the command layer, consistent with `apply_pending_edit`'s pending-action pattern.
- `do_commit(root, message, include_untracked=False) -> str`
  - Stage: `git add -u` (tracked) — and **only if** `include_untracked` was explicitly requested, additionally `git add <each new file>` by explicit path (never `-A`).
  - `git -c commit.gpgsign=false commit -m <message>`. Speak the resulting short SHA + subject. `update_profile(root, last_task="committed: "+subject)`. **Never** `git push`.
- `resume_brief(root=None) -> str`
  - Speak the profile: *"Working on Zendaya. Tests run with `pytest -m 'not slow'`. Last time: wake-word verifier handoff. Recent files: wake.py, listener_v2.py."* Pulls only from the profile (no shell).

Parsers (`_parse_pytest`, `_parse_git_status`) are **pure string→dict** functions — the unit-test surface.

### 4.3 `zendaya.py` wiring — effort S

Extend command routing with a small `parse_dev_command(user_text)` (kept separate from `parse_coder_request` for clarity), recognizing:
- "run (the) tests" / "run tests in `<project>`" → `pytest_brief`
- "what changed" / "git status" / "any changes" → `git_brief`
- "commit (this/that)" / "commit with message `<m>`" / "commit including new files" → `smart_commit` (→ pending confirm)
- "work on `<project>`" / "switch to `<path>`" / "open project `<x>`" → `set_current` + `resume_brief`
- "resume" / "where did we leave off" / "what was I doing" → `resume_brief`
- "what projects do you know" → `list_projects`

Dispatch mirrors the existing coder block (~line 3369). The commit confirm reuses the **pending-action** mechanism already used by `apply_pending_edit`: `smart_commit` returns `{"confirm": True, …}`, Zendaya speaks the message and arms a pending action; the user's next "yes" runs `do_commit`, "no"/timeout cancels.

## 5. Data flow

```
"run the tests"
  → parse_dev_command → dev_voice.pytest_brief(current_root)
      → coder.safe_shell(test_cmd, cwd)  → _parse_pytest → spoken triage
      → project.update_profile(last_task)            → send_response (spoken)

"commit this"
  → dev_voice.smart_commit(current_root)
      → safe_shell(git status/diff) → coder._gen(commit msg)
      → {"confirm": True, message, files}    → Zendaya speaks msg, arms pending action
"yes"
  → dev_voice.do_commit(root, message)
      → safe_shell("git add -u") → safe_shell("git -c commit.gpgsign=false commit -m …")
      → spoken SHA + subject  → project.update_profile(last_task)

"work on Foo"
  → project.set_current("Foo") → dev_voice.resume_brief → spoken briefing
```

## 6. Components & interfaces (isolation)

- `memory/project.py` — registry/profile/current-project; depends only on `data_store` + stdlib. No knowledge of shells or speech. Unit-testable with a temp data dir.
- `skills/dev_voice.py` — orchestration; depends on `coder` (safe_shell/_gen) + `project`. Pure parsers (`_parse_pytest`, `_parse_git_status`) are isolated and independently testable. Returns strings; does not call `send_response` itself.
- `zendaya.py` — `parse_dev_command` + dispatch + the spoken-confirm gate for commits. The only place speech + pending-action live.

## 7. Error handling & safety

**Commit safety (hard rules):**
- Commit requires an explicit spoken **"yes"** (the pending-action gate); "no"/silence/timeout cancels with no state change.
- Staging is **`git add -u` only** (tracked modifications). **Never** `git add -A`/`git add .`. New/untracked files are staged **only** on the explicit "commit including new files" variant, and then by **explicit per-file path**, never a wildcard.
- **Never** `git push` (out of scope; the user pushes themselves — consistent with the repo's git posture).
- Commits use `git -c commit.gpgsign=false commit` (matches session convention).
- All shell runs stay inside `_is_under_safe_root`; a project root outside safe roots → spoken refusal.

**Failure modes:**
- `git`/`pytest` not found, or command non-zero in a non-test way → spoken graceful message, no profile corruption.
- Gemini failure for a summary/commit message → fall back to a **templated** line (status counts / a generic `chore: update <n> files`), never block.
- Parser sees unexpected output → return a safe "couldn't parse, here's the raw tail" short message.
- `projects.json` missing/corrupt → treat as empty registry, re-seed the Zendaya default; never crash the loop.

## 8. Testing

`backend/tests/test_dev_voice.py` and `backend/tests/test_project_memory.py` (Gemini + shell mocked):

**`memory/project.py`:**
- Registry round-trips through a temp `zendaya_data`: `set_current` → `current()`/`current_root()` reflect it; persists across reload.
- `current_root()` defaults to the Zendaya repo when unset.
- `set_current` resolves by **name** (case-insensitive) and by **path**; registers unseen projects with a sane default `test_cmd`.
- `update_profile`/`note_files` merge + cap `recent_files`; `default_test_cmd` heuristics (pytest vs npm).

**`skills/dev_voice.py`:**
- `_parse_pytest` against fixture strings: all-pass; N-failed with a first-failure name+error; errors; empty/garbage tail → safe fallback.
- `_parse_git_status` against fixture `git status --short` output: clean; tracked-only; mixed tracked + untracked counts.
- `pytest_brief` (mock `safe_shell`) speaks the right triage and updates `last_task`.
- `git_brief` (mock `safe_shell` + `_gen`) returns one sentence; templated fallback when `_gen` raises.
- `smart_commit` returns `{"confirm": True, …}` and **does not** run any `git add`/`commit` (assert `safe_shell` only saw read-only `git status`/`git diff`).
- `do_commit` (mock `safe_shell`): asserts the staging call is **`git add -u`** and that **no** call contains `add -A`/`add .`; that commit uses `-c commit.gpgsign=false`; that `include_untracked=False` never stages new files; that **no** call is `git push`.
- A no-confirm path performs **no** commit.

**`zendaya.py`:** `parse_dev_command` routing table (each phrase → expected `type`); the commit pending-action gate: "commit this" arms a pending action, "yes" → `do_commit`, "no" → cancel.

Run: `venv\Scripts\python.exe -m pytest backend/tests -q -m "not slow"`.

## 9. Out of scope / YAGNI

- `git push` / branch management / PR creation (the user pushes; respects the repo's git posture).
- Multi-step autonomous coding agents (that's Pack D — safe autonomy).
- Inferring the project from the foreground window (deferred to Pack C perception).
- Streaming the test output live; we summarize the final result.
- Editing the test command by voice beyond `set` (heuristic default + profile field is enough for now).

## 10. Open risks

- **Spoken triage length:** very long tracebacks must compress to one or two sentences — the parser extracts only the first failure's test id + exception line; the rest is available as text but not spoken.
- **Commit message quality** depends on the Gemini diff summary; the spoken-confirm gate is the safety net (the user hears it before anything is committed), and a templated fallback covers brain failures.
- **Project-name disambiguation** by voice (homophones, partial names) — `set_current` matches case-insensitively and falls back to asking the user to repeat/spell if no unique match.
