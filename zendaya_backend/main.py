"""
Refactored and consolidated zendaya_backend/main.py

Goals:
- Remove duplicates, fix inconsistencies, and make startup/shutdown robust.
- Avoid heavy work at import time so tests can import the app safely.
- Provide defensive fallbacks/mocks for optional modules.
- Provide clear exception handlers, request-id middleware, and health caching.
- Integrate WebSocket-based real-time system broadcasting.
- Keep endpoints and behavior compatible with prior tests (placeholders remain
  so tests can patch module attributes).
"""

import os
import asyncio
import logging
logging.getLogger("comtypes").setLevel(logging.ERROR)
import uuid
import json
import base64
import psutil
import io
from starlette.status import WS_1011_INTERNAL_ERROR

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zendaya_backend.knowledge.biometric_recognition import BiometricRecognitionSystem
from zendaya_backend.core.error_engine import ErrorUnderstandingEngine
from zendaya_backend.knowledge.voice_service import VoiceService, preload_voice_service
from zendaya_backend.services.stt_service import STTService
from zendaya_backend.services.memory_service import memory_service

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from fastapi import (
    FastAPI,
    Request,
    WebSocket,
    HTTPException,
    Depends,
    File,
    UploadFile,
    status, Query
)
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.websockets import WebSocketDisconnect
from fastapi.websockets import WebSocketState # Added this import
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator
from jose import jwt, JWTError

# ---------------------------
# Defensive / optional imports
# ---------------------------
# These imports may not be present in a test env; use fallbacks so tests don't fail.
try:
    from zendaya_backend.core.config import settings  # real settings in prod
except Exception:
    class _DummySettings:
        app_name = "Zendaya AI Assistant"
        app_version = "0.0.0"
        debug = True
        allowed_origins = ["*"]
        access_token_expire_minutes = 60
        websocket_heartbeat_interval = 5
        secret_key = "dummy-secret-key-for-testing"
        algorithm = "HS256"
    settings = _DummySettings()

# Auth / DB / Services (optional)
try:
    from zendaya_backend.core.security import (
        create_access_token,
        get_current_user,
        User,
        OAuth2PasswordBearer
    )
    oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")
except Exception:
    # minimal compatible placeholders
    from pydantic import BaseModel as _BaseModel
    class User(_BaseModel):
        username: str = "test"
        disabled: bool = False

    async def get_current_user(token: str):
        raise HTTPException(status_code=401, detail="Auth not configured in test env")

    async def get_current_active_user(token: str = Depends(lambda: None)) -> User:
        raise HTTPException(status_code=401, detail="Auth not configured in test env")

    def create_access_token(data: dict, expires_delta=None) -> str:
        # Minimal JWT-ish fallback (not secure) for tests if real one missing
        return "test-token"

    oauth2_scheme = lambda tokenUrl=None: None

try:
    from zendaya_backend.database.connection import init_db, get_db
except Exception:
    async def init_db():
        return None
    async def get_db():
        class _Ctx:
            async def __aenter__(self): return None
            async def __aexit__(self, exc_type, exc, tb): return False
        return _Ctx()

# Optional heavy services (may be unavailable in tests)
try:
    from zendaya_backend.ai_core.gemini_service import GeminiService
except Exception:
    GeminiService = None

try:
    from zendaya_backend.knowledge.voice_service import VoiceService
except Exception:
    VoiceService = None

try:
    from zendaya_backend.knowledge.rag_service import RAGService
except Exception:
    RAGService = None

try:
    from zendaya_backend.knowledge.biometric_recognition import BiometricRecognitionSystem
except Exception:
    BiometricRecognitionSystem = None

try:
    from zendaya_backend.agent.workflow_orchestrator import WorkflowOrchestrator
except Exception:
    WorkflowOrchestrator = None

# ChatService (import real or fallback)
try:
    from zendaya_backend.services.chat import ChatService  # use the real one directly
except Exception:
    class ChatService:
        async def process_message(self, message, user=None, context=None):
            return {"text": f"Echo: {message}"}

    # Safe fallback minimal version if chat module fails to import
    from typing import Any, Dict, Optional
    from datetime import datetime

    class ChatService:
        async def process_message(self, message: str, user: Any = None, context: Optional[Dict] = None) -> Dict:
            """Fallback chat processor (for tests or degraded mode)."""
            return {
                "text": f"Echo: {message}",
                "timestamp": datetime.utcnow().isoformat(),
                "context": context or {}
            }

# Optional: RAG-enhanced chat
try:
    from zendaya_backend.services.rag_chat import RAGChatService
except Exception:
    RAGChatService = None

# Smart home controller placeholder
try:
    from agent.tools.smart_home_controller import SmartHomeController
except Exception:
    SmartHomeController = None

# Error engine / offline intelligence placeholders
try:
    from zendaya_backend.ai_core.error_understanding import ErrorUnderstandingEngine
except Exception:
    ErrorUnderstandingEngine = None

try:
    from zendaya_backend.knowledge.offline_intelligence import OfflineIntelligence
except Exception:
    OfflineIntelligence = None

