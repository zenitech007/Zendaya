# backend/utils/supabase_auth.py
import jwt, os
from fastapi import HTTPException

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

def verify_token_admin(token: str):
    if not token:
        raise HTTPException(403, "Missing token")

    try:
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])

        if payload.get("role") != "admin":
            raise HTTPException(403, "Admin only")

        return payload
        
    except Exception:
        raise HTTPException(403, "Invalid token")
