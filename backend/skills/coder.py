"""
skills.coder — code generation, multi-file projects, and safe execution.

Builds on the single-file helpers already in zendaya.py (`generate_and_write_file`,
`edit_file_with_ai`). Adds:
    * write_file_smart      — single-file generate-and-write with hardened prompt
    * edit_file_smart       — edit with optional unified-diff preview + confirm
    * generate_project      — multi-file project from a JSON file manifest
    * read_project_context  — pack a project's text files for prompt context
    * edit_in_project       — project-aware edits across multiple files
    * run_code              — sandboxed subprocess runner (interpreter allowlist)

All Gemini calls go through a small wrapper that lazily imports the client from
the main `zendaya` module so this file stays importable on its own (e.g. for
unit testing the safety helpers).
"""

from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Gemini access (lazy, optional)
# ---------------------------------------------------------------------------

_CODE_SYSTEM_PROMPT = (
    "You are a senior software engineer working as a backend code generator. "
    "When the user asks for code, output ONLY the raw code or JSON the caller asked for. "
    "Never wrap output in markdown code fences (no ```). Never add explanatory prose. "
    "Never apologise. Produce production-quality, idiomatic code with sensible names "
    "and a short docstring or comment at the top of each file describing its purpose."
)


def _gemini():
    """Return (client, ready_bool). Imports lazily from the main brain module."""
    try:
        import zendaya as _z
        return getattr(_z, "_gemini_client", None), getattr(_z, "_GEMINI_READY", False)
    except Exception:
        return None, False


def _gen(prompt: str, system: Optional[str] = None) -> str:
    """Single Gemini call. Raises on failure so callers can decide what to do."""
    client, ready = _gemini()
    if not ready or client is None:
        raise RuntimeError("Gemini is offline — set GEMINI_API_KEY and check network.")
    contents = [system or _CODE_SYSTEM_PROMPT, prompt]
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )
    return (response.text or "").strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_+\-]*\s*\n?|\n?```\s*$", re.MULTILINE)


def _strip_code_fence(text: str) -> str:
    """Remove leading/trailing ``` fences if Gemini ignored the instruction."""
    if not text:
        return text
    s = text.strip()
    if s.startswith("```"):
        # Drop the first fence line.
        lines = s.split("\n")
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        s = "\n".join(lines)
    return s.strip()


def _expand(path: str) -> str:
    return os.path.realpath(os.path.expandvars(os.path.expanduser(path)))


_SAFE_ROOTS = [
    _expand("~/Desktop"),
    _expand("~/Documents"),
    _expand("~/Downloads"),
    _expand("~/Zendaya"),
]


def _is_under_safe_root(path: str) -> bool:
    """True if `path` is inside the user's home work areas. Used by run_code only."""
    rp = _expand(path)
    cwd = os.path.realpath(os.getcwd())
    roots = list(_SAFE_ROOTS) + [cwd]
    for root in roots:
        try:
            rp_p, root_p = Path(rp), Path(root)
            rp_p.relative_to(root_p)
            return True
        except ValueError:
            continue
    return False