# ---------------------------
# Logging configuration
# ---------------------------
logging.basicConfig(
    level=logging.DEBUG if getattr(settings, "debug", False) else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------
# FastAPI app with lifespan
# ---------------------------
app = FastAPI(title=getattr(settings, "app_name", "Zendaya AI Assistant"),
              version=getattr(settings, "app_version", "0.0.0"))

# Allow CORS according to settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "allowed_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request-id middleware for correlation
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

# ---------------------------
# App state defaults (safe on import)
# ---------------------------
# Provide mocks or None so tests can import/patch them
class SmartHomeMock:
    def __init__(self):
        # typed mutable attribute so static analyzers know this instance has the field
        self.discovered_devices: List[str] = []

app.state.gemini_service = None
app.state.voice_service = None
app.state.rag_service = None
app.state.biometric_system = None
app.state.zendaya_agent = None
app.state.workflow_orchestrator = None
app.state.smart_home = SmartHomeMock() if SmartHomeController is None else None
app.state.offline_intelligence = None
app.state.error_engine = None
app.state.conversation_memory = {}

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ---------------------------
# Health caching
# ---------------------------
_health_cache = {"data": None, "timestamp": datetime.min}

# ---------------------------
# Utilities & dependencies
# ---------------------------
async def get_services(request: Request) -> Dict[str, Any]:
    """Return map of known services from app.state (for backward compatibility)."""
    keys = [
        "biometric_system", "conversation_memory", "error_engine", "gemini_service",
        "offline_intelligence", "rag_service", "voice_service", "zendaya_agent",
        "smart_home", "workflow_orchestrator", "chat_service"
    ]
    return {k: getattr(request.app.state, k, None) for k in keys}

# ---------------------------
# Pydantic models
# ---------------------------
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default"
    context: Optional[Dict[str, Any]] = None
    voice_enabled: bool = True
    audio_base64: Optional[str] = None
    image_base64: Optional[str] = None

    @validator("message")
    def not_empty_message(cls, v):
        if not v or not v.strip():
            raise ValueError("message cannot be empty")
        return v

class ChatResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    emotion: Optional[str] = "confident"
    clarification_needed: bool = False
    suggestions: Optional[List[str]] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class SynthesizeRequest(BaseModel):
    text: str
    voice_id: str = "mxTlDrtKZzOqgjtBw4hM"

    @validator("text")
    def not_empty_text(cls, v):
        if not v or not v.strip():
            raise ValueError("text cannot be empty")
        return v

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    full_name: Optional[str] = None

    @validator("password")
    def password_strength(cls, v):
        import re
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must include at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must include at least one digit")
        return v

class HealthResponse(BaseModel):
    status: str
    services: Dict[str, Any]
    discovered_devices: int
    registered_users: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

# ---------------------------
# Exception handlers
# ---------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error: %s", exc)
    return JSONResponse(status_code=422, content={"detail": exc.errors(), "timestamp": datetime.utcnow().isoformat()})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"detail": str(exc), "timestamp": datetime.utcnow().isoformat()})

# ---------------------------
# Connection manager for websockets
# ---------------------------
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        try:
            self.active_connections.remove(websocket)
        except ValueError:
            pass

    async def send_personal_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

    async def broadcast(self, message: Dict[str, Any]):
        # Iterate over a copy of the list to safely remove disconnected clients
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                # If sending fails, assume the client disconnected and remove them.
                self.disconnect(connection)

manager = ConnectionManager()

# ---------------------------
# Health computation + cached wrapper
# ---------------------------
async def compute_health() -> Dict[str, Any]:
    """Computes the current health of all integrated services."""
    services_status = {
        "gemini": bool(getattr(app.state, "gemini_service", None)),
        "voice": bool(getattr(app.state, "voice_service", None)),
        "rag": bool(getattr(app.state, "rag_service", None)),
        "agent": bool(getattr(app.state, "zendaya_agent", None)),
        "offline_intelligence": bool(getattr(app.state, "offline_intelligence", None)),
        "error_understanding": bool(getattr(app.state, "error_understanding", None)),
        "biometric_recognition": getattr(app.state, "biometric_system", None) is not None,
        "smart_home_integration": bool(getattr(app.state, "smart_home", None)),
        "workflow_orchestrator": bool(getattr(app.state, "workflow_orchestrator", None)),
        "elevenlabs": bool(getattr(app.state, "elevenlabs_service", None)),
    }

    registered_users = 0
    try:
        if app.state.biometric_system and hasattr(app.state.biometric_system, "get_all_users"):
            users = await asyncio.to_thread(app.state.biometric_system.get_all_users)
            registered_users = len(users)
    except Exception:
        registered_users = 0  # Default if service fails

    discovered_devices = len(getattr(app.state.smart_home, "discovered_devices", []))

    return {
        "status": "healthy" if all(services_status.values()) else "degraded",
        "services": services_status,
        "discovered_devices": discovered_devices,
        "registered_users": registered_users,
        "timestamp": datetime.utcnow().isoformat()
    }

async def cached_health_check(ttl_seconds: int = 10) -> Dict[str, Any]:
    """Returns a cached or fresh system health check."""
    now = datetime.utcnow()
    if _health_cache["data"] and (now - _health_cache["timestamp"]) < timedelta(seconds=ttl_seconds):
        return _health_cache["data"]
    
    data = await compute_health()
    _health_cache["data"] = data
    _health_cache["timestamp"] = now
    return data

