"""
zendaya_backend/services/chat.py

Core ChatService for handling conversational logic.
---------------------------------------------------
- Lightweight foundation for message handling.
- Supports async operations.
- Keeps per-user session context.
- Designed to integrate with RAGChatService (for retrieval-augmented memory).
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


class ChatService:
    """Base Chat Service responsible for managing sessions and message exchange."""

    def __init__(self):
        # Store per-user sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        logger.info("[ChatService] Initialized core chat manager.")

    # -------------------------------------------------------------------------
    # Session Management
    # -------------------------------------------------------------------------
    async def create_session(self, user_id: str) -> bool:
        """Create or reset a new chat session for a given user."""
        try:
            if user_id not in self.active_sessions:
                self.active_sessions[user_id] = {
                    "messages": [],
                    "created_at": datetime.utcnow(),
                }
                logger.debug(f"[ChatService] Created session for user {user_id}")
            return True
        except Exception as e:
            logger.exception(f"[ChatService] Failed to create session: {e}")
            return False

    async def reset_session(self, user_id: str) -> bool:
        """Force reset of an existing session."""
        try:
            self.active_sessions[user_id] = {"messages": [], "created_at": datetime.utcnow()}
            logger.debug(f"[ChatService] Reset session for user {user_id}")
            return True
        except Exception as e:
            logger.exception(f"[ChatService] Failed to reset session: {e}")
            return False

    async def get_session_history(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieve the last N messages for a given user session."""
        try:
            session = self.active_sessions.get(user_id)
            if not session:
                return []
            messages = session["messages"][-limit:]
            return messages
        except Exception as e:
            logger.exception(f"[ChatService] Error retrieving history: {e}")
            return []

    # -------------------------------------------------------------------------
    # Messaging Logic
    # -------------------------------------------------------------------------
    async def send_message(self, user_id: str, message: str) -> Optional[str]:
        """Send a message in a chat session."""
        try:
            if user_id not in self.active_sessions:
                await self.create_session(user_id)

            self.active_sessions[user_id]["messages"].append({
                "role": "user",
                "content": message,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.debug(f"[ChatService] Received message from {user_id}: {message}")
            # In production, route this message to an AI model
            return "Message received"
        except Exception as e:
            logger.exception(f"[ChatService] Failed to send message: {e}")
            return None

    async def process_message(
        self,
        message: str,
        user: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a user's chat message and return an AI response placeholder.
        In advanced setups, this is extended by RAGChatService.
        """
        try:
            user_id = getattr(user, "username", "default")

            # Ensure user session exists
            if user_id not in self.active_sessions:
                await self.create_session(user_id)

            # Store user message
            await self.send_message(user_id, message)

            # Mock AI logic (replace with Gemini/OpenAI call)
            ai_reply = f"I received your message: '{message}'. How can I help you further?"

            # Store bot reply
            self.active_sessions[user_id]["messages"].append({
                "role": "assistant",
                "content": ai_reply,
                "timestamp": datetime.utcnow().isoformat()
            })

            logger.debug(f"[ChatService] Processed message for {user_id}")

            return {
                "text": ai_reply,
                "timestamp": datetime.utcnow().isoformat(),
                "context": context or {},
                "clarification_needed": False
            }

        except Exception as e:
            logger.exception(f"[ChatService] Processing message failed: {e}")
            return {
                "text": "I'm having trouble processing your message.",
                "clarification_needed": True
            }

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------
    async def delete_user_session(self, user_id: str) -> bool:
        """Completely remove a user's chat history."""
        try:
            if user_id in self.active_sessions:
                del self.active_sessions[user_id]
                logger.debug(f"[ChatService] Deleted session for user {user_id}")
                return True
            return False
        except Exception as e:
            logger.exception(f"[ChatService] Failed to delete session: {e}")
            return False

    async def summarize_history(self, user_id: str) -> str:
        """Summarize a user's past conversation (basic placeholder)."""
        try:
            history = await self.get_session_history(user_id, limit=5)
            if not history:
                return "No recent conversation found."
            messages = [m["content"] for m in history if m.get("role") == "user"]
            summary = f"Summary of your recent chat: {' | '.join(messages)}"
            logger.debug(f"[ChatService] Generated summary for {user_id}")
            return summary
        except Exception as e:
            logger.exception(f"[ChatService] Failed to summarize: {e}")
            return "Unable to summarize chat history right now."

    async def cleanup_inactive_sessions(self, max_age_minutes: int = 30):
        """Periodically clean up inactive user sessions."""
        try:
            now = datetime.utcnow()
            to_delete = []
            for user_id, session in self.active_sessions.items():
                if (now - session["created_at"]).total_seconds() > max_age_minutes * 60:
                    to_delete.append(user_id)

            for user_id in to_delete:
                del self.active_sessions[user_id]
                logger.info(f"[ChatService] Cleaned inactive session: {user_id}")
        except Exception as e:
            logger.exception(f"[ChatService] Failed to cleanup sessions: {e}")

