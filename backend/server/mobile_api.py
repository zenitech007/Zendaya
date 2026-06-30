"""Mobile API router for the Zendaya Android app. Mounted under /api/v1.

All routes require a valid bearer token (see server.mobile_auth). The chat
route runs a synchronous turn through the brain and returns the reply text.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from server.mobile_auth import require_token

router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_token)])


class MobileChatIn(BaseModel):
    message: str


@router.get("/health")
def mobile_health():
    return {"ok": True, "name": "Zendaya"}


@router.post("/chat")
def mobile_chat(payload: MobileChatIn):
    # Imported here (not at module load) to avoid an import cycle with
    # state_server, which mounts this router.
    from server.state_server import chat_sync
    return chat_sync(payload.message)
