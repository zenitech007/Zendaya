# backend/routes/system_actions.py
from fastapi import APIRouter, Depends, HTTPException
from ..utils.supabase_auth import verify_token_admin
import subprocess

router = APIRouter(prefix="/system")

@router.post("/restart/{service}")
async def restart_service(service: str, user=Depends(verify_token_admin)):
    try:
        subprocess.run(["systemctl", "restart", service], check=True)
        return {"ok": True, "msg": f"{service} restarted"}
    except:
        raise HTTPException(500, f"Failed to restart {service}")

@router.post("/reboot")
async def reboot(user=Depends(verify_token_admin)):
    subprocess.run(["reboot"])
    return {"ok": True}