def _ensure_parent(path: str) -> None:
    parent = os.path.dirname(_expand(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _file_type_hint(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return {
        ".html": "HTML", ".css": "CSS", ".js": "JavaScript", ".jsx": "React JSX",
        ".ts": "TypeScript", ".tsx": "React TSX", ".py": "Python", ".java": "Java",
        ".cpp": "C++", ".c": "C", ".sh": "Bash shell script", ".bat": "Windows batch",
        ".sql": "SQL", ".json": "JSON", ".xml": "XML", ".md": "Markdown",
        ".txt": "plain text", ".yml": "YAML", ".yaml": "YAML", ".toml": "TOML",
        ".rs": "Rust", ".go": "Go", ".rb": "Ruby", ".php": "PHP",
    }.get(ext, f"{ext.lstrip('.')} file" if ext else "plain text")


_TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".scss", ".json",
    ".md", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".sh", ".bat",
    ".rs", ".go", ".rb", ".php", ".java", ".cpp", ".c", ".h", ".hpp",
    ".xml", ".sql", ".env",
}

_SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", "dist", "build",
    ".next", ".cache", ".idea", ".vscode", "target",
}


# ---------------------------------------------------------------------------
# Syntax checks (used after write/edit and as a standalone agent action)
# ---------------------------------------------------------------------------

def _check_python(path: str) -> Tuple[bool, str]:
    proc = subprocess.run(
        [sys.executable, "-m", "py_compile", path],
        capture_output=True, text=True, timeout=20, shell=False,
    )
    if proc.returncode == 0:
        return True, "py_compile: ok"
    return False, f"py_compile: {(proc.stderr or proc.stdout).strip()[-1500:]}"


def _check_node(path: str) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["node", "--check", path],
            capture_output=True, text=True, timeout=15, shell=False,
        )
    except FileNotFoundError:
        return True, "node: skipped (node not installed)"
    if proc.returncode == 0:
        return True, "node --check: ok"
    return False, f"node --check: {(proc.stderr or proc.stdout).strip()[-1500:]}"


def _check_json(path: str) -> Tuple[bool, str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            json.load(f)
        return True, "json: ok"
    except Exception as e:
        return False, f"json: {e}"


def _check_typescript(path: str) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["npx", "--yes", "tsc", "--noEmit", "--allowJs", path],
            capture_output=True, text=True, timeout=45, shell=False,
        )
    except FileNotFoundError:
        return True, "tsc: skipped (npx not installed)"
    if proc.returncode == 0:
        return True, "tsc --noEmit: ok"
    return False, f"tsc --noEmit: {(proc.stdout or proc.stderr).strip()[-1500:]}"


_SYNTAX_CHECKERS = {
    ".py": _check_python,
    ".js": _check_node,
    ".mjs": _check_node,
    ".cjs": _check_node,
    ".json": _check_json,
    ".ts": _check_typescript,
    ".tsx": _check_typescript,
}


def syntax_check(path: str) -> Tuple[bool, str]:
    """
    Verify a file parses/compiles. Returns (ok, message).
    Unknown extensions return (True, "(no checker)") so the caller can move on.
    """
    expanded = _expand(path)
    if not os.path.isfile(expanded):
        return False, f"no such file: {expanded}"
    ext = os.path.splitext(expanded)[1].lower()
    checker = _SYNTAX_CHECKERS.get(ext)
    if checker is None:
        return True, f"(no syntax checker for {ext or 'extension-less file'})"
    try:
        return checker(expanded)
    except subprocess.TimeoutExpired:
        return False, "syntax check timed out"
    except Exception as e:
        return False, f"syntax check crashed: {e}"


# ---------------------------------------------------------------------------
# Single-file generation & editing
# ---------------------------------------------------------------------------

def write_file_smart(description: str, path: str) -> str:
    """Generate file content from a natural-language description and write to `path`."""
    if not description or not path:
        return "I need both a description and a path."
    expanded = _expand(path)
    file_type = _file_type_hint(path)

    prompt = (
        f"Create a {file_type} file. Spec from the user: {description}\n\n"
        f"Output ONLY the raw file content. No prose, no fences, no commentary."
    )
    try:
        raw = _gen(prompt)
    except Exception as e:
        return f"Couldn't generate that file: {e}"

    content = _strip_code_fence(raw)
    if not content.strip():
        return "Gemini returned an empty file — try rephrasing the request."

    try:
        _ensure_parent(expanded)
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        return f"Generated the file but couldn't save: {e}"

    msg = f"Wrote {os.path.basename(expanded)} ({len(content)} chars) to {expanded}"
    ok, check_msg = syntax_check(expanded)
    msg += f"\n[syntax] {'✓' if ok else '✗'} {check_msg}"
    return msg


