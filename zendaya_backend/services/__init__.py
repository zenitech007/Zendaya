"""
Services package for Zendaya AI Assistant.
Contains core service implementations for chat, voice, biometrics, etc.
"""

from typing import Dict, Any, Optional
from .chat import ChatService
from ..knowledge.voice_service import VoiceService
from ..knowledge.biometric_recognition import BiometricRecognitionSystem  # Updated import path
from ..agent.tools.smart_home_controller import SmartHomeController
from ..agent.workflow_orchestrator import WorkflowOrchestrator
from ..knowledge.rag_service import RAGService  # Updated import path

# Export service classes
__all__ = [
    'ChatService',
    'VoiceService', 
    'BiometricRecognitionSystem',
    'SmartHomeController',
    'WorkflowOrchestrator',
    'RAGService',
    'get_service_map'
]

# Service instances
_chat_service: Optional[ChatService] = None
_voice_service: Optional[VoiceService] = None
_biometric_system: Optional[BiometricRecognitionSystem] = None
_smart_home: Optional[SmartHomeController] = None
_workflow_orchestrator: Optional[WorkflowOrchestrator] = None
_rag_service: Optional[RAGService] = None

def get_service_map() -> Dict[str, Any]:
    """
    Returns a mapping of all initialized services.
    Used for dependency injection and testing.
    """
    return {
        "chat_service": _chat_service,
        "voice_service": _voice_service,
        "biometric_system": _biometric_system,
        "smart_home": _smart_home,
        "workflow_orchestrator": _workflow_orchestrator,
        "rag_service": _rag_service
    }