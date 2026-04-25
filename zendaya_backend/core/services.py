"""Service management and initialization."""

from typing import Dict, Any, Optional
from fastapi import FastAPI
from unittest.mock import Mock
import logging

# Fix the imports to use full package paths
from zendaya_backend.services.chat import ChatService
from zendaya_backend.core.gemini import GeminiService
from zendaya_backend.core.error_engine import ErrorUnderstandingEngine
from zendaya_backend.core.health import HealthCache
from zendaya_backend.core.config import settings
from zendaya_backend.knowledge.voice_service import VoiceService

logger = logging.getLogger(__name__)

class ServiceManager:
    def __init__(self):
        self.app: Optional[FastAPI] = None
        self._services: Dict[str, Any] = {}
        
    async def initialize(self, app: FastAPI):
        """Initialize with app context"""
        self.app = app
        await self.initialize_services()
    
    async def initialize_services(self):
        """Initialize all services with fallbacks"""
        if not self.app:
            raise RuntimeError("FastAPI app not initialized. Call initialize() first")
            
        services = {
            "chat_service": (ChatService, Mock),
            "gemini_service": (GeminiService, Mock),
            "voice_service": (VoiceService, Mock),
            # ...other services
        }
        
        for name, (service_class, fallback) in services.items():
            try:
                instance = service_class() if service_class else fallback()
                setattr(self.app.state, name, instance)
                self._services[name] = instance
            except Exception as e:
                logger.warning(f"Failed to initialize {name}: {e}")
                setattr(self.app.state, name, fallback())