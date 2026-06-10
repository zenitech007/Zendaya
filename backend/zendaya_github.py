"""
zendaya_github — `gh` CLI wrapper.

Thin, safe shell over GitHub's official CLI. Every public function returns a
trimmed string the brain can read aloud or feed back into a planning loop.

    auth_status()              -> str
    repo_clone(url, dest=None) -> str   (clone into ~/Zendaya/repos/)
    repo_list(owner=None)      -> str
    issue_list(repo=None)      -> str
    issue_view(num, repo=None) -> str
    pr_list(repo=None)         -> str
    pr_view(num, repo=None)    -> str
    pr_diff(num, repo=None)    -> str
    pr_create(title, body)     -> str   (stages behind pending_confirm)

Hard guarantees:
    * `shell=False` everywhere; arguments are passed as a list.
    * `gh` must already be installed and authenticated; we don't try to do
      either ourselves (auth flows are interactive).
    * Mutating commands (`pr create`) stage MEM["pending_confirm"] so the
      existing yes/no flow handles approval. Read-only commands run inline.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

_REPO_ROOT = Path(os.path.expanduser("~/Zendaya/repos"))
_REPO_ROOT.mkdir(parents=True, exist_ok=True)


def _gh() -> Optional[str]:
    return shutil.which("gh")


def _mem() -> Optional[dict]:
    try:
        import zendaya as _z
        return getattr(_z, "MEM", None)
    except Exception:
        return None


def _run(args: List[str], cwd: Optional[str] = None, timeout: int = 60) -> str:
    gh = _gh()
    if not gh:
        return "GitHub CLI (`gh`) isn't installed. Run: `winget install --id GitHub.cli`."
    try:
        proc = subprocess.run(
            [gh, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return f"`gh {args[0] if args else ''}` timed out after {timeout}s."
    except Exception as e:
        return f"gh failed: {e}"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        msg = err or out or f"exit {proc.returncode}"
        return f"gh error: {msg[:1500]}"
    return out[:6000] if out else "(no output)"


def auth_status() -> str:
    return _run(["auth", "status"])


def repo_clone(url: str, dest: Optional[str] = None) -> str:
    if not url:
        return "I need a repo URL or owner/name."
    name = dest or re.sub(r"[^A-Za-z0-9._\-]+", "_", url.rsplit("/", 1)[-1].replace(".git", ""))
    target = _REPO_ROOT / name
    if target.exists():
        return f"Already cloned at {target}. Pull manually if you want to update."
    return _run(["repo", "clone", url, str(target)])


def repo_list(owner: Optional[str] = None) -> str:
    args = ["repo", "list", "--limit", "30"]
    if owner:
        args.insert(2, owner)
    return _run(args)


def issue_list(repo: Optional[str] = None) -> str:
    args = ["issue", "list", "--limit", "20"]
    if repo:
        args += ["--repo", repo]
    return _run(args)


def issue_view(number: int, repo: Optional[str] = None) -> str:
    args = ["issue", "view", str(int(number))]
    if repo:
        args += ["--repo", repo]
    return _run(args)


def pr_list(repo: Optional[str] = None) -> str:
    args = ["pr", "list", "--limit", "20"]
    if repo:
        args += ["--repo", repo]
    return _run(args)


def pr_view(number: int, repo: Optional[str] = None) -> str:
    args = ["pr", "view", str(int(number))]
    if repo:
        args += ["--repo", repo]
    return _run(args)


def pr_diff(number: int, repo: Optional[str] = None) -> str:
    args = ["pr", "diff", str(int(number))]
    if repo:
        args += ["--repo", repo]
    out = _run(args, timeout=90)
    if len(out) > 6000:
        return out[:6000] + "\n... (diff truncated)"
    return out


def pr_create(title: str, body: str = "", repo_dir: Optional[str] = None) -> str:
    """Stage a PR creation. The user must confirm before we actually push."""
    if not title.strip():
        return "PR needs a title."
    cwd = repo_dir or os.getcwd()
    if not os.path.isdir(os.path.join(cwd, ".git")):
        return f"`{cwd}` doesn't look like a git repo. cd to one or pass repo_dir."
    mem = _mem()
    if mem is None:
        return "Memory isn't available; can't stage the PR confirmation."
    mem["pending_confirm"] = {
        "action": "gh_pr_create",
        "title": title.strip(),
        "body": body.strip(),
        "cwd": cwd,
        "ts": time.time(),
    }
    return (
        f"Ready to open PR **{title.strip()}** from `{cwd}`. "
        f"Say yes to push and create, or no to cancel."
    )


def confirm_pr_create(pending: Dict) -> str:
    title = pending.get("title") or ""
    body = pending.get("body") or ""
    cwd = pending.get("cwd") or os.getcwd()
    if not title:
        return "Lost the PR title — try again."
    args = ["pr", "create", "--title", title, "--body", body, "--fill"]
    return _run(args, cwd=cwd, timeout=120)