# ---------------------------
# Real system metrics collector (ADD HERE)
# ---------------------------
async def get_system_metrics() -> dict:
    """Collect real-time CPU, memory, and disk usage."""
    return {
        "cpu": psutil.cpu_percent(interval=None),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage("/").percent
    }

# ---------------------------
# Background task for broadcasting status
# ---------------------------
async def broadcast_system_status():
    while True:
        try:
            health_data = await cached_health_check()
            metrics = await get_system_metrics()

            message_to_broadcast = {
                "type": "system_status",
                "data": {
                    **health_data,
                    **metrics
                }
            }
            await manager.broadcast(message_to_broadcast)
        except Exception as e:
            logger.error(f"Error in broadcast_system_status: {e}")
        await asyncio.sleep(2)


# Persona compaction background task
async def persona_compaction_task(interval_seconds: int = 60):
    """
    Periodically compact recent memories into a persona summary stored on app.state.
    This summary is used to augment prompts and can be persisted to disk if desired.
    """
    while True:
        try:
            summary = memory_service.compact_summaries(max_chars=3000)
            app.state.persona_memory = summary
            logger.debug("Persona compaction: summary length=%d", len(summary))
        except Exception as e:
            logger.exception("persona_compaction_task failed: %s", e)
        await asyncio.sleep(interval_seconds)


# ---------------------------
# Lifespan / startup / shutdown
# ---------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("startup: beginning initialization")
    # Initialize DB
    try:
        await init_db()
        logger.info("startup: DB initialized")
    except Exception as exc:
        logger.warning("startup: init_db failed: %s", exc)
    
    # ---------------------------
    # Preload Shuri Coqui Voice Model
    # ---------------------------
    try:
        from zendaya_backend.knowledge.voice_service import preload_voice_service
        logger.info("startup: launching background preload for Shuri XTTS voice...")
        try:
            asyncio.create_task(preload_voice_service())
            logger.info("startup: preload task created (background).")
        except Exception:
            logger.info("startup: preload task creation failed, falling back to await")
            await preload_voice_service()
            logger.info("startup: Voice System Ready.")

    except Exception as e:
        logger.warning(f"startup: Voice preload failed: {e}")

    # ---------------------------
    # 2️⃣ Initialize Shuri Voice Service (Coqui-only)
    # ---------------------------
    try:
        from zendaya_backend.knowledge.voice_service import VoiceService
        app.state.voice_service = VoiceService()
        logger.info("startup: Shuri VoiceService initialized (Coqui XTTS only).")
    except Exception as e:
        app.state.voice_service = None
        logger.warning(f"⚠️ Shuri VoiceService initialization failed: {e}")

    # ---------------------------
    # 2️⃣ Initialize Chat Services (RAG + Core)
    # ---------------------------
    try:
        if RAGChatService:
            app.state.chat_service = RAGChatService()
            logger.info("startup: RAGChatService initialized (Retrieval-Augmented Chat).")
        elif ChatService:
            app.state.chat_service = ChatService()
            logger.info("startup: ChatService initialized (basic chat).")
        else:
            app.state.chat_service = None
            logger.warning("startup: No chat service available.")
    except Exception as e:
        app.state.chat_service = None
        logger.warning(f"⚠️ Chat service initialization failed: {e}")

    # ---------------------    
    # 3️⃣ Initialize Biometric Recognition System
    # ---------------------
    try:
        if BiometricRecognitionSystem:
            biometric_system = BiometricRecognitionSystem(data_dir="zendaya_backend/data/biometric_system_data")
            app.state.biometric_system = biometric_system
            users = await asyncio.to_thread(biometric_system.get_all_users)
            logger.info(f"✅ Biometric Recognition System initialized with {len(users)} registered users.")
        else:
            app.state.biometric_system = None
            logger.info("BiometricRecognitionSystem not available; skipping biometric initialization.")
    except Exception as e:
        app.state.biometric_system = None
        logger.warning(f"⚠️ Biometric Recognition System failed: {e}")

    # ---------------------
    # 5. Initialize Speech-to-Text Service
    # ---------------------
    try:
        # Use "base.en" for a good balance of speed and accuracy.
        # Use "tiny.en" if it's too slow.
        app.state.stt_service = STTService(model_name="base.en")
    except Exception as e:
        app.state.stt_service = None
        logger.warning(f"⚠️ STT (Whisper) Service failed to initialize: {e}")

    # ---------------------

    # 4️⃣ Initialize Error Understanding Engine
    # ---------------------
    try:
        from zendaya_backend.core.error_engine import ErrorUnderstandingEngine
        error_engine = ErrorUnderstandingEngine() if ErrorUnderstandingEngine else None
        if error_engine:
            # Optional: quick test to confirm it analyzes properly
            try:
                test_analysis = await error_engine.analyze_error("Test error message")
                if test_analysis:
                    logger.info(f"✅ Error Understanding Engine ready. Sample detection: {getattr(test_analysis, 'error_type', str(test_analysis))}")
                else:
                    logger.warning("⚠️ Error Understanding Engine returned no analysis during startup test.")
            except Exception as inner_exc:
                logger.warning("Error Understanding Engine test call failed: %s", inner_exc)
            app.state.error_understanding = error_engine
        else:
            app.state.error_understanding = None
    except Exception as e:
        app.state.error_understanding = None
        logger.warning(f"⚠️ Error Understanding Engine failed: {e}")

    # Initialize registered users list
    app.state.registered_users = []

    # Initialize heavy services defensively
    try:
        if GeminiService:
            app.state.gemini_service = GeminiService()
        else:
            app.state.gemini_service = None
        logger.info("startup: gemini_service set")
    except Exception:
        logger.exception("startup: gemini init failed")
        app.state.gemini_service = None

    # Smart Greeting Sequence
    try:
        from zendaya_backend.agent.tools.greeting import greet_user

        system_status = { "DB": True, "AI": True } # simplified for brevity
        recovery_map = { "DB": (lambda: asyncio.sleep(1)), "AI": (lambda: asyncio.sleep(1)) }
        
        async def _schedule_greeting():
            await asyncio.sleep(0.6)
            voice_service_obj = getattr(app.state, "voice_service", None)
            voice_id = getattr(voice_service_obj, "default_voice_id", "mxTlDrtKZzOqgjtBw4hM")
            await greet_user(system_status, recovery_map, voice_service_obj, voice_id)

        asyncio.create_task(_schedule_greeting())
        logger.info("startup: Smart greeting initialized")
    except Exception as e:
        logger.exception(f"startup: Smart greeting setup failed: {e}")

    # Start the WebSocket broadcasting task
    asyncio.create_task(broadcast_system_status())
    logger.info("startup: System status broadcaster started.")

    # Start persona compaction task (background)
    try:
        asyncio.create_task(persona_compaction_task(60))
        logger.info("startup: Persona compaction task started.")
    except Exception as e:
        logger.warning("Failed to start persona compaction task: %s", e)

    logger.info("startup: complete")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("shutdown: begin cleanup")
    # Gracefully shut down services
    candidates = [
        "voice_service", "gemini_service", "rag_service", "biometric_system",
        "zendaya_agent", "workflow_orchestrator", "smart_home"
    ]
    for name in candidates:
        svc = getattr(app.state, name, None)
        if svc is None:
            continue
        # Attempt to call cleanup or close methods
        for method_name in ["cleanup", "close"]:
            if hasattr(svc, method_name):
                try:
                    method = getattr(svc, method_name)
                    if asyncio.iscoroutinefunction(method):
                        await method()
                    else:
                        await asyncio.to_thread(method)
                    logger.info("shutdown: cleaned %s", name)
                    break # Stop after successful cleanup
                except Exception:
                    logger.exception("shutdown: cleanup failed for %s", name)
    logger.info("shutdown: complete")


# ---------------------------
# WebSocket Voice Stream Handler
# ---------------------------
class VoiceStreamHandler:
    """
    Manages a single WebSocket voice connection, buffering audio
    and processing it for biometrics and transcription.
    """
    def __init__(self, websocket: WebSocket, session_id: str, biometric_system: BiometricRecognitionSystem, voice_service: VoiceService):
        self.websocket = websocket
        self.session_id = session_id
        self.biometric_system = biometric_system
        self.voice_service = voice_service
        self.audio_buffer = io.BytesIO()
        self.user = None
        self.stream_mode = False
        self.use_voice_id = False

    async def handle_message(self, data: Any):
        """Handles incoming WebSocket data (audio bytes or text)."""
        if isinstance(data, bytes):
            # This is an audio chunk, write it to the buffer
            self.audio_buffer.write(data)
            
        elif isinstance(data, str):
            # This is a JSON control message
            try:
                message = json.loads(data)
                if message.get("type") == "end_of_stream":
                    logger.info(f"Client sent end_of_stream for {self.session_id}")
                    await self.process_final_audio()
                elif message.get("type") == "synthesize":
                    logger.info(f"Client requested synthesis for {self.session_id}")
                    await self.handle_synthesize_request(message.get("text", ""))
                elif message.get("type") == "stream_mode":
                    # Client requested streaming mode for live partial transcription.
                    logger.info(f"Client requested stream_mode for {self.session_id}")
                    # mark this handler as operating in stream mode
                    self.stream_mode = True
                    try:
                        await self.websocket.send_json({"type": "stream_mode_ack"})
                    except Exception:
                        pass
                elif message.get("type") == "enable_voice_id":
                    # Client requests enabling/disabling voice biometric verification
                    enabled = bool(message.get("enabled", True))
                    logger.info(f"Client requested enable_voice_id={enabled} for {self.session_id}")
                    self.use_voice_id = enabled
                    try:
                        await self.websocket.send_json({"type": "enable_voice_id_ack", "enabled": enabled})
                    except Exception:
                        pass
            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON text message: {data}")

    async def handle_synthesize_request(self, text: str):
        """
        Synthesizes text using the VoiceService and sends the
        audio data back to the client.
        """
        if not text or not self.voice_service:
            if not self.voice_service:
                logger.warning("Cannot synthesize: VoiceService is not available.")
            return

        try:
            # 1. Generate the audio file using your Coqui service
            # Use a friendly celebrity Zendaya style by default for personality
            emotion = "friendly"
            tone = "celebrity-zendaya"
            synthesis_result = await voice_service.synthesize(
                text,
                emotion=emotion,
                style=tone,
            )
            
            if not synthesis_result:
                logger.warning("Voice synthesis failed, not sending audio.")
                return

            audio_path = synthesis_result.get("path")
            
            # 2. Read the audio file's bytes and encode them
            # This is blocking I/O, so we run it in a thread
            def read_and_encode(path):
                with open(path, "rb") as audio_file:
                    file_bytes = audio_file.read()
                return base64.b64encode(file_bytes).decode('utf-8')

            audio_base64 = await asyncio.to_thread(read_and_encode, audio_path)
            logger.info(f"Successfully synthesized and encoded response audio.")

            # 3. Send the audio back to the client
            await self.websocket.send_json({
                "type": "voice_response",
                "text": text, # Send the original text for context
                "audio_base64": audio_base64,
                "content_type": "audio/wav" # Helps the client
            })
            
        except Exception as e:
            logger.error(f"Error during voice synthesis request: {e}")

    async def process_final_audio(self):
        """
        Called when the user stops speaking. This processes the
        complete audio for biometrics and transcription.
        """
        logger.info(f"Processing final audio for session {self.session_id}...")
        full_audio_bytes = self.audio_buffer.getvalue()

        if not full_audio_bytes:
            logger.warning("No audio data to process.")
            # Reset buffer and return
            self.audio_buffer.close()
            self.audio_buffer = io.BytesIO()
            return

        # --- 1. Biometric Identification ---
        user_result = None
        # Only attempt biometric voice identification if the client requested it
        if getattr(self, "use_voice_id", False) and self.biometric_system:
            try:
                user_result = await asyncio.to_thread(
                    self.biometric_system.verify_voice,
                    full_audio_bytes
                )
                if user_result:
                    self.user = user_result
                    logger.info(f"Biometric match for {self.session_id}: {user_result['name']}")
                    await self.websocket.send_json({
                        "type": "biometric_match",
                        "user": user_result
                    })
                else:
                    logger.info(f"No biometric match for {self.session_id}.")
            except Exception as e:
                logger.error(f"Biometric verification failed: {e}")

        # --- 2. Transcription (STT) ---
        transcribed_text = None
        stt_service: STTService = self.websocket.app.state.stt_service

        if stt_service:
            # If the client requested stream_mode, attempt a streaming transcription
            # path that can return incremental/partial text. If transcribe_stream
            # is available on the STT service, use it and send a partial result.
            if getattr(self, "stream_mode", False):
                try:
                    if hasattr(stt_service, "transcribe_stream"):
                        partial = await stt_service.transcribe_stream(full_audio_bytes)
                        if partial:
                            await self.websocket.send_json({
                                "type": "partial_transcription",
                                "text": partial
                            })
                        # In stream mode we do not continue with the normal final-processing
                        return
                except Exception as e:
                    logger.error(f"Stream transcription failed: {e}")

            # Fallback: synchronous/batch transcription
            transcribed_text = await stt_service.transcribe(full_audio_bytes)

            # Multi-speaker diarization placeholder: if the STT service supports
            # diarization, run it and forward results to the client for UI rendering.
            if hasattr(stt_service, "diarize"):
                try:
                    diarization = await stt_service.diarize(full_audio_bytes)
                    if diarization:
                        await self.websocket.send_json({
                            "type": "diarization",
                            "data": diarization
                        })
                except Exception as e:
                    logger.error(f"Diarization failed: {e}")

        if not transcribed_text:
            logger.error("STT service failed to transcribe audio.")
            await self.websocket.send_json({
                "type": "transcription_error",
                "message": "Sorry, I could not understand the audio."
            })
            # Reset and return
            self.audio_buffer.close()
            self.audio_buffer = io.BytesIO()
            return

        # --- 3. Send transcription back to client ---
        await self.websocket.send_json({
            "type": "final_transcription",
            "text": transcribed_text
        })

        # --- 4. Get Response from Chat Service (AI Brain) ---
        chat_service = self.websocket.app.state.chat_service
        if not chat_service:
            logger.error("Chat service is unavailable.")
            self.audio_buffer.close()
            self.audio_buffer = io.BytesIO()
            return

        # --- Retrieve relevant memories and persona block (best-effort) ---
        try:
            persona_block = getattr(app.state, "persona_memory", "")
            relevant_memories = await asyncio.to_thread(memory_service.retrieve, transcribed_text, 6)
            mem_block = "\n".join([f"- {m.get('summary') or m.get('raw')}" for m in relevant_memories if m])
            augmented = ""
            if persona_block:
                augmented += f"[PERSONA]\n{persona_block}\n[END_PERSONA]\n"
            if mem_block:
                augmented += f"[RELEVANT_MEMORIES]\n{mem_block}\n[END_RELEVANT]\n"
            augmented += transcribed_text
            # Pass augmented text to chat service as best-effort augmentation
            chat_response = await chat_service.process_message(augmented, user=self.user)
        except Exception as e:
            logger.exception("Memory retrieval integration failed: %s", e)
            # fallback to simple message if anything fails
            chat_response = await chat_service.process_message(transcribed_text, user=self.user)
        response_text = chat_response.get("text")

        if not response_text:
            logger.error("Chat service returned an empty response.")
            # Reset and return
            self.audio_buffer.close()
            self.audio_buffer = io.BytesIO()
            return

        # --- 5. Synthesize Audio Response (TTS Mouth) ---
        voice_service: VoiceService = self.websocket.app.state.voice_service
        audio_base64 = None

        if voice_service:
            try:
                # 1. Generate the audio file
                # Use a friendly celebrity Zendaya style for responses
                emotion = "friendly"
                tone = "celebrity-zendaya"
                synthesis_result = await voice_service.synthesize(
                    response_text,
                    emotion=emotion,
                    style=tone,
                )
                
                if synthesis_result:
                    audio_path = synthesis_result.get("path")
                    
                    # 2. Read the file bytes and encode them for sending
                    def read_and_encode(path):
                        with open(path, "rb") as audio_file:
                            file_bytes = audio_file.read()
                        return base64.b64encode(file_bytes).decode('utf-8')

                    audio_base64 = await asyncio.to_thread(read_and_encode, audio_path)
                    logger.info(f"Successfully synthesized and encoded response audio.")
                else:
                    logger.warning("Voice synthesis failed, returning text only.")
                    
            except Exception as e:
                logger.error(f"Error during voice synthesis: {e}")
        else:
            logger.warning("Voice service unavailable, returning text only.")

        # --- 6. Send Final Response to Client ---
        if audio_base64:
            # Send the text AND the audio
            await self.websocket.send_json({
                "type": "voice_response",
                "text": response_text,
                "audio_base64": audio_base64,
                "content_type": "audio/wav" # Helps the client
            })
        else:
            # Fallback: just send the text response
            await self.websocket.send_json({
                "type": "chat_response", 
                "data": chat_response
            })

        # Best-effort: store the exchange in memory_service asynchronously
        try:
            asyncio.create_task(
                memory_service.ingest_memory(
                    content=f"User: {transcribed_text}\nZendaya: {response_text}",
                    user_id=self.session_id,
                    source="voice_chat"
                )
            )
        except TypeError:
            # memory_service.ingest_memory may be a blocking function; run in thread
            try:
                asyncio.create_task(asyncio.to_thread(
                    memory_service.ingest_memory,
                    f"User: {transcribed_text}\nZendaya: {response_text}",
                    self.session_id,
                    "voice_chat"
                ))
            except Exception as e:
                logger.error(f"Memory store failed (thread fallback): {e}")
        except Exception as e:
            logger.error(f"Memory store failed: {e}")

        # --- 7. Reset Buffer ---
        self.audio_buffer.close()
        self.audio_buffer = io.BytesIO()

    async def cleanup(self):
        """Called on WebSocket disconnect."""
        # Process any audio that was left in the buffer
        await self.process_final_audio()
        self.audio_buffer.close()
        logger.info(f"Cleaned up handler for session {self.session_id}")

