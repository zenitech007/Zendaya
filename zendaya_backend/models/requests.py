from pydantic import BaseModel, validator
from typing import Optional, Dict, Any

class ChatRequest(BaseModel):
    """Chat request with validation"""
    message: str
    user_id: Optional[str] = "default"
    context: Optional[Dict[str, Any]] = None
    
    @validator("message")
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()