"""
Gemini AI Service - Core conversational intelligence
"""
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model_name = "gemini-1.5-flash"
        self.model = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Gemini API"""
        if not self.api_key:
            print("Warning: GEMINI_API_KEY not found in environment")
            return
        
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
            print("✅ Gemini AI service initialized")
        except Exception as e:
            print(f"❌ Failed to initialize Gemini: {e}")
    
    def is_ready(self) -> bool:
        """Check if the service is ready"""
        return self.model is not None
    
    async def generate_response(
        self,
        message: str,
        context: Optional[str] = None,
        agent_result: Optional[Dict[str, Any]] = None,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate AI response using Gemini"""
        if not self.is_ready():
            return "My cognitive core is offline. Please check the Gemini API configuration."
        
        # Build system prompt
        system_prompt = self._build_system_prompt(user_context)
        
        # Build context
        context_parts = []
        
        if context:
            context_parts.append(f"Knowledge Context:\n{context}")
        
        if agent_result and agent_result.get("actions"):
            actions_summary = "\n".join([f"- {action}" for action in agent_result["actions"]])
            context_parts.append(f"Actions Executed:\n{actions_summary}")
        
        if conversation_history:
            history_text = self._format_conversation_history(conversation_history)
            context_parts.append(f"Recent Conversation:\n{history_text}")
        
        # Combine all parts
        full_prompt = [system_prompt]
        if context_parts:
            full_prompt.append("\n".join(context_parts))
        full_prompt.append(f"User: {message}\nZendaya:")
        
        try:
            response = self.model.generate_content("\n\n".join(full_prompt))
            return response.text.strip()
        except Exception as e:
            return f"I encountered an error processing your request: {str(e)}"
    
    def _build_system_prompt(self, user_context: Optional[Dict[str, Any]] = None) -> str:
        """Build the system prompt for Zendaya"""
        base_prompt = (
            "You are Zendaya, a brilliant, witty, confident AI assistant inspired by JARVIS from Iron Man "
            "and characters like Shuri from Black Panther. You are the cognitive core of a distributed AI system.\n\n"
            "Personality traits:\n"
            "- Speak like a friendly genius with occasional playful quips\n"
            "- Keep responses concise but informative (typically 2-4 sentences)\n"
            "- Show confidence in your capabilities\n"
            "- Be helpful while maintaining your witty personality\n"
            "- Use provided context and search results to give accurate information\n"
            "- Don't hallucinate facts - if you're unsure, say so\n\n"
            "You have access to various tools and can perform actions like web searches, "
            "calendar management, and system control through your agent framework."
        )
        
        if user_context and user_context.get("professional_mode"):
            base_prompt += "\n\nIMPORTANT: Professional mode is active. Maintain a formal, direct tone."
        
        return base_prompt
    
    def _format_conversation_history(self, history: List[Dict[str, Any]]) -> str:
        """Format conversation history for context"""
        formatted = []
        for msg in history[-6:]:  # Last 6 messages
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            formatted.append(f"{role.capitalize()}: {content}")
        return "\n".join(formatted)