# ---------------------------
# Routes
# ---------------------------
@app.get("/", status_code=200)
async def root():
    return {"message": getattr(settings, "app_name", "Zendaya AI Assistant API")}

@app.get("/health", response_model=HealthResponse)
async def health():
    data = await cached_health_check()
    return HealthResponse(**data)

@app.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def chat_endpoint(request: Request, chat_request: ChatRequest, user: User = Depends(get_current_active_user), services: dict = Depends(get_services)):
    chat_service = services.get("chat_service")
    if not chat_service or not hasattr(chat_service, "process_message"):
        raise HTTPException(status_code=503, detail="Chat service is unavailable")
    try:
        response = await chat_service.process_message(chat_request.message, user, chat_request.context)
        if isinstance(response, dict):
            if "timestamp" not in response:
                response["timestamp"] = datetime.utcnow().isoformat()

            # Best-effort: store this text-chat exchange in memory_service asynchronously
            try:
                asyncio.create_task(
                    memory_service.ingest_memory(
                        content=f"User: {chat_request.message}\nZendaya: {response.get('text', '')}",
                        user_id=chat_request.user_id,
                        source="text_chat"
                    )
                )
            except TypeError:
                try:
                    asyncio.create_task(asyncio.to_thread(
                        memory_service.ingest_memory,
                        f"User: {chat_request.message}\nZendaya: {response.get('text', '')}",
                        chat_request.user_id,
                        "text_chat"
                    ))
                except Exception as e:
                    logger.error(f"Memory store failed (thread fallback): {e}")
            except Exception as e:
                logger.error(f"Memory store failed: {e}")

            return ChatResponse(**response)
        raise HTTPException(status_code=500, detail="Invalid response from chat service")
    except Exception as exc:
        logger.exception("chat processing failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

# ... [Other routes like /synthesize, /transcribe, etc., remain here]

@app.get("/status")
async def get_status():
    return {"success": True, "message": "Service is running", "data": {"status": "ok"}}

# ---------------------------
# WebSocket endpoint
# ---------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # Token validation logic removed from here
    await manager.connect(websocket)
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await websocket.send_json({
                    "type": "ping",
                    "timestamp": datetime.utcnow().isoformat()
                })
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("WebSocket disconnected")
@app.post("/system/discover-devices")
async def discover_devices():
    logger.info("Discovering new smart devices...")
    if not hasattr(app.state, "smart_home") or app.state.smart_home is None:
        # Ensure a compatible mock is available with a mutable attribute
        app.state.smart_home = SmartHomeMock()
    
    devices = ["Living Room Light", "Thermostat", "Front Door Camera"]
    app.state.smart_home.discovered_devices = devices
    logger.info(f"Discovered devices: {devices}")
    return {"success": True, "devices": devices}

@app.websocket("/ws/amplitude")
async def websocket_amplitude_endpoint(
    websocket: WebSocket,
    session_id: str | None = Query(None)
):
    """
    Handles real-time amplitude/volume data from the client.
    This is mostly for UI feedback.
    """
    await websocket.accept()
    
    if not session_id:
        logger.warning(f"Amplitude WebSocket connected with NO session_id.")
    else:
        logger.info(f"Amplitude WebSocket connected: session_id={session_id}")

    try:
        while True:
            # Expecting JSON data like {"level": 0.85}
            data = await websocket.receive_json()
            level = data.get("level", 0)

            # Broadcast this to all connected system dashboards
            await manager.broadcast({
                "type": "amplitude_update",
                "data": {
                    "session_id": session_id,
                    "level": level
                }
            })
            
    except WebSocketDisconnect:
        logger.info(f"Amplitude WebSocket disconnected: session_id={session_id}")
    except Exception as e:
        logger.error(f"Error in amplitude websocket (session={session_id}): {e}")


@app.websocket("/ws/voice")
async def websocket_voice_endpoint(
    websocket: WebSocket,
    session_id: str | None = Query(None),
    # NOTE: You will likely need to re-add your auth dependency here
    # user: User = Depends(get_current_active_user) 
):
    """
    Handles the real-time voice data stream for biometrics and transcription.
    """
    await websocket.accept()
    logger.info(f"Voice WebSocket connected: session_id={session_id}")

    # --- UPDATED BLOCK ---
    biometric_system = websocket.app.state.biometric_system
    voice_service = websocket.app.state.voice_service # Get the voice service

    if not biometric_system or not voice_service:
        reason = f"Service unavailable: Biometric={bool(biometric_system)}, Voice={bool(voice_service)}"
        logger.error(reason)
        await websocket.close(code=WS_1011_INTERNAL_ERROR, reason=reason)
        return
    
    # Create a handler to manage this connection's state
    handler = VoiceStreamHandler(websocket, session_id, biometric_system, voice_service)
    # --- END OF UPDATED BLOCK ---

    try:
        while True:
            # Receive() can handle both text and bytes
            data = await websocket.receive()
            
            if "bytes" in data:
                await handler.handle_message(data["bytes"])
            elif "text" in data:
                await handler.handle_message(data["text"])
                
    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected: session_id={session_id}")
        # Process any buffered audio on disconnect
        await handler.cleanup()
    except Exception as e:
        logger.error(f"Error in voice websocket (session={session_id}): {e}")


@app.websocket("/ws/system")
async def system_ws(websocket: WebSocket):
    # --- Token validation logic ADDED here ---
    token = websocket.query_params.get("token")
    if not token:
        logger.warning("[SYSTEM WS] Connection attempt without token.")
        await websocket.close(code=1008)
        return
    
    try:
        # Use os.getenv for safer access
        jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
        if not jwt_secret:
            logger.error("[SYSTEM WS] SUPABASE_JWT_SECRET environment variable not set.")
            raise JWTError("Server configuration error: JWT secret missing.")
            
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
        )
        logger.info(f"[SYSTEM WS] Client authenticated: {payload.get('sub')}")
    except JWTError as e:
        logger.warning(f"[SYSTEM WS] WebSocket auth failed: {e}")
        await websocket.close(code=1008)
        return
    # --- End of token validation ---

    await websocket.accept()
    print("[SYSTEM WS] Client connected")

    try:
        while True:
            # CPU %
            cpu = psutil.cpu_percent(interval=None)

            # RAM %
            memory = psutil.virtual_memory().percent

            # Disk %
            disk = psutil.disk_usage("/").percent

            # Network connectivity test
            try:
                net_ok = psutil.net_if_stats()
                network = any(i.isup for i in net_ok.values())
            except:
                network = False

            # OPTIONAL: check services running
            def check_service(name):
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc.info['name'] and name.lower() in proc.info['name'].lower():
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                return False

            services = {
                "voice": check_service("uvicorn"), 
                "chat": check_service("python"), 
            }

            # placeholder values for your AI functions
            discoveredDevices = 0
            registeredUsers = 1

            # send real system metrics
            await websocket.send_json({
                "type": "system",
                "cpu": cpu,
                "memory": memory,
                "disk": disk,
                "network": network,
                "services": services,
                "discoveredDevices": discoveredDevices,
                "registeredUsers": registeredUsers
            })

            # send ping
            await websocket.send_json({"type": "ping"})

            await asyncio.sleep(2)

    except WebSocketDisconnect:
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close()
            except Exception:
                pass # Ignore errors on close
        print("[SYSTEM WS] Client disconnected")

    except Exception as e:
        print(f"[SYSTEM WS ERROR] {e}")
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close()
        except Exception:
            pass # Ignore errors on close if already disconnected