def edit_file_smart(path: str, change: str, preview: bool = True) -> str:
    """
    Edit an existing file via Gemini.

    When `preview=True` and the change isn't tiny, returns a unified diff and
    stores the proposed write under MEM["pending_confirm"] so the user can
    confirm via the existing confirm flow (recognised action: "apply_edit").

    When `preview=False`, applies the edit immediately, after creating a .bak.
    """
    if not path or not change:
        return "I need both a file path and a change description."
    expanded = _expand(path)
    if not os.path.isfile(expanded):
        return f"I can't find the file: {expanded}"

    try:
        with open(expanded, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except Exception as e:
        return f"Error reading {os.path.basename(expanded)}: {e}"

    file_type = _file_type_hint(expanded)
    prompt = (
        f"Here is the current content of '{os.path.basename(expanded)}' ({file_type}):\n\n"
        f"---FILE START---\n{original}\n---FILE END---\n\n"
        f"Apply this change: {change}\n\n"
        f"Output ONLY the complete, modified file content. No fences, no prose."
    )
    try:
        raw = _gen(prompt)
    except Exception as e:
        return f"Couldn't generate the edit: {e}"

    new_content = _strip_code_fence(raw)
    if not new_content.strip():
        return "Gemini returned empty content — edit aborted."
    if new_content == original:
        return "Gemini returned the file unchanged — nothing to apply."

    if preview:
        diff_text = _summarise_diff(original, new_content, os.path.basename(expanded))
        try:
            import zendaya as _z
            _z.MEM["pending_confirm"] = {
                "action": "apply_edit",
                "path": expanded,
                "new_content": new_content,
            }
            _z.save_memory(_z.MEM)
        except Exception:
            return _apply_edit(expanded, original, new_content)
        return (
            f"Proposed edit to {os.path.basename(expanded)}:\n\n{diff_text}\n\n"
            f"Say 'confirm edit' to apply, or 'cancel' to discard."
        )

    return _apply_edit(expanded, original, new_content)


def _apply_edit(expanded_path: str, original: str, new_content: str) -> str:
    backup = expanded_path + ".bak"
    try:
        shutil.copy2(expanded_path, backup)
    except Exception:
        backup = None
    try:
        with open(expanded_path, "w", encoding="utf-8") as f:
            f.write(new_content)
    except Exception as e:
        return f"Failed to write changes: {e}"
    msg = f"Updated {os.path.basename(expanded_path)}"
    if backup:
        msg += f" (backup at {os.path.basename(backup)})"
    msg += "."
    ok, check_msg = syntax_check(expanded_path)
    msg += f"\n[syntax] {'✓' if ok else '✗'} {check_msg}"
    return msg


def apply_pending_edit(payload: dict) -> str:
    """Called by the confirm flow when MEM['pending_confirm']['action']=='apply_edit'."""
    path = payload.get("path")
    new_content = payload.get("new_content", "")
    if not path or not os.path.isfile(path):
        return "The file is gone — edit cancelled."
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            original = f.read()
    except Exception as e:
        return f"Couldn't re-read the file: {e}"
    return _apply_edit(path, original, new_content)


def _summarise_diff(a: str, b: str, name: str, max_lines: int = 40) -> str:
    diff = list(difflib.unified_diff(
        a.splitlines(), b.splitlines(),
        fromfile=f"a/{name}", tofile=f"b/{name}",
        n=2, lineterm="",
    ))
    if not diff:
        return "(no textual difference)"
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"... ({len(diff) - max_lines} more diff lines)"]
    return "\n".join(diff)


# ---------------------------------------------------------------------------
# Multi-file projects
# ---------------------------------------------------------------------------

