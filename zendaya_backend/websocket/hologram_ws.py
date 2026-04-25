from fastapi import APIRouter, WebSocket
import json
import asyncio
import random

router = APIRouter()
clients = set()

@router.websocket("/ws/hologram")
async def hologram_ws(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)
    print("🪩 Hologram client connected")

    try:
        while True:
            # Send fake amplitude until voice engine streams real data
            await websocket.send_text(json.dumps({
                "type": "heartbeat",
                "amplitude": random.random(),
                "status": "online"
            }))
            await asyncio.sleep(0.1)
    except Exception:
        pass
    finally:
        clients.remove(websocket)
        print("Hologram client disconnected")

async def broadcast_amplitude(amplitude: float):
    """Broadcast live voice amplitude to all hologram clients"""
    if not clients:
        return
    data = json.dumps({"type": "amplitude", "amplitude": amplitude})
    for ws in list(clients):
        try:
            await ws.send_text(data)
        except Exception:
            clients.remove(ws)
