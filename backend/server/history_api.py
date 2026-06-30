"""History API for the Zendaya Android app. Mounted under /api/v1.

Serves the durable conversation transcript (memory.transcripts) so the phone
can browse past days. All routes require a bearer token (server.mobile_auth).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from server.mobile_auth import require_token

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])


@router.get("/history/days")
def history_days():
    from memory import transcripts
    return {"days": transcripts.list_days()}


@router.get("/history")
def history_day(day: str = Query(default="")):
    day = (day or "").strip()
    if not day:
        raise HTTPException(status_code=400, detail="missing 'day' query param")
    from memory import transcripts
    return {"day": day, "messages": transcripts.get_day(day)}
