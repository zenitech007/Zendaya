# 🤖 Zendaya AI Assistant - JARVIS Architecture

<div align="center">

![Zendaya AI](https://img.shields.io/badge/Zendaya-AI%20Assistant-blue?style=for-the-badge&logo=robot)
![Python](https://img.shields.io/badge/Python-3.9+-green?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-red?style=for-the-badge&logo=fastapi)
![Flutter](https://img.shields.io/badge/Flutter-Mobile-blue?style=for-the-badge&logo=flutter)
![Unity](https://img.shields.io/badge/Unity-AR%20Client-black?style=for-the-badge&logo=unity)
![React](https://img.shields.io/badge/React-Dashboard-cyan?style=for-the-badge&logo=react)

**A distributed AI assistant system inspired by JARVIS from Iron Man and Griot from Black Panther**

[Features](#-features) • [Architecture](#-architecture) • [Setup](#-setup) • [Usage](#-usage) • [API](#-api-documentation) • [Contributing](#-contributing)

</div>

---

## 🌟 Features

### 🧠 Core Intelligence
- **Advanced AI**: Powered by Google Gemini 1.5 Pro with enhanced reasoning
- **Voice Recognition**: Biometric voice and face recognition for family members
- **Offline Intelligence**: Local knowledge base for autonomous operation
- **Error Understanding**: Advanced speech correction and clarification system

### 🏠 Universal Device Control
- **Cross-Platform Agents**: Control any device on your network (Windows, macOS, Linux, Android, iOS)
- **Smart Home Integration**: Philips Hue, TP-Link Kasa, Roku, Chromecast, Nest, Ring, and more
- **Network Discovery**: Automatic device scanning and capability detection
- **Secure Communication**: mTLS encryption for all device commands

### 🎙️ Advanced Voice Processing
- **Noise Cancellation**: Crystal-clear audio processing with librosa and noisereduce
- **ElevenLabs TTS**: Premium voice synthesis with emotional intelligence
- **Real-time Streaming**: Live audio streaming for immediate responses
- **Context Awareness**: Understands speech errors and provides intelligent corrections

### 🔄 Multi-Platform Clients
- **Flutter Mobile**: Cross-platform mobile and desktop client
- **Unity AR**: HoloLens 2 augmented reality interface with spatial anchors
- **React Dashboard**: Real-time system monitoring and control interface
- **Python CLI**: Command-line interface for direct system interaction

### 🛡️ Production-Ready Security
- **Supabase Auth**: Built-in authentication with JWT tokens
- **Supabase PostgreSQL**: Scalable cloud database with Row Level Security
- **Encrypted Communication**: All device communication secured with mTLS
- **Row Level Security**: Automatic data isolation per user
- **Comprehensive Testing**: Full test suite with CI/CD pipeline

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Zendaya AI System                        │
├─────────────────────────────────────────────────────────────┤
│  Frontend Clients                                           │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Flutter Mobile  │  │ Unity AR Client │  │ React Web   │ │
│  │ (Cross-platform)│  │ (HoloLens 2)    │  │ (Dashboard) │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Backend Services (FastAPI)                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   AI Core       │  │ Device Control  │  │   Agent     │ │
│  │ (Gemini Pro)    │  │ (Orchestrator)  │  │ (LangChain) │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│  Device Network                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │ Smart Home      │  │ Mobile Devices  │  │ Computers   │ │
│  │ (IoT Devices)   │  │ (iOS/Android)   │  │ (Win/Mac)   │ │
│  └─────────────────┘  └─────────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Setup

### Prerequisites
- Python 3.9+
- Node.js 16+
- Flutter 3.10+
- Unity 2022.3+ (for AR client)
- Supabase account (free tier available)

### 1. Backend Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/zendaya-ai-assistant.git
cd zendaya-ai-assistant

# Install Python dependencies with Poetry
cd zendaya-backend
pip install poetry
poetry install

# Setup environment variables
cp .env.example .env
# Edit .env with your Supabase credentials and API keys

# Test database connection
poetry run python test_db_connection.py

# Start the backend
poetry run python main.py
```

### 2. Web Dashboard

```bash
# Install dependencies
npm install

# Start development server
npm run dev
```

### 3. Flutter Client

```bash
cd zendaya-flutter-client
flutter pub get
flutter run
```

### 4. Unity AR Client

1. Open Unity Hub
2. Open the `zendaya-unity-ar-client` project
3. Import MRTK 2.8+
4. Configure for HoloLens 2
5. Build and deploy

---

## 🔧 Configuration

### Supabase Setup

1. **Create Supabase Project** at https://supabase.com
2. **Get your credentials** from Project Settings → API:
   - Project URL
   - `anon` public key
   - `service_role` secret key
3. **Get database password** from Project Settings → Database
4. **Database is ready** - Tables already created via migrations

### Required Environment Variables

Create a `.env` file in the root directory:

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_DB_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@db.your-project.supabase.co:5432/postgres

# Application Security
SECRET_KEY=generate-with-openssl-rand-hex-32
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# AI Services (optional but recommended)
# Core AI Services
GEMINI_API_KEY=your_gemini_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here

# Knowledge & Search
PINECONE_API_KEY=your_pinecone_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost/zendaya
# Or use SQLite: sqlite:///./zendaya.db

# Security
SECRET_KEY=your-super-secret-key-change-this-in-production
```

### Device Control Setup

1. **Smart Home Devices**: Ensure devices are on the same network
2. **Mobile Devices**: Install the Flutter client
3. **Computers**: Run the Python CLI client
4. **Network Security**: Configure firewall rules for device communication

---

## 📱 Usage Examples

### Voice Commands
```
"Zendaya, turn on the living room lights"
"Zendaya, what's the weather like today?"
"Zendaya, send a message to my wife saying I'm coming home"
"Zendaya, show my calendar on the wall" (AR client)
```

### Complex Workflows
```
"Zendaya, turn on the living room TV then text my wife on WhatsApp 
when she is coming home, after checking available restaurants for 
dinner reservation tonight"
```

### Device Control
```
"Zendaya, power off my phone"
"Zendaya, send this file to my laptop"
"Zendaya, take a screenshot of my tablet"
```

---

## 📡 API Documentation

The FastAPI backend provides comprehensive API documentation:

- **Interactive Docs**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI Schema**: `http://localhost:8000/openapi.json`

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | User authentication |
| `/chat` | POST | Main conversation endpoint |
| `/devices/discover` | POST | Discover network devices |
| `/devices/control` | POST | Control specific device |
| `/biometric/register` | POST | Register family member |
| `/workflow/execute` | POST | Execute complex workflow |

---

## 🧪 Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=zendaya_backend

# Run specific test file
poetry run pytest tests/test_main.py -v
```

### Test Coverage
- Unit tests for core services
- Integration tests for API endpoints
- Mock external services
- Authentication and security tests

---

## 🔄 CI/CD Pipeline

The project includes a comprehensive GitHub Actions workflow:

- **Code Quality**: Linting, formatting, type checking
- **Testing**: Unit and integration tests
- **Security**: Dependency scanning with Trivy
- **Multi-Platform**: Tests across Python, Flutter, and TypeScript

---

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guidelines](CONTRIBUTING.md) for details.

### Development Setup

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Code Style

- Python: Black formatting, isort imports, flake8 linting
- TypeScript: ESLint with Prettier
- Flutter: Dart formatting with flutter format

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- **Inspiration**: JARVIS (Iron Man) and Griot (Black Panther)
- **AI Services**: Google Gemini, ElevenLabs, Pinecone
- **Frameworks**: FastAPI, Flutter, Unity MRTK, React
- **Community**: Open source contributors and testers

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/zendaya-ai-assistant/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/zendaya-ai-assistant/discussions)
- **Documentation**: [Wiki](https://github.com/yourusername/zendaya-ai-assistant/wiki)

---

<div align="center">

**Built with ❤️ by the Zendaya AI Team**

*"My tech is always at your service."* - Zendaya

</div>