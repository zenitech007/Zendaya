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
from knowledge.voice_service import AdvancedVoiceService
from knowledge.offline_intelligence import OfflineIntelligence
from ai_core.error_understanding import ErrorUnderstandingEngine
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
voice_service = AdvancedVoiceService()
offline_intelligence = OfflineIntelligence()
error_engine = ErrorUnderstandingEngine()
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
    emotion: Optional[str] = "confident"
    clarification_needed: bool = False
    suggestions: Optional[List[str]] = None
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
        "agent": zendaya_agent.is_ready(),
        "offline_intelligence": True,
        "error_understanding": True
    }
    
    return {
        "status": "healthy" if all(services_status.values()) else "degraded",
        "services": services_status,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Enhanced chat pipeline with error understanding and offline capabilities:
    1. Process input (text or transcribed audio)
    2. Analyze for errors and clarification needs
    3. Try offline intelligence first
    4. Retrieve relevant context from RAG
    5. Execute agent tools if needed
    6. Generate response via Gemini with emotional intelligence
    7. Synthesize speech via ElevenLabs with appropriate emotion
    """
    try:
        user_id = request.user_id
        message = request.message.strip()
        
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Analyze input for errors and understanding
        error_context = error_engine.analyze_input(message)
        
        # Check if clarification is needed
        if error_context.confidence < 0.6:
            clarification = error_engine.generate_clarification_response(error_context)
            if clarification:
                audio_url = await voice_service.synthesize_with_emotion(clarification, "concerned")
                return ChatResponse(
                    text=clarification,
                    audio_url=audio_url,
                    emotion="concerned",
                    clarification_needed=True,
                    suggestions=error_context.suggested_corrections,
                    timestamp=datetime.now().isoformat()
                )
        
        # Use corrected message if available
        processed_message = error_context.suggested_corrections[0] if error_context.suggested_corrections else message
        
        # Initialize conversation memory for user
        if user_id not in conversation_memory:
            conversation_memory[user_id] = []
        
        # Add user message to memory
        conversation_memory[user_id].append({
            "role": "user",
            "content": processed_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Try offline intelligence first
        offline_result = offline_intelligence.generate_offline_response(processed_message, user_id)
        
        if not offline_result["needs_online"] and offline_result["confidence"] > 0.7:
            # Store successful offline interaction
            offline_intelligence.store_conversation(user_id, processed_message, offline_result["response"])
            
            # Determine emotion based on response type
            emotion = "helpful" if "help" in processed_message.lower() else "confident"
            audio_url = await voice_service.synthesize_with_emotion(offline_result["response"], emotion)
            
            return ChatResponse(
                text=offline_result["response"],
                audio_url=audio_url,
                emotion=emotion,
                context={"source": offline_result["source"], "offline": True},
                timestamp=datetime.now().isoformat()
            )
        
        # Retrieve relevant context from RAG
        rag_context = await rag_service.query(processed_message)
        
        # Execute agent tools if needed
        agent_result = await zendaya_agent.process(processed_message, rag_context)
        
        # Generate AI response
        conversation_history = conversation_memory[user_id][-10:]  # Last 10 messages
        ai_response = await gemini_service.generate_response(
            message=processed_message,
            context=rag_context,
            agent_result=agent_result,
            conversation_history=conversation_history,
            user_context=request.context,
            error_context=error_context
        )
        
        # Add AI response to memory
        conversation_memory[user_id].append({
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Store knowledge for offline use
        offline_intelligence.store_knowledge(processed_message, ai_response, "conversation", 0.8)
        offline_intelligence.store_conversation(user_id, processed_message, ai_response, request.context)
        
        # Cache response for offline access
        offline_intelligence.cache_api_response(processed_message, ai_response)
        
        # Determine appropriate emotion for response
        emotion = "confident"
        if any(word in processed_message.lower() for word in ["help", "problem", "issue", "error"]):
            emotion = "helpful"
        elif any(word in processed_message.lower() for word in ["great", "awesome", "perfect", "excellent"]):
            emotion = "excited"
        elif any(word in ai_response.lower() for word in ["sorry", "unfortunately", "cannot", "unable"]):
            emotion = "concerned"
        
        # Synthesize speech if voice enabled
        audio_url = None
        if request.voice_enabled:
            audio_url = await voice_service.synthesize_with_emotion(ai_response, emotion)
        
        return ChatResponse(
            text=ai_response,
            audio_url=audio_url,
            emotion=emotion,
            context={
                "agent_actions": agent_result.get("actions", []),
                "error_analysis": {
                    "confidence": error_context.confidence,
                    "corrections_applied": len(error_context.suggested_corrections) > 0
                },
                "offline_capable": True
            },
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat processing error: {str(e)}")

@app.post("/transcribe")
async def transcribe_audio(audio_file: UploadFile = File(...), context_phrases: List[str] = None):
    """Enhanced transcribe audio with noise cancellation and error detection"""
    try:
        audio_data = await audio_file.read()
        result = await voice_service.transcribe_with_context(audio_data, context_phrases)
        
        # Generate clarification if needed
        clarification = ""
        if result["needs_clarification"]:
            clarification = await voice_service.generate_clarification_question(result)
        
        return {
            "transcript": result["transcript"],
            "confidence": result["confidence"],
            "quality_score": result["quality_score"],
            "alternatives": result["alternatives"],
            "needs_clarification": result["needs_clarification"],
            "clarification_question": clarification,
            "word_details": result["word_details"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")

@app.post("/synthesize")
async def synthesize_speech(request: SynthesizeRequest, emotion: str = "confident"):
    """Enhanced synthesize text to speech with emotional intelligence"""
    try:
        audio_url = await voice_service.synthesize_with_emotion(request.text, emotion, request.voice_id)
        return {"audio_url": audio_url, "emotion": emotion}
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

@app.post("/offline/learn")
async def learn_from_feedback(user_id: str, query: str, response: str, feedback: str):
    """Learn from user feedback to improve offline responses"""
    try:
        offline_intelligence.learn_from_interaction(query, response, feedback)
        return {"message": "Learning recorded successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Learning error: {str(e)}")

@app.get("/offline/status")
async def offline_status():
    """Get offline intelligence status"""
    return {
        "offline_ready": True,
        "knowledge_entries": "Available",
        "cached_responses": "Available",
        "last_cleanup": "Available"
    }

@app.post("/analyze/input")
async def analyze_input(text: str, transcription_data: Dict[str, Any] = None):
    """Analyze input for errors and understanding"""
    try:
        error_context = error_engine.analyze_input(text, transcription_data)
        return {
            "error_type": error_context.error_type,
            "confidence": error_context.confidence,
            "suggested_corrections": error_context.suggested_corrections,
            "context_clues": error_context.context_clues,
            "user_intent": error_context.user_intent,
            "clarification_needed": error_context.confidence < 0.6
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Input analysis error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )