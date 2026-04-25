"""
Refactored auth.py for FastAPI + Supabase (supabase-py)

Features:
- Unifies auth validation using the Supabase API as the single source of truth.
- Fixes security hole where WebSockets could be accessed with revoked tokens.
- Makes all auth calls non-blocking using asyncio.to_thread to prevent
  server stalls.
- Provides a single, secure `get_current_active_user` (async) dependency.
- Provides a simple `verify_token` (async) helper for WebSockets.
- Provides `get_optional_user` (async) for non-protected routes.

Environment variables required:
- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_JWT_SECRET (Still recommended, but no longer used for local validation)
"""
from typing import Optional, Dict, Any
import os
import asyncio
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

# Note: jwt and PyJWTError are no longer needed as we won't validate locally.
from supabase import create_client, Client

# ---------------------------------------------------------------------------
# Configuration / environment
# ---------------------------------------------------------------------------
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment"
    )

# Initialize supabase client with service role key (server-side only)
# We type-hint the client for better editor support.
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class User(BaseModel):
    id: str
    email: Optional[str] = None
    aud: Optional[str] = None
    exp: Optional[int] = None
    raw: Optional[Dict[str, Any]] = None

# ---------------------------------------------------------------------------
# Security scheme
# ---------------------------------------------------------------------------
# We set auto_error=False so we can provide custom error messages and flow.
security = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Core Asynchronous Helper
# ---------------------------------------------------------------------------

def _fetch_user_from_supabase_sync(token: str) -> Dict[str, Any]:
    """
    Synchronous, blocking function to fetch a user from Supabase.
    This is designed to be run in a thread.
    
    Raises:
        Exception: If the token is invalid or the Supabase API call fails.
    """
    # supabase.auth.get_user expects the JWT access token.
    # It will raise an exception if the token is invalid (expired, bad sig, etc.)
    resp = supabase.auth.get_user(token)

    # The response shape can be either a dict with 'user' key or an object with 'data'.
    if isinstance(resp, dict):
        user_obj = resp.get("user") or resp.get("data")
    else:
        user_obj = getattr(resp, "user", None) or getattr(resp, "data", None)
    
    if not user_obj:
        raise Exception("User not found in Supabase response")

    # We must convert the user object to a dict *here* in the sync
    # function, as the original object may not be thread-safe.
    if hasattr(user_obj, "to_dict"):
        return user_obj.to_dict() # Handle Pydantic-like models
    elif isinstance(user_obj, dict):
        return user_obj # Already a dict
    elif hasattr(user_obj, "__dict__"):
        return user_obj.__dict__ # Handle simple objects
    else:
        # Fallback: try to get common attributes
        return {
            "id": getattr(user_obj, "id", None),
            "email": getattr(user_obj, "email", None),
            "aud": getattr(user_obj, "aud", None),
            "exp": getattr(user_obj, "exp", None),
        }

async def verify_token(token: str) -> User:
    """
    Asynchronously verifies a token against the Supabase API.
    This is the single source of truth for all authentication.
    
    Raises HTTPException(401) on failure.
    """
    try:
        user_obj = await asyncio.to_thread(_fetch_user_from_supabase_sync, token)
        
        if not user_obj or not user_obj.get("id"):
             raise Exception("Invalid user object received from Supabase")

        # Normalize into our User model.
        user_data = {
            "id": user_obj.get("id"),
            "email": user_obj.get("email"),
            "aud": user_obj.get("aud"),
            "exp": user_obj.get("exp"),
            "raw": user_obj,
        }
        return User(**user_data)
        
    except Exception as e:
        # Catches exceptions from _fetch_user_from_supabase_sync (e.g., bad token)
        # or from our own validation.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ---------------------------------------------------------------------------
# Main Dependencies
# ---------------------------------------------------------------------------

async def get_current_active_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> User:
    """
    Async FastAPI dependency that:
    1. Extracts bearer token.
    2. Validates it against the Supabase API (the single source of truth).
    
    Returns a User object on success or raises HTTPException(401) on failure.
    """
    if credentials is None or not credentials.scheme.lower() == "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Securely verify the token and get the user in one non-blocking call.
    return await verify_token(token)


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[User]:
    """
    Async dependency for optional users. Returns None instead of 401.
    """
    if credentials is None:
        return None
    try:
        # We must await the async dependency
        return await get_current_active_user(credentials)
    except HTTPException:
        return None