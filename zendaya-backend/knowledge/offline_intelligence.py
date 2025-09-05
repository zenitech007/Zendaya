"""
Offline Intelligence - Local knowledge base and reasoning
"""
import os
import json
import sqlite3
import pickle
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
from pathlib import Path

class OfflineIntelligence:
    def __init__(self, data_dir: str = "offline_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize databases
        self.knowledge_db = self.data_dir / "knowledge.db"
        self.conversation_db = self.data_dir / "conversations.db"
        self.cache_db = self.data_dir / "cache.db"
        
        # Knowledge categories
        self.knowledge_file = self.data_dir / "knowledge_base.json"
        self.patterns_file = self.data_dir / "response_patterns.json"
        
        self._initialize_databases()
        self._load_base_knowledge()
    
    def _initialize_databases(self):
        """Initialize SQLite databases for offline storage"""
        # Knowledge database
        with sqlite3.connect(self.knowledge_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge (
                    id INTEGER PRIMARY KEY,
                    category TEXT,
                    question_hash TEXT UNIQUE,
                    question TEXT,
                    answer TEXT,
                    confidence REAL,
                    last_used TIMESTAMP,
                    usage_count INTEGER DEFAULT 0
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY,
                    topic TEXT,
                    fact TEXT,
                    source TEXT,
                    reliability REAL,
                    timestamp TIMESTAMP
                )
            """)
        
        # Conversation database
        with sqlite3.connect(self.conversation_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY,
                    user_id TEXT,
                    message TEXT,
                    response TEXT,
                    timestamp TIMESTAMP,
                    context TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    preferences TEXT,
                    last_updated TIMESTAMP
                )
            """)
        
        # Cache database
        with sqlite3.connect(self.cache_db) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS api_cache (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT,
                    response TEXT,
                    timestamp TIMESTAMP,
                    expiry TIMESTAMP
                )
            """)
    
    def _load_base_knowledge(self):
        """Load comprehensive base knowledge"""
        base_knowledge = {
            "system_info": {
                "What are you?": "I am Zendaya, an advanced AI assistant inspired by JARVIS and Griot. I'm designed to help you with various tasks, from simple questions to complex system management.",
                "Who created you?": "I was created as an advanced AI assistant system with distributed architecture, featuring cognitive intelligence, knowledge management, and comprehensive device control.",
                "What can you do?": "I can control devices, manage your schedule, search the web, handle files, monitor system performance, control smart home devices, and much more. I'm designed to be your comprehensive digital assistant."
            },
            "device_control": {
                "How do I open an application?": "Just tell me to 'open [application name]' and I'll launch it for you. I can open browsers, text editors, media players, and most installed applications.",
                "How do I control system volume?": "I can adjust your system volume by saying 'set volume to [level]' or 'increase/decrease volume'. I have full audio control capabilities.",
                "How do I manage files?": "I can help you find, copy, move, or organize files. Just tell me what you need to do with which files."
            },
            "smart_home": {
                "How do I control lights?": "I can control smart lights by saying 'turn on/off lights' or 'dim lights to [percentage]'. I support various smart home protocols.",
                "How do I adjust temperature?": "Tell me 'set temperature to [degrees]' and I'll adjust your smart thermostat accordingly.",
                "How do I check security?": "I can monitor your security system status and provide alerts about any unusual activity."
            },
            "productivity": {
                "How do I schedule meetings?": "I can access your calendar and schedule meetings. Just tell me the details and I'll handle the scheduling.",
                "How do I manage emails?": "I can read your emails, compose responses, and organize your inbox based on your preferences.",
                "How do I set reminders?": "Just tell me what you want to be reminded about and when, and I'll make sure you don't forget."
            },
            "troubleshooting": {
                "System running slow?": "I can diagnose performance issues, close unnecessary applications, clear temporary files, and optimize your system for better performance.",
                "Internet connection issues?": "I can run network diagnostics, reset network adapters, and help troubleshoot connectivity problems.",
                "Application not responding?": "I can force-close unresponsive applications and restart them, or suggest alternative solutions."
            }
        }
        
        # Save base knowledge if file doesn't exist
        if not self.knowledge_file.exists():
            with open(self.knowledge_file, 'w') as f:
                json.dump(base_knowledge, f, indent=2)
        
        # Load response patterns
        response_patterns = {
            "greeting": [
                "Hello! I'm Zendaya, your AI assistant. How can I help you today?",
                "Good to see you! What can I assist you with?",
                "Hey there! Ready to get things done together?"
            ],
            "confirmation": [
                "Absolutely, I'll take care of that right away.",
                "Consider it done. I'm on it.",
                "Perfect, executing that command now."
            ],
            "error_recovery": [
                "Let me try a different approach to solve this.",
                "I'll find another way to accomplish that for you.",
                "No worries, I have alternative methods to handle this."
            ],
            "clarification": [
                "I want to make sure I understand correctly. Could you clarify?",
                "Just to be certain, are you asking me to",
                "Let me confirm what you need:"
            ]
        }
        
        if not self.patterns_file.exists():
            with open(self.patterns_file, 'w') as f:
                json.dump(response_patterns, f, indent=2)
    
    def store_knowledge(self, question: str, answer: str, category: str = "general", confidence: float = 1.0):
        """Store new knowledge for offline access"""
        question_hash = hashlib.md5(question.lower().encode()).hexdigest()
        
        with sqlite3.connect(self.knowledge_db) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO knowledge 
                (category, question_hash, question, answer, confidence, last_used, usage_count)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT usage_count FROM knowledge WHERE question_hash = ?), 0))
            """, (category, question_hash, question, answer, confidence, datetime.now(), question_hash))
    
    def query_offline_knowledge(self, query: str) -> Optional[Dict[str, Any]]:
        """Query offline knowledge base"""
        query_lower = query.lower()
        query_hash = hashlib.md5(query_lower.encode()).hexdigest()
        
        with sqlite3.connect(self.knowledge_db) as conn:
            # Direct match
            result = conn.execute("""
                SELECT question, answer, confidence, category
                FROM knowledge 
                WHERE question_hash = ?
            """, (query_hash,)).fetchone()
            
            if result:
                # Update usage statistics
                conn.execute("""
                    UPDATE knowledge 
                    SET last_used = ?, usage_count = usage_count + 1
                    WHERE question_hash = ?
                """, (datetime.now(), query_hash))
                
                return {
                    "answer": result[1],
                    "confidence": result[2],
                    "category": result[3],
                    "source": "offline_direct"
                }
            
            # Fuzzy matching
            all_questions = conn.execute("""
                SELECT question, answer, confidence, category
                FROM knowledge
            """).fetchall()
            
            best_match = None
            best_score = 0
            
            for q, a, c, cat in all_questions:
                score = self._calculate_similarity(query_lower, q.lower())
                if score > 0.7 and score > best_score:
                    best_score = score
                    best_match = {
                        "answer": a,
                        "confidence": c * score,
                        "category": cat,
                        "source": "offline_fuzzy",
                        "similarity": score
                    }
            
            return best_match
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate text similarity using simple word overlap"""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def cache_api_response(self, query: str, response: str, expiry_hours: int = 24):
        """Cache API responses for offline access"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        expiry = datetime.now() + timedelta(hours=expiry_hours)
        
        with sqlite3.connect(self.cache_db) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO api_cache 
                (query_hash, query, response, timestamp, expiry)
                VALUES (?, ?, ?, ?, ?)
            """, (query_hash, query, response, datetime.now(), expiry))
    
    def get_cached_response(self, query: str) -> Optional[str]:
        """Retrieve cached API response"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        
        with sqlite3.connect(self.cache_db) as conn:
            result = conn.execute("""
                SELECT response FROM api_cache 
                WHERE query_hash = ? AND expiry > ?
            """, (query_hash, datetime.now())).fetchone()
            
            return result[0] if result else None
    
    def store_conversation(self, user_id: str, message: str, response: str, context: Dict[str, Any] = None):
        """Store conversation for learning"""
        with sqlite3.connect(self.conversation_db) as conn:
            conn.execute("""
                INSERT INTO conversations 
                (user_id, message, response, timestamp, context)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, message, response, datetime.now(), json.dumps(context or {})))
    
    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Get user context and preferences"""
        with sqlite3.connect(self.conversation_db) as conn:
            # Get recent conversations
            recent = conn.execute("""
                SELECT message, response, context 
                FROM conversations 
                WHERE user_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 10
            """, (user_id,)).fetchall()
            
            # Get preferences
            prefs = conn.execute("""
                SELECT preferences 
                FROM user_preferences 
                WHERE user_id = ?
            """, (user_id,)).fetchone()
            
            return {
                "recent_conversations": [
                    {"message": r[0], "response": r[1], "context": json.loads(r[2] or "{}")}
                    for r in recent
                ],
                "preferences": json.loads(prefs[0]) if prefs else {}
            }
    
    def generate_offline_response(self, query: str, user_id: str = "default") -> Dict[str, Any]:
        """Generate response using offline intelligence"""
        # Check direct knowledge
        knowledge_result = self.query_offline_knowledge(query)
        if knowledge_result and knowledge_result["confidence"] > 0.8:
            return {
                "response": knowledge_result["answer"],
                "confidence": knowledge_result["confidence"],
                "source": "offline_knowledge",
                "needs_online": False
            }
        
        # Check cached responses
        cached = self.get_cached_response(query)
        if cached:
            return {
                "response": cached,
                "confidence": 0.9,
                "source": "cached",
                "needs_online": False
            }
        
        # Generate contextual response
        user_context = self.get_user_context(user_id)
        
        # Load response patterns
        with open(self.patterns_file, 'r') as f:
            patterns = json.load(f)
        
        # Determine response type
        query_lower = query.lower()
        
        if any(word in query_lower for word in ["hello", "hi", "hey", "good morning", "good afternoon"]):
            response = patterns["greeting"][0]
            confidence = 1.0
        elif any(word in query_lower for word in ["help", "what can you do", "capabilities"]):
            response = "I can help you with device control, file management, system monitoring, smart home control, scheduling, and much more. Even offline, I have extensive knowledge to assist you."
            confidence = 1.0
        elif knowledge_result:
            response = f"{knowledge_result['answer']} (Note: I'm currently offline, so this information might not be the most current.)"
            confidence = knowledge_result["confidence"] * 0.8
        else:
            response = "I understand you're asking about something, but I don't have that information in my offline knowledge base. When I'm back online, I'll be able to help you better with that."
            confidence = 0.3
        
        return {
            "response": response,
            "confidence": confidence,
            "source": "offline_generated",
            "needs_online": confidence < 0.7
        }
    
    def learn_from_interaction(self, query: str, response: str, user_feedback: str = None):
        """Learn from user interactions to improve offline responses"""
        if user_feedback and "correct" in user_feedback.lower():
            self.store_knowledge(query, response, confidence=0.9)
        elif user_feedback and "wrong" in user_feedback.lower():
            # Mark as low confidence or remove
            self.store_knowledge(query, f"[UNCERTAIN] {response}", confidence=0.3)
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old cached data"""
        cutoff = datetime.now() - timedelta(days=days)
        
        with sqlite3.connect(self.cache_db) as conn:
            conn.execute("DELETE FROM api_cache WHERE timestamp < ?", (cutoff,))
        
        with sqlite3.connect(self.conversation_db) as conn:
            conn.execute("DELETE FROM conversations WHERE timestamp < ?", (cutoff,))