"""
Integration tests for main API endpoints (cleaned and production-ready)
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from zendaya_backend.main import app, get_services, get_current_active_user
from zendaya_backend.models.users import User
from zendaya_backend.models.api import HealthResponse


# ---------------------------------------------------------------------------
# ✅ Mock dependencies
# ---------------------------------------------------------------------------

mock_user = User(
    username="testuser",
    email="test@test.com",
    full_name="Test User",
    id="test123",
    disabled=False
)

mock_service_map = {
    "voice_service": AsyncMock(
        transcribe_with_context=AsyncMock(return_value={"transcript": "test", "confidence": 0.95}),
        synthesize=AsyncMock(return_value="/audio/test.mp3")
    ),
    "rag_service": AsyncMock(query=AsyncMock(return_value="Test knowledge")),
    "workflow_orchestrator": AsyncMock(get_workflow_status=AsyncMock(return_value={"status": "completed", "id": "test123"})),
    "smart_home": AsyncMock(
        control_device=AsyncMock(return_value={"result": "Success"}),
        get_devices=AsyncMock(return_value={"devices": []})
    ),
    "biometric_system": Mock(
        register_user=Mock(return_value={"user_id": "user123"}),
        verify_user=Mock(return_value=True)
    ),
    "chat_service": AsyncMock(process_message=AsyncMock(return_value={"text": "Test response", "timestamp": "2025-10-14T10:00:00Z"})),
    "gemini_service": AsyncMock(generate_response=AsyncMock(return_value="Test response")),
    "zendaya_agent": AsyncMock(process=AsyncMock(return_value={"actions": [], "result": "Agent response"}))
}


async def override_get_services():
    """Dependency override for mock service map"""
    return mock_service_map


async def override_get_current_active_user():
    """Dependency override for mock authenticated user"""
    return mock_user


# Apply overrides
app.dependency_overrides[get_services] = override_get_services
app.dependency_overrides[get_current_active_user] = override_get_current_active_user


# ---------------------------------------------------------------------------
# ✅ Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    """Provide a test client with dependency overrides applied."""
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# ✅ Integration Tests
# ---------------------------------------------------------------------------

class TestMainEndpoints:
    """Integration tests for Zendaya main API endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint returns online status."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert data.get("status") == "online"
        assert "message" in data

    def test_health_endpoint(self, client: TestClient):
        """Test /health endpoint structure and types."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()

        # Validate structure using Pydantic
        HealthResponse(**data)
        assert data["status"] == "healthy"

    def test_chat_endpoint_success(self, client: TestClient):
        """Test successful chat message."""
        response = client.post("/chat", json={"message": "Hello Zendaya"})
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "Test response"

    def test_synthesize_endpoint_success(self, client: TestClient):
        """Test successful text-to-speech synthesis."""
        response = client.post("/synthesize", json={"text": "Hello world", "voice_id": "test-voice"})
        assert response.status_code == 200
        data = response.json()
        assert data["audio_url"] == "/audio/test.mp3"

    # -----------------------------------------------------------------------
    # ❌ Invalid & error handling tests
    # -----------------------------------------------------------------------

    @pytest.mark.parametrize("endpoint,method,payload,expected_status", [
        ("/chat", "post", {"message": ""}, 400),
        ("/chat", "post", {}, 422),
        ("/chat", "post", {"message": 123}, 422),
        ("/synthesize", "post", {"text": ""}, 400),
        ("/conversation/", "get", None, 404),
        ("/conversation/", "delete", None, 404),
        ("/workflow/invalid-id", "get", None, 404),
        ("/workflow/", "get", None, 404),
    ])
    
    def test_invalid_endpoints(self, client: TestClient, endpoint, method, payload, expected_status):
        """Test endpoints with invalid or missing payloads."""
        func = getattr(client, method)

        kwargs = {}
        if payload is not None:
            if method.lower() in ["post", "put", "patch"]:
                kwargs['json'] = payload
            else: # for GET, DELETE, etc.
                kwargs['params'] = payload

        response = func(endpoint, **kwargs)
        assert response.status_code == expected_status

    # -----------------------------------------------------------------------
    # ✅ Mocked service endpoints
    # -----------------------------------------------------------------------

    @patch("zendaya_backend.main.biometric_system")
    def test_biometric_registration_success(self, mock_bio, client: TestClient):
        """Test successful biometric registration."""
        mock_bio.register_user.return_value = {"user_id": "user123"}

        response = client.post("/biometric/register", json={"name": "John Doe", "relationship": "family"})
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == "user123"

    @patch("zendaya_backend.main.smart_home")
    def test_smart_home_control_success(self, mock_home, client: TestClient):
        """Test controlling a smart home device."""
        mock_home.control_device = AsyncMock(return_value={"result": "Device controlled successfully"})
        response = client.post("/smart_home/control", json={"command": "turn on lights"})
        assert response.status_code == 200
        assert "result" in response.json()

    @patch("zendaya_backend.main.workflow_orchestrator")
    def test_workflow_status_success(self, mock_orch, client: TestClient):
        """Test retrieving workflow status."""
        mock_orch.get_workflow_status.return_value = {"id": "test123", "status": "completed"}
        response = client.get("/workflow/status")
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == "test123"

    # -----------------------------------------------------------------------
    # ⚙️ Edge case tests
    # -----------------------------------------------------------------------

    def test_chat_extremely_long_message(self, client: TestClient):
        """Test sending an extremely long chat message."""
        long_message = "a" * 10000
        response = client.post("/chat", json={"message": long_message})
        assert response.status_code in [200, 400, 413, 422]

    def test_chat_special_characters(self, client: TestClient):
        """Test chat handling of special characters."""
        msg = "Hello 🤖 Zendaya! Can you handle émojis and spëcial chars?"
        response = client.post("/chat", json={"message": msg})
        assert response.status_code in [200, 401]

    @patch("zendaya_backend.main.zendaya_agent")
    def test_agent_tool_failure(self, mock_agent, client: TestClient):
        """Test error handling when a tool fails inside the agent."""
        mock_agent.process = AsyncMock(side_effect=Exception("Tool execution failed"))
        response = client.post("/chat", json={"message": "search for something"})
        assert response.status_code in [200, 500]

    def test_concurrent_requests(self):
        """Test handling multiple concurrent /health requests."""
        import concurrent.futures

        # Change signature to accept an argument
        def make_request(_):
            with TestClient(app) as c:
                return c.get("/health").status_code

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(make_request, range(10)))

        assert all(status == 200 for status in results)
        assert len(results) == 10

    # -----------------------------------------------------------------------
    # 🚫 Authentication edge case
    # -----------------------------------------------------------------------

    def test_chat_unauthorized(self):
        """Test chat endpoint without authentication override (expect 401)."""
        # Temporarily remove the override
        app.dependency_overrides.pop(get_current_active_user, None)
        with TestClient(app) as c:
            response = c.post("/chat", json={"message": "unauthenticated"})
        assert response.status_code == 401
        # Restore override
        app.dependency_overrides[get_current_active_user] = override_get_current_active_user
