"""
Pytest configuration and fixtures
"""
import pytest
import asyncio
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from zendaya_backend.main import app
from zendaya_backend.core.config import settings


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    return TestClient(app)


@pytest.fixture
def mock_gemini_service():
    """Mock Gemini service"""
    mock = Mock()
    mock.is_ready.return_value = True
    mock.generate_response = AsyncMock(return_value="Test response from Zendaya")
    return mock


@pytest.fixture
def mock_voice_service():
    """Mock voice service"""
    mock = Mock()
    mock.is_ready.return_value = True
    mock.transcribe_with_context = AsyncMock(return_value={
        "transcript": "test transcript",
        "confidence": 0.95,
        "needs_clarification": False,
        "alternatives": [],
        "word_details": [],
        "quality_score": 0.9
    })
    mock.synthesize_with_emotion = AsyncMock(return_value="/audio/test.mp3")
    return mock


@pytest.fixture
def mock_rag_service():
    """Mock RAG service"""
    mock = Mock()
    mock.is_ready.return_value = True
    mock.query = AsyncMock(return_value="Test knowledge context")
    mock.ingest_document = AsyncMock(return_value=5)
    return mock


@pytest.fixture
def auth_headers():
    """Authentication headers for testing"""
    # In a real test, you'd generate a proper JWT token
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def sample_chat_request():
    """Sample chat request data"""
    return {
        "message": "Hello Zendaya",
        "user_id": "test-user",
        "voice_enabled": True
    }

@pytest.fixture
def mock_tools():
    """Create mock agent tools"""
    web_search_tool = Mock()
    web_search_tool.arun = AsyncMock(return_value="Search results")

    smart_home_tool = Mock()
    smart_home_tool.arun = AsyncMock(return_value="Device controlled")

    calendar_tool = Mock()
    calendar_tool.arun = AsyncMock(return_value="Calendar checked")

    return {
        "web_search": web_search_tool,
        "smart_home": smart_home_tool,
        "calendar": calendar_tool
    }

@pytest.fixture
async def orchestrator(mock_tools):
    """Create WorkflowOrchestrator instance"""
    from zendaya_backend.agent.workflow_orchestrator import WorkflowOrchestrator
    orch = WorkflowOrchestrator(tools=mock_tools)
    await orch.startup()
    yield orch
    await orch.shutdown()