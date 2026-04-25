from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class User(BaseModel):
    """User model for authentication and identification"""
    id: str
    username: str
    email: str
    full_name: str
    disabled: bool = False
    created_at: datetime = datetime.utcnow()
    updated_at: Optional[datetime] = None