@app.post("/system/register-user")
async def register_user():
    logger.info("Registering new user...")
    if not hasattr(app.state, "registered_users"):
        app.state.registered_users = []
    new_user = f"user_{len(app.state.registered_users) + 1}"
    app.state.registered_users.append(new_user)
    return {"success": True, "registered_users": app.state.registered_users}


@app.post("/system/test-workflow")
async def test_workflow():
    logger.info("Executing workflow test...")
    if app.state.workflow_orchestrator:
        try:
            # Simulate success
            return {"success": True, "message": "Workflow executed successfully"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "error": "Workflow orchestrator not available"}

@app.post("/system/analyze-error")
async def analyze_error(request: Request):
    try:
        data = await request.json()
        message = data.get("error", "")
        if not message:
            return {"error": "No error message provided"}

        if app.state.error_understanding:
            analysis = await app.state.error_understanding.analyze_error(message)
            if analysis:
                return {"status": "ok", "analysis": analysis.__dict__}
        
        return {"status": "failed", "reason": "Engine unavailable"}
    except Exception as e:
        logger.error(f"Error in analyze_error endpoint: {e}")
        return {"status": "failed", "error": str(e)}


@app.post("/system/optimize")
async def optimize_system():
    logger.info("Optimizing system performance...")
    await asyncio.sleep(1)
    return {"success": True, "message": "Optimization complete"}

