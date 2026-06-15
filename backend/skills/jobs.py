"""
skills.jobs — multi-agent job queue.

Lets Zendaya run several BONSAI agent goals in parallel without blocking the
main console / voice loop. Each submitted goal becomes a job with an id;
results are pushed back via send_response when complete.

Public API:
    submit(goal, max_steps=None, wall_clock_s=None) -> str       # returns job id
    list_jobs() -> list[dict]                                     # all jobs (newest first)
    get_job(job_id) -> dict | None
    cancel(job_id) -> str
    running_count() -> int

Each job dict has:
    {id, goal, status, started, finished, summary, max_steps, wall_clock_s, thread}
status ∈ {"queued", "running", "done", "failed", "cancelled"}

Concurrency:
    - Each job runs on its own daemon thread, with its own RunHandle.
    - skills.agent.run_agent now takes a per-call RunHandle, so multiple jobs
      execute truly in parallel. Each job stores its handle so cancel(id) can
      stop just that one without touching its siblings.
    - Cancellation is cooperative: cancel(id) sets the per-job RunHandle's
      cancel event; the agent loop checks it between steps.
"""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Dict, List, Optional


_JOBS_LOCK = threading.Lock()
_JOBS: Dict[str, Dict[str, Any]] = {}


def _z():
    import zendaya as _zmod
    return _zmod


def _agent():
    import skills.agent as _amod
    return _amod


def _now() -> float:
    return time.time()


def _short_id() -> str:
    return uuid.uuid4().hex[:8]


def submit(goal: str, max_steps: Optional[int] = None, wall_clock_s: Optional[int] = None) -> str:
    """Queue a new agent goal. Returns the job id immediately."""
    goal = (goal or "").strip()
    if not goal:
        raise ValueError("goal is empty")
    job_id = _short_id()
    job = {
        "id": job_id,
        "goal": goal,
        "status": "queued",
        "started": None,
        "finished": None,
        "summary": "",
        "max_steps": max_steps,
        "wall_clock_s": wall_clock_s,
        "thread": None,
        "cancel_requested": False,
        "handle": None,
    }
    with _JOBS_LOCK:
        _JOBS[job_id] = job
    t = threading.Thread(target=_run_job, args=(job_id,), daemon=True, name=f"agent-{job_id}")
    job["thread"] = t
    t.start()
    return job_id


def _run_job(job_id: str) -> None:
    job = _JOBS.get(job_id)
    if job is None:
        return
    if job["cancel_requested"]:
        with _JOBS_LOCK:
            job["status"] = "cancelled"
            job["finished"] = _now()
            job["summary"] = "Cancelled before start."
        _notify(job)
        return
    agent = _agent()
    handle = agent.new_handle()
    with _JOBS_LOCK:
        job["handle"] = handle
        job["status"] = "running"
        job["started"] = _now()
    try:
        kwargs: Dict[str, Any] = {"handle": handle}
        if job["max_steps"] is not None:
            kwargs["max_steps"] = job["max_steps"]
        if job["wall_clock_s"] is not None:
            kwargs["wall_clock_s"] = job["wall_clock_s"]
        summary = agent.run_agent(job["goal"], **kwargs)
        with _JOBS_LOCK:
            job["status"] = "cancelled" if job["cancel_requested"] else "done"
            job["finished"] = _now()
            job["summary"] = summary or "(no summary)"
    except Exception as e:
        with _JOBS_LOCK:
            job["status"] = "failed"
            job["finished"] = _now()
            job["summary"] = f"Agent crashed: {e}"
    _notify(job)


def _notify(job: Dict[str, Any]) -> None:
    """Push job completion back through Zendaya's main response channel."""
    try:
        z = _z()
        prefix = {
            "done": "Agent done",
            "failed": "Agent failed",
            "cancelled": "Agent cancelled",
        }.get(job["status"], "Agent")
        elapsed = ""
        if job["started"] and job["finished"]:
            elapsed = f" ({job['finished'] - job['started']:.0f}s)"
        msg = f"{prefix} [{job['id']}]{elapsed}: {job['summary']}"
        z.send_response(msg)
    except Exception:
        pass


def cancel(job_id: str) -> str:
    job = _JOBS.get(job_id)
    if job is None:
        return f"No such job: {job_id}"
    if job["status"] in ("done", "failed", "cancelled"):
        return f"Job {job_id} already {job['status']}."
    job["cancel_requested"] = True
    # Signal just THIS job's handle — sibling jobs keep running.
    try:
        h = job.get("handle")
        if h is not None:
            h.cancel()
    except Exception:
        pass
    return f"Cancellation requested for {job_id}."


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    job = _JOBS.get(job_id)
    if job is None:
        return None
    return _public_view(job)


def list_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    with _JOBS_LOCK:
        items = list(_JOBS.values())
    items.sort(key=lambda j: (j["started"] or j.get("queued_at") or 0), reverse=True)
    return [_public_view(j) for j in items[:limit]]


def running_count() -> int:
    with _JOBS_LOCK:
        return sum(1 for j in _JOBS.values() if j["status"] in ("queued", "running"))


def _public_view(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": job["id"],
        "goal": job["goal"],
        "status": job["status"],
        "started": job["started"],
        "finished": job["finished"],
        "summary": job["summary"],
    }


def render_status() -> str:
    """Human-friendly listing for the user."""
    items = list_jobs(limit=10)
    if not items:
        return "No agent jobs yet."
    lines = []
    for j in items:
        elapsed = ""
        if j["started"]:
            end = j["finished"] or _now()
            elapsed = f" {end - j['started']:.0f}s"
        snippet = (j["summary"] or "").splitlines()[0][:80] if j["summary"] else j["goal"][:80]
        lines.append(f"  [{j['id']}] {j['status']:<9}{elapsed:>6}  {snippet}")
    return "Agent jobs:\n" + "\n".join(lines)