def generate_project(spec: str, root_dir: str) -> str:
    """
    Generate a small multi-file project from a natural-language spec.

    Asks Gemini for a JSON manifest of the form:
        {"files": [{"path": "relative/path", "content": "..."}, ...],
         "run_cmd": "optional shell command to run/test the project"}

    Writes every file inside `root_dir` (containment-checked) and returns a
    summary plus the suggested run command.
    """
    if not spec or not root_dir:
        return "I need both a project spec and a target folder."
    root = _expand(root_dir)
    if os.path.exists(root) and not os.path.isdir(root):
        return f"Target {root} exists and isn't a folder."
    os.makedirs(root, exist_ok=True)

    prompt = (
        "Generate a complete small project as a strict JSON object. Schema:\n"
        '{"files": [{"path": "relative/file/path", "content": "raw file content"}, ...],\n'
        ' "run_cmd": "optional command to run or test the project, or null"}\n\n'
        "Rules:\n"
        "- Output ONLY the JSON object. No markdown fences. No prose.\n"
        "- Use forward-slash relative paths (e.g. 'src/app.py').\n"
        "- Keep the project minimal but functional. 2-12 files.\n"
        "- Include a README.md briefly explaining the project.\n"
        "- For Python projects, include requirements.txt if any third-party deps.\n"
        f"\nProject spec: {spec}"
    )
    try:
        raw = _gen(prompt)
    except Exception as e:
        return f"Couldn't generate the project: {e}"

    manifest = _parse_json_lenient(raw)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        return "Gemini didn't return a usable JSON manifest. Try a more specific spec."

    written: List[str] = []
    skipped: List[str] = []
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            continue
        rel = (entry.get("path") or "").strip().replace("\\", "/")
        content = entry.get("content")
        if not rel or content is None:
            continue
        # Containment check.
        target = _expand(os.path.join(root, rel))
        try:
            Path(target).resolve().relative_to(Path(root).resolve())
        except ValueError:
            skipped.append(rel)
            continue
        try:
            _ensure_parent(target)
            with open(target, "w", encoding="utf-8") as f:
                f.write(_strip_code_fence(str(content)) if isinstance(content, str) else json.dumps(content, indent=2))
            written.append(rel)
        except Exception:
            skipped.append(rel)

    if not written:
        return "I parsed the manifest but couldn't write any files."

    run_cmd = manifest.get("run_cmd") or ""
    summary = f"Wrote {len(written)} files into {root}:\n  - " + "\n  - ".join(written)
    if skipped:
        summary += f"\n(skipped {len(skipped)} unsafe/empty entries)"
    if run_cmd:
        summary += f"\n\nSuggested run command: {run_cmd}"
    return summary


def _parse_json_lenient(raw: str) -> Optional[dict]:
    """Try hard to recover a JSON object from a model response."""
    if not raw:
        return None
    s = _strip_code_fence(raw).strip()
    # Direct attempt.
    try:
        return json.loads(s)
    except Exception:
        pass
    # Find first '{' and last '}'.
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(s[start:end + 1])
        except Exception:
            return None
    return None


# ---------------------------------------------------------------------------
# Project-aware reading & editing
# ---------------------------------------------------------------------------

def read_project_context(root_dir: str, max_files: int = 15, max_chars_per_file: int = 4000) -> str:
    """Walk a project directory and pack the most relevant text files into a prompt block."""
    root = _expand(root_dir)
    if not os.path.isdir(root):
        return f"(no such directory: {root})"

    candidates: List[Tuple[str, int]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in _TEXT_EXTS:
                continue
            full = os.path.join(dirpath, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                continue
            if size > 200_000:
                continue
            candidates.append((full, size))

    # Prefer interesting files: README, entrypoints, then by smallest size first.
    def score(path: str, size: int) -> tuple:
        base = os.path.basename(path).lower()
        priority = 0
        if base.startswith("readme"):
            priority -= 5
        if base in ("main.py", "app.py", "index.js", "index.ts", "server.js", "server.py"):
            priority -= 3
        if base.endswith((".md", ".toml", ".yml", ".yaml", "requirements.txt", "package.json")):
            priority -= 2
        return (priority, size)

    candidates.sort(key=lambda c: score(*c))
    selected = candidates[:max_files]

    blocks: List[str] = [f"Project root: {root}", f"Total files considered: {len(candidates)}", ""]
    for full, _ in selected:
        rel = os.path.relpath(full, root).replace("\\", "/")
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            continue
        if len(content) > max_chars_per_file:
            content = content[:max_chars_per_file] + f"\n... (truncated, {len(content)} total chars)"
        blocks.append(f"--- FILE: {rel} ---\n{content}\n")
    return "\n".join(blocks)


def edit_in_project(root_dir: str, change: str) -> str:
    """Decide which files in a project need editing and apply changes to each."""
    if not root_dir or not change:
        return "I need a project folder and a change description."
    root = _expand(root_dir)
    if not os.path.isdir(root):
        return f"No such project folder: {root}"

    context = read_project_context(root)
    locate_prompt = (
        "You are looking at a project. Decide which files need to be edited to satisfy "
        "the user's change request. Output ONLY a strict JSON object of the form:\n"
        '{"files": [{"path": "relative/path", "instructions": "what to change in this file"}]}\n'
        "Pick at most 5 files. Use forward-slash relative paths exactly as shown.\n\n"
        f"{context}\n\nChange request: {change}"
    )
    try:
        raw = _gen(locate_prompt)
    except Exception as e:
        return f"Couldn't plan the edit: {e}"

    plan = _parse_json_lenient(raw)
    if not isinstance(plan, dict) or not isinstance(plan.get("files"), list):
        return "Gemini didn't return a usable edit plan."

    results: List[str] = []
    for item in plan["files"][:5]:
        if not isinstance(item, dict):
            continue
        rel = (item.get("path") or "").strip().replace("\\", "/")
        instr = (item.get("instructions") or "").strip()
        if not rel or not instr:
            continue
        target = _expand(os.path.join(root, rel))
        try:
            Path(target).resolve().relative_to(Path(root).resolve())
        except ValueError:
            results.append(f"- skipped {rel} (outside project)")
            continue
        if not os.path.isfile(target):
            # Allow creation if the model said so.
            outcome = write_file_smart(instr, target)
        else:
            outcome = edit_file_smart(target, instr, preview=False)
        results.append(f"- {rel}: {outcome}")

    if not results:
        return "Edit plan was empty — nothing changed."
    return f"Project edit complete in {root}:\n" + "\n".join(results)


# ---------------------------------------------------------------------------
# Sandboxed runner
# ---------------------------------------------------------------------------

_INTERPRETER_BY_EXT = {
    ".py": [sys.executable or "python"],
    ".js": ["node"],
    ".mjs": ["node"],
    ".sh": ["bash"],
    ".ps1": ["powershell", "-NoProfile", "-File"],
}


def run_code(path: str, timeout_s: int = 20, args: Optional[List[str]] = None) -> str:
    """
    Run a script file in a subprocess with a timeout and captured I/O.

    Refuses anything outside the user's safe roots. No shell. Interpreter is
    chosen from extension; unknown extensions are refused.
    """
    if not path:
        return "I need a path to run."
    expanded = _expand(path)
    if not os.path.isfile(expanded):
        return f"No such file: {expanded}"
    if not _is_under_safe_root(expanded):
        return (
            f"Refusing to run a script outside your work folders "
            f"(Desktop / Documents / Downloads / Zendaya / cwd). Path: {expanded}"
        )
    ext = os.path.splitext(expanded)[1].lower()
    if ext not in _INTERPRETER_BY_EXT:
        return f"I can only run {', '.join(sorted(_INTERPRETER_BY_EXT.keys()))} files. Got {ext or '(no extension)'}."
    cmd = list(_INTERPRETER_BY_EXT[ext]) + [expanded] + list(args or [])
    timeout_s = max(1, min(int(timeout_s), 120))
    started = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=os.path.dirname(expanded) or None,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"Killed after {timeout_s}s (timeout). Output up to that point was discarded."
    except FileNotFoundError as e:
        return f"Couldn't find the interpreter: {e}"
    except Exception as e:
        return f"Run failed: {e}"
    elapsed = time.time() - started
    out = (proc.stdout or "").rstrip()
    err = (proc.stderr or "").rstrip()
    if len(out) > 4000:
        out = out[:4000] + "\n... (stdout truncated)"
    if len(err) > 2000:
        err = err[:2000] + "\n... (stderr truncated)"
    parts = [f"exit={proc.returncode}, elapsed={elapsed:.1f}s"]
    if out:
        parts.append(f"--- stdout ---\n{out}")
    if err:
        parts.append(f"--- stderr ---\n{err}")
    if not out and not err:
        parts.append("(no output)")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Auto-fix loop — run, observe stderr, ask Gemini to patch, retry.
# ---------------------------------------------------------------------------

_ERROR_HINT_RE = re.compile(
    r"(Traceback|SyntaxError|NameError|TypeError|ValueError|ImportError|"
    r"ModuleNotFoundError|AttributeError|IndexError|KeyError|FileNotFoundError|"
    r"PermissionError|RuntimeError|Error:|error TS\d+|ReferenceError)",
    re.I,
)


def _looks_like_error(stderr: str, exit_code: int) -> bool:
    if exit_code == 0:
        return False
    return bool(stderr.strip())


def run_with_autofix(path: str, max_attempts: int = 3, timeout_s: int = 20) -> str:
    """
    Run a script. If it exits non-zero with a real error, ask Gemini to patch
    the file in place and try again. Up to `max_attempts` total runs.

    Each patch is applied without the diff-preview confirmation — this helper
    is meant to be invoked by the agent loop or by the user explicitly asking
    to "fix and run", and it always reports the full attempt history so the
    user can audit what changed.
    """
    expanded = _expand(path)
    if not os.path.isfile(expanded):
        return f"No such file: {expanded}"
    if not _is_under_safe_root(expanded):
        return "Refusing — that file isn't in your safe roots."

    attempts = max(1, min(int(max_attempts), 5))
    history: List[str] = []

    for attempt in range(1, attempts + 1):
        result = run_code(expanded, timeout_s=timeout_s)
        history.append(f"[attempt {attempt}] {result}")

        # Parse exit code out of the first line.
        first = result.splitlines()[0] if result else ""
        m = re.search(r"exit=(-?\d+)", first)
        exit_code = int(m.group(1)) if m else 1
        stderr_block = ""
        if "--- stderr ---" in result:
            stderr_block = result.split("--- stderr ---", 1)[1].strip()

        if not _looks_like_error(stderr_block, exit_code):
            return "\n\n".join(history) + f"\n\n✅ ran clean on attempt {attempt}."

        # Ask Gemini for a patch — feed it the file + the error.
        try:
            current = Path(expanded).read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            history.append(f"[attempt {attempt}] couldn't re-read file: {e}")
            break

        fix_prompt = (
            "The script below failed when executed. Rewrite the FULL file so it runs cleanly. "
            "Output ONLY the corrected file contents — no markdown, no commentary, no fences. "
            "Preserve the original purpose; change the smallest amount needed to fix the error.\n\n"
            f"--- file: {os.path.basename(expanded)} ---\n{current}\n\n"
            f"--- runtime error ---\n{stderr_block[:2000]}\n"
        )
        try:
            patched = _strip_code_fence(_gen(fix_prompt))
        except Exception as e:
            history.append(f"[attempt {attempt}] Gemini patch failed: {e}")
            break
        if not patched.strip() or patched.strip() == current.strip():
            history.append(f"[attempt {attempt}] Gemini returned no useful change — stopping.")
            break

        # Backup + write.
        try:
            shutil.copy2(expanded, expanded + ".bak")
            Path(expanded).write_text(patched, encoding="utf-8")
            history.append(f"[attempt {attempt}] applied patch ({len(patched)} chars).")
        except Exception as e:
            history.append(f"[attempt {attempt}] couldn't write patch: {e}")
            break

    return "\n\n".join(history) + f"\n\n❌ still failing after {attempts} attempt(s)."


# ---------------------------------------------------------------------------
# Code-aware search & listing (used by the agent loop)
# ---------------------------------------------------------------------------

def grep_files(root_dir: str, pattern: str, max_hits: int = 60, ignore_case: bool = True) -> str:
    """
    Search text files under `root_dir` for `pattern` (regex). Refuses outside safe roots.
    Returns a compact listing: 'rel/path:line: text'.
    """
    root = _expand(root_dir)
    if not os.path.isdir(root):
        return f"(no such folder: {root})"
    if not _is_under_safe_root(root):
        return f"Refusing — {root} isn't inside your safe roots."
    try:
        rx = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        return f"(bad regex: {e})"
    hits: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in _TEXT_EXTS:
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    for lineno, line in enumerate(f, start=1):
                        if rx.search(line):
                            rel = os.path.relpath(full, root).replace("\\", "/")
                            hits.append(f"{rel}:{lineno}: {line.rstrip()[:200]}")
                            if len(hits) >= max_hits:
                                return "\n".join(hits) + f"\n... (truncated at {max_hits})"
            except Exception:
                continue
    return "\n".join(hits) if hits else "(no matches)"


def list_files(root_dir: str, max_entries: int = 200) -> str:
    """List files under `root_dir`, skipping noise dirs. Refuses outside safe roots."""
    root = _expand(root_dir)
    if not os.path.isdir(root):
        return f"(no such folder: {root})"
    if not _is_under_safe_root(root):
        return f"Refusing — {root} isn't inside your safe roots."
    out: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                size = os.path.getsize(full)
            except OSError:
                size = 0
            out.append(f"{rel}\t{size}")
            if len(out) >= max_entries:
                return "\n".join(out) + f"\n... (truncated at {max_entries})"
    return "\n".join(out) if out else "(empty)"


# ---------------------------------------------------------------------------
# Sandboxed shell — narrow allowlist of dev commands inside safe roots.
# ---------------------------------------------------------------------------

_SHELL_ALLOWLIST = {
    # exact program names allowed; arguments are unrestricted but command runs without shell=True
    "pip", "pip3", "python", "python3",
    "node", "npm", "npx", "yarn", "pnpm",
    "git", "tsc", "eslint", "prettier",
    "pytest", "ruff", "black", "mypy", "flake8",
    "go", "cargo", "rustc",
}


def safe_shell(command: str, cwd: Optional[str] = None, timeout_s: int = 60) -> str:
    """
    Run a single dev command (no shell, no chaining) inside a safe-root cwd.

    `command` is split into argv. The first token must be in _SHELL_ALLOWLIST.
    Disallowed metacharacters: | & ; > < ` $ ( ) — anything that needs a shell.
    """
    if not command or not command.strip():
        return "(empty command)"
    if any(ch in command for ch in "|&;><`$()"):
        return "Refusing: shell metacharacters not allowed. Run one program at a time."
    try:
        import shlex
        argv = shlex.split(command, posix=False)
    except Exception as e:
        return f"Couldn't parse command: {e}"
    if not argv:
        return "(empty command)"
    program = os.path.basename(argv[0]).lower()
    if program.endswith(".exe"):
        program = program[:-4]
    if program not in _SHELL_ALLOWLIST:
        return f"Refusing: '{program}' isn't on the allowlist {sorted(_SHELL_ALLOWLIST)}."

    workdir = _expand(cwd) if cwd else os.getcwd()
    if not os.path.isdir(workdir):
        return f"(no such cwd: {workdir})"
    if not _is_under_safe_root(workdir):
        return f"Refusing: cwd {workdir} isn't inside your safe roots."

    timeout_s = max(1, min(int(timeout_s), 300))
    started = time.time()
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout_s,
            cwd=workdir, shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"Killed after {timeout_s}s (timeout)."
    except FileNotFoundError as e:
        return f"Couldn't find program: {e}"
    except Exception as e:
        return f"Run failed: {e}"
    elapsed = time.time() - started
    out = (proc.stdout or "").rstrip()
    err = (proc.stderr or "").rstrip()
    if len(out) > 4000:
        out = out[:4000] + "\n... (stdout truncated)"
    if len(err) > 2000:
        err = err[:2000] + "\n... (stderr truncated)"
    parts = [f"$ {command}", f"exit={proc.returncode}, elapsed={elapsed:.1f}s"]
    if out:
        parts.append(f"--- stdout ---\n{out}")
    if err:
        parts.append(f"--- stderr ---\n{err}")
    if not out and not err:
        parts.append("(no output)")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("skills.coder loaded.")
    print("Safe roots:", _SAFE_ROOTS)