@app.get("/api/users")
async def get_users():
    users = getattr(app.state, "registered_users", [])
    return {"users": users}


# Memory management endpoints
from pydantic import BaseModel

class IngestMemoryPayload(BaseModel):
    content: str
    user_id: Optional[str] = None
    source: Optional[str] = "conversation"
    type: Optional[str] = "utterance"
    summary: Optional[str] = None
    privacy_level: Optional[str] = "default"
    metadata: Optional[Dict[str, Any]] = {}

@app.post("/memory/ingest")
async def ingest_memory_endpoint(payload: IngestMemoryPayload):
    # Respect privacy_level: don't store 'sensitive' by default
    if payload.privacy_level == "sensitive":
        return {"status": "skipped", "reason": "sensitive data not stored"}
    # Use thread to avoid blocking event loop for heavy embedding
    try:
        mem = await asyncio.to_thread(
            memory_service.ingest_memory,
            payload.content,
            payload.user_id,
            payload.source,
            payload.type,
            payload.summary,
            payload.privacy_level,
            payload.metadata
        )
        return {"status": "ok", "memory": mem}
    except Exception as e:
        logger.exception("ingest_memory failed: %s", e)
        return {"status": "error", "error": str(e)}

@app.get("/memory/query")
async def query_memory(q: str, k: int = 6):
    try:
        results = await asyncio.to_thread(memory_service.retrieve, q, k)
        return {"query": q, "results": results}
    except Exception as e:
        logger.exception("memory/query failed: %s", e)
        return {"query": q, "results": []}

@app.post("/memory/clear_user")
async def clear_user_memories(user_id: str):
    try:
        await asyncio.to_thread(memory_service.clear_user_memories, user_id)
        return {"status": "ok"}
    except Exception as e:
        logger.exception("clear_user_memories failed: %s", e)
        return {"status": "error", "error": str(e)}


# ---------------------------
#  🗣️ Test Voice Endpoint (ElevenLabs)
# ---------------------------
from fastapi import Form
from fastapi.responses import JSONResponse
from zendaya_backend.knowledge.voice_service import VoiceService

@app.post("/system/test-voice")
@limiter.limit("10/minute")
async def test_voice_endpoint(request: Request, text: str = Form(...)):
    """
    Unified TTS endpoint.
    Uses ElevenLabs (if available), else Coqui, else pyttsx3.
    Always plays via hologram first; falls back to silent background.
    """
    try:
        vs: VoiceService = app.state.voice_service
        if not vs:
            return JSONResponse({"error": "VoiceService not initialized"}, status_code=500)

        # generate audio
        result = await vs.synthesize(text, emotion="calm")
        if not result:
            return JSONResponse({"error": "TTS failed"}, status_code=500)

        # play it (hologram prioritized)
        await vs.play(result["path"], hologram_priority=True)

        return {
            "success": True,
            "path": result["path"],
            "duration": result["duration"]
        }

    except Exception as e:
        logger.error(f"Voice test endpoint failed: {e}")
        return JSONResponse(
            {"error": f"TTS pipeline error: {str(e)}"},
            status_code=500
        )

# ---------------------------
# Recovery helpers (simple examples)
# ---------------------------
async def attempt_voice_recovery(chat_service=None) -> bool:
    """Safely reinitialize the VoiceService if it fails or becomes unavailable."""
    try:
        # Ensure VoiceService is importable
        if not VoiceService:
            logger.warning("VoiceService module unavailable; skipping recovery.")
            return False

        # Initialize a fresh VoiceService instance
        svc = VoiceService()
        app.state.voice_service = svc

        logger.info("✅ VoiceService successfully recovered and reinitialized.")
        return True

    except Exception as exc:
        logger.exception("❌ attempt_voice_recovery failed: %s", exc)
        return False

# ---------------------------
# Expose module-level names for tests to patch (keeps compatibility)
# ---------------------------
__all__ = [
    "app", "ChatRequest", "ChatResponse", "SynthesizeRequest",
    "RegisterRequest", "get_services", "attempt_voice_recovery"
]

@app.get("/system/chat-version")
async def chat_version():
    svc = getattr(app.state, "chat_service", None)
    if not svc:
        return {"active": False, "type": None}
    return {"active": True, "type": svc.__class__.__name__}



