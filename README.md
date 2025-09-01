# Zendaya AI Assistant - JARVIS Architecture

A distributed AI assistant system inspired by JARVIS from Iron Man, featuring a FastAPI backend, Flutter client, and Unity AR client.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Zendaya AI System                        │
├─────────────────────────────────────────────────────────────┤
│  Frontend Clients                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Flutter Mobile  │  │ Unity AR Client │  │ Web Client  │ │
│  │ (Cross-platform)│  │ (HoloLens 2)    │  │ (Browser)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Backend Services (FastAPI)                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   AI Core       │  │   Knowledge     │  │   Agent     │ │
│  │ (Gemini API)    │  │ (RAG + Voice)   │  │ (LangChain) │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  External Services                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Google Gemini   │  │  ElevenLabs     │  │  Pinecone   │ │
│  │ (Intelligence)  │  │    (Voice)      │  │ (Knowledge) │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Features

### Core Intelligence
- **Conversational AI**: Powered by Google Gemini API
- **Personality**: Witty, confident assistant inspired by Shuri/JARVIS
- **Memory**: Persistent conversation history and context

### Voice Capabilities
- **Speech-to-Text**: Google Cloud Speech-to-Text API
- **Text-to-Speech**: ElevenLabs API with premium voice quality
- **Voice ID**: `mxTlDrtKZzOqgjtBw4hM` (Zendaya's signature voice)

### Knowledge System
- **RAG Pipeline**: Document ingestion with Pinecone vector database
- **Smart Retrieval**: Context-aware knowledge retrieval
- **Multi-format Support**: PDF, TXT document processing

### Agent Framework
- **LangChain Integration**: Sophisticated tool execution
- **Web Search**: Real-time information via Tavily API
- **Calendar Management**: Google Calendar integration
- **IoT Control**: Smart home device management (extensible)

### Multi-Platform Clients
- **Flutter**: Cross-platform mobile/desktop client
- **Unity AR**: HoloLens 2 augmented reality interface
- **Web**: Browser-based interface

## 🛠️ Setup Instructions

### 1. Backend Setup

```bash
cd zendaya-backend
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure your API keys:

```env
# Core AI Services
GEMINI_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Knowledge & Search
PINECONE_API_KEY=your_pinecone_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Google Services (optional)
GOOGLE_APPLICATION_CREDENTIALS=path/to/google-credentials.json
```

### 3. Required API Keys

| Service | Purpose | Required |
|---------|---------|----------|
| **Google Gemini** | Core AI intelligence | ✅ Yes |
| **ElevenLabs** | Premium voice synthesis | ✅ Yes |
| **Pinecone** | Vector database for RAG | ✅ Yes |
| **Tavily** | Web search capabilities | ✅ Yes |
| **Google Cloud** | Speech-to-Text (optional) | ⚪ Optional |

### 4. Start the Backend

```bash
cd zendaya-backend
python main.py
```

The API will be available at `http://localhost:8000`

## 📡 API Endpoints

### Core Chat API
- **POST** `/chat` - Main conversation endpoint
- **GET** `/health` - Service health check

### Voice Services
- **POST** `/transcribe` - Audio to text conversion
- **POST** `/synthesize` - Text to speech synthesis

### Knowledge Management
- **POST** `/knowledge/ingest` - Upload documents to knowledge base
- **GET** `/knowledge/search` - Search knowledge base

### Conversation Management
- **GET** `/conversation/{user_id}` - Get conversation history
- **DELETE** `/conversation/{user_id}` - Clear conversation history

## 🎯 Usage Examples

### Basic Chat
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What's the weather like today?",
    "user_id": "user123",
    "voice_enabled": true
  }'
```

### Document Ingestion
```bash
curl -X POST "http://localhost:8000/knowledge/ingest" \
  -F "file=@document.pdf"
```

## 🔧 Development

### Project Structure
```
zendaya-backend/
├── main.py                 # FastAPI application
├── ai_core/               # Gemini AI integration
│   └── gemini_service.py
├── knowledge/             # RAG and voice services
│   ├── rag_service.py
│   └── voice_service.py
├── agent/                 # LangChain agent framework
│   ├── zendaya_agent.py
│   └── tools/
│       ├── web_search.py
│       ├── calendar_manager.py
│       └── iot_controller.py
└── requirements.txt
```

### Adding New Tools
1. Create tool class in `agent/tools/`
2. Implement `get_tool()` method returning LangChain Tool
3. Register in `zendaya_agent.py`

## 🎮 Client Development

### Flutter Client
- Modern chat interface with voice recording
- Real-time audio playback of responses
- Cross-platform (iOS, Android, Desktop)

### Unity AR Client
- MRTK-based HoloLens 2 application
- 3D floating text responses in AR space
- Voice command integration

## 🔐 Security Notes

- API keys should never be committed to version control
- Use environment variables for all sensitive configuration
- Implement proper authentication for production deployment
- Consider rate limiting for API endpoints

## 📈 Roadmap

- [ ] Advanced memory management with long-term storage
- [ ] Multi-user support with user profiles
- [ ] Enhanced IoT integrations
- [ ] Custom voice training capabilities
- [ ] Advanced AR visualizations
- [ ] Plugin system for third-party integrations

---

**Built with ❤️ by the Zendaya AI Team**

*"My tech is always at your service."* - Zendaya