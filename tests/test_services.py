"""
Unit tests for core services
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from zendaya_backend.ai_core.gemini_service import GeminiService
from zendaya_backend.knowledge.rag_service import RAGService
from zendaya_backend.knowledge.voice_service import VoiceService


class TestGeminiService:
    """Test Gemini AI service"""
    
    def test_initialization(self):
        """Test service initialization"""
        service = GeminiService()
        assert service.model_name == "gemini-2.5-flash"
    
    @patch('google.genai.Client')
    def test_is_ready(self, mock_client):
        """Test service ready check"""
        service = GeminiService()
        service.client = Mock()
        assert service.is_ready() == True
    
    @pytest.mark.asyncio
    @patch('google.genai.Client')
    async def test_generate_response(self, mock_client_class):
        """Test response generation"""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.text = "Test response"
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        service = GeminiService()
        service.client = mock_client
        
        response = await service.generate_response("Test message")
        assert response == "Test response"


class TestRAGService:
    """Test RAG service"""
    
    def test_initialization(self):
        """Test service initialization"""
        service = RAGService()
        assert service.index_name == "zendaya-knowledge"
    
    @patch('pinecone.Pinecone')
    def test_is_ready(self, mock_pinecone):
        """Test service ready check"""
        service = RAGService()
        service.index = Mock()
        service.embedding_model = Mock()
        assert service.is_ready() == True
    
    @pytest.mark.asyncio
    async def test_query_empty_result(self):
        """Test query with empty result"""
        service = RAGService()
        service.index = None
        service.embedding_model = None
        
        result = await service.query("test query")
        assert result == ""


class TestVoiceService:
    """Test advanced voice service"""
    
    def test_initialization(self):
        """Test service initialization"""
        service = VoiceService()
        assert service.default_voice_id == "mxTlDrtKZzOqgjtBw4hM"
    
    def test_is_ready(self):
        """Test service ready check"""
        service = VoiceService()
        service.elevenlabs_api_key = "test-key"
        assert service.is_ready() == True
    
    @pytest.mark.asyncio
    async def test_preprocess_audio(self):
        """Test audio preprocessing"""
        service = VoiceService()
        test_audio = b"test audio data"
        
        # Should return original audio if processing fails
        result = await service.preprocess_audio(test_audio)
        assert isinstance(result, bytes)
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_synthesize_with_emotion(self, mock_client):
        """Test speech synthesis with emotion"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b"audio data"
        
        mock_client_instance = Mock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client.return_value.__aexit__ = AsyncMock(return_value=None)
        
        service = VoiceService()
        service.elevenlabs_api_key = "test-key"
        
        result = await service.synthesize_with_emotion("Test text", "confident")
        assert result is not None
        assert result.startswith("/audio/")