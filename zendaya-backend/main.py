"""
Zendaya AI Assistant - FastAPI Backend Service
JARVIS-inspired architecture with distributed components
"""
import os
import json
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from ai_core.gemini_service import GeminiService
from knowledge.rag_service import RAGService
from knowledge.voice_service import VoiceService
from agent.zendaya_agent import ZendayaAgent

# Initialize FastAPI app
app = FastAPI(
    title="Zendaya AI Assistant",
    description="JARVIS-inspired AI assistant with distributed architecture",
    version="1.0.0"
)

# CORS middleware for cross-platform clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
gemini_service = GeminiService()
rag_service = RAGService()
voice_service = VoiceService()
zendaya_agent = ZendayaAgent()

# Request/Response models
class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default"
    context: Optional[Dict[str, Any]] = None
    voice_enabled: bool = True

class ChatResponse(BaseModel):
    text: str
    audio_url: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    timestamp: str

class TranscribeRequest(BaseModel):
    audio_data: bytes

class SynthesizeRequest(BaseModel):
    text: str
    voice_id: str = "mxTlDrtKZzOqgjtBw4hM"

# Global conversation memory
conversation_memory: Dict[str, List[Dict[str, Any]]] = {}

@app.get("/")
async def root():
    return {
        "message": "Zendaya AI Assistant Backend",
        "status": "online",
        "architecture": "JARVIS-inspired distributed system",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    services_status = {
        "gemini": gemini_service.is_ready(),
        "elevenlabs": voice_service.is_ready(),
        "rag": rag_service.is_ready(),
        "agent": zendaya_agent.is_ready()
    }
    
    return {
        "status": "healthy" if all(services_status.values()) else "degraded",
        "services": services_status,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Main chat pipeline:
    1. Process input (text or transcribed audio)
    2. Retrieve relevant context from RAG
    3. Execute agent tools if needed
    4. Generate response via Gemini
    5. Synthesize speech via ElevenLabs
    """
    try:
        user_id = request.user_id
        message = request.message.strip()
        
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Initialize conversation memory for user
        if user_id not in conversation_memory:
            conversation_memory[user_id] = []
        
        # Add user message to memory
        conversation_memory[user_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Retrieve relevant context from RAG
        rag_context = await rag_service.query(message)
        
        # Execute agent tools if needed
        agent_result = await zendaya_agent.process(message, rag_context)
        
        # Generate AI response
        conversation_history = conversation_memory[user_id][-10:]  # Last 10 messages
        ai_response = await gemini_service.generate_response(
            message=message,
            context=rag_context,
            agent_result=agent_result,
            conversation_history=conversation_history,
            user_context=request.context
        )
        
        # Add AI response to memory
        conversation_memory[user_id].append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Synthesize speech if voice enabled
        audio_url = None
        if request.voice_enabled:
            audio_url = await voice_service.synthesize(ai_response)
        
        return ChatResponse(
            text=ai_response,
            audio_url=audio_url,
            context={"agent_actions": agent_result.get("actions", [])},
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")

@app.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """Transcribe audio to text using Google Speech-to-Text"""
    try:
        audio_data = await audio_file.read()
        transcript = await voice_service.transcribe(audio_data)
        return {"transcript": transcript}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

@app.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest):
    """Synthesize text to speech using ElevenLabs"""
    try:
        audio_url = await voice_service.synthesize(request.text, request.voice_id)
        return {"audio_url": audio_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech synthesis error: {str(e)}")

@app.post("/knowledge/ingest")
async def ingest_document(file: UploadFile = File(...)):
    """Ingest documents into the knowledge base"""
    try:
        content = await file.read()
        result = await rag_service.ingest_document(file.filename, content)
        return {"message": f"Document '{file.filename}' ingested successfully", "chunks": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Document ingestion error: {str(e)}")

@app.get("/knowledge/search")
async def search_knowledge(query: str, limit: int = 5):
    """Search the knowledge base"""
    try:
        results = await rag_service.query(query, limit)
        return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Knowledge search error: {str(e)}")

@app.get("/conversation/{user_id}")
async def get_conversation_history(user_id: str, limit: int = 20):
    """Get conversation history for a user"""
    history = conversation_memory.get(user_id, [])
    return {"history": history[-limit:]}

@app.delete("/conversation/{user_id}")
async def clear_conversation_history(user_id: str):
    """Clear conversation history for a user"""
    if user_id in conversation_memory:
        del conversation_memory[user_id]
    return {"message": f"Conversation history cleared for user {user_id}"}

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )