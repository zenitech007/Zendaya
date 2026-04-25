# backend/routes/system_ws.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from datetime import datetime
from ..utils.supabase_auth import verify_token_admin
import psutil, asyncio, json

router = APIRouter()

active_connections = set()

async def broadcast(message: dict):
    msg = json.dumps(message)
    for ws in list(active_connections):
        try:
            await ws.send_text(msg)
        except:
            active_connections.remove(ws)

@router.websocket("/ws")
async def system_ws(websocket: WebSocket, token: str = None):
    # ✅ require admin JWT
    user = verify_token_admin(token)
    if not user:
        await websocket.close()
        return    

    await websocket.accept()
    active_connections.add(websocket)

    try:
        while True:
            # ✅ OS metrics
            data = {
                "type": "system_status",
                "data": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "cpu": psutil.cpu_percent(),
                    "memory": psutil.virtual_memory().percent,
                    "disk": psutil.disk_usage("/").percent,
                    "network": psutil.net_io_counters().bytes_sent != 0,
                }
            }
            await websocket.send_json(data)
            await asyncio.sleep(2)  # send every 2s

    except WebSocketDisconnect:
        active_connections.remove(websocket)
