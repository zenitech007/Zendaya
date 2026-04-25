from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, TypeVar, Generic
from datetime import datetime

T = TypeVar('T')

class ServiceResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    status: Optional[str] = None  # Added status field as optional with None default

class StatusResponse(BaseModel):  # Renamed from ServiceResponse
    message: str
    status: str = "online"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, Any]
    discovered_devices: int
    registered_users: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None

class ChatResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    actions: List[Dict[str, Any]] = []

class WorkflowResponse(BaseModel):
    id: str
    status: str
    tasks: Optional[List[Dict[str, Any]]] = None

class APIServiceResponse(BaseModel, Generic[T]):
    """Generic API response wrapper"""
    success: bool
    message: str
    data: Optional[T] = None