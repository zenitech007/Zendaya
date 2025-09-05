"""
Advanced Error Understanding and Context Analysis
"""
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import difflib
from dataclasses import dataclass

@dataclass
class ErrorContext:
    error_type: str
    confidence: float
    suggested_corrections: List[str]
    context_clues: List[str]
    user_intent: str

class ErrorUnderstandingEngine:
    def __init__(self):
        self.common_errors = self._load_common_errors()
        self.context_patterns = self._load_context_patterns()
        self.intent_classifiers = self._load_intent_classifiers()
    
    def _load_common_errors(self) -> Dict[str, Any]:
        """Load common speech recognition and user input errors"""
        return {
            "homophones": {
                "there": ["their", "they're"],
                "to": ["too", "two"],
                "your": ["you're"],
                "its": ["it's"],
                "open": ["upon"],
                "close": ["clothes", "chose"],
                "file": ["while", "pile"],
                "system": ["sister", "cyst"],
                "control": ["central", "patrol"],
                "device": ["devise", "the vice"],
                "calendar": ["calender"],
                "email": ["e-mail", "gmail"],
                "volume": ["column"],
                "temperature": ["temp", "temper"],
                "security": ["secure", "securely"]
            },
            "technical_terms": {
                "api": ["a p i", "app", "happy"],
                "cpu": ["c p u", "see you"],
                "gpu": ["g p u", "gee you"],
                "ram": ["r a m", "ram memory"],
                "ssd": ["s s d", "solid state"],
                "wifi": ["wi-fi", "wireless", "wife i"],
                "bluetooth": ["blue tooth", "blue two"],
                "ethernet": ["ether net", "internet"]
            },
            "command_variations": {
                "open": ["launch", "start", "run", "execute", "begin"],
                "close": ["quit", "exit", "stop", "end", "kill", "terminate"],
                "increase": ["raise", "up", "higher", "more", "boost"],
                "decrease": ["lower", "down", "less", "reduce", "drop"],
                "set": ["change", "adjust", "modify", "configure"],
                "show": ["display", "view", "see", "list"],
                "find": ["search", "locate", "look for", "get"],
                "delete": ["remove", "erase", "clear", "destroy"]
            }
        }
    
    def _load_context_patterns(self) -> Dict[str, List[str]]:
        """Load context patterns for better understanding"""
        return {
            "device_control": [
                r"\b(turn|switch|set|adjust|control|manage)\b.*\b(on|off|up|down|to)\b",
                r"\b(open|close|start|stop|launch|quit)\b.*\b(app|application|program|software)\b",
                r"\b(volume|brightness|temperature|speed|power)\b",
                r"\b(lights|music|tv|computer|phone|tablet)\b"
            ],
            "file_management": [
                r"\b(file|folder|document|picture|video|music)\b",
                r"\b(copy|move|delete|rename|create|save)\b",
                r"\b(desktop|downloads|documents|pictures)\b",
                r"\.(txt|pdf|doc|jpg|png|mp3|mp4|exe)\b"
            ],
            "system_info": [
                r"\b(system|computer|pc|laptop|device)\b.*\b(status|info|performance|health)\b",
                r"\b(cpu|memory|ram|disk|storage|battery)\b",
                r"\b(running|slow|fast|hot|cold|full|empty)\b"
            ],
            "calendar_schedule": [
                r"\b(meeting|appointment|event|schedule|calendar)\b",
                r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                r"\b(morning|afternoon|evening|night|am|pm)\b",
                r"\b(remind|notification|alert)\b"
            ],
            "communication": [
                r"\b(email|message|text|call|contact)\b",
                r"\b(send|receive|reply|forward|delete)\b",
                r"\b(inbox|outbox|draft|spam)\b"
            ]
        }
    
    def _load_intent_classifiers(self) -> Dict[str, Dict[str, Any]]:
        """Load intent classification patterns"""
        return {
            "command": {
                "patterns": [r"^(please\s+)?(can\s+you\s+)?(\w+)\s+", r"\b(do|make|create|execute|run)\b"],
                "confidence_boost": 0.2
            },
            "question": {
                "patterns": [r"^(what|how|when|where|why|who|which)\b", r"\?$"],
                "confidence_boost": 0.1
            },
            "request": {
                "patterns": [r"\b(could|would|can|will)\s+you\b", r"\bplease\b"],
                "confidence_boost": 0.15
            },
            "information": {
                "patterns": [r"\b(tell|show|display|list|find)\b.*\b(me|about|for)\b"],
                "confidence_boost": 0.1
            }
        }
    
    def analyze_input(self, user_input: str, transcription_data: Dict[str, Any] = None) -> ErrorContext:
        """Comprehensive analysis of user input for errors and intent"""
        
        # Initial analysis
        cleaned_input = self._clean_input(user_input)
        potential_errors = self._detect_errors(cleaned_input, transcription_data)
        context_clues = self._extract_context_clues(cleaned_input)
        user_intent = self._classify_intent(cleaned_input, context_clues)
        
        # Generate corrections
        corrections = self._generate_corrections(cleaned_input, potential_errors, context_clues)
        
        # Calculate confidence
        confidence = self._calculate_confidence(transcription_data, potential_errors, context_clues)
        
        # Determine error type
        error_type = self._classify_error_type(potential_errors, transcription_data)
        
        return ErrorContext(
            error_type=error_type,
            confidence=confidence,
            suggested_corrections=corrections,
            context_clues=context_clues,
            user_intent=user_intent
        )
    
    def _clean_input(self, text: str) -> str:
        """Clean and normalize input text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Fix common punctuation issues
        text = re.sub(r'\s+([.!?])', r'\1', text)
        text = re.sub(r'([.!?])\s*([a-zA-Z])', r'\1 \2', text)
        
        return text
    
    def _detect_errors(self, text: str, transcription_data: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Detect potential errors in the input"""
        errors = []
        words = text.lower().split()
        
        # Check for homophones
        for i, word in enumerate(words):
            for correct_word, alternatives in self.common_errors["homophones"].items():
                if word in alternatives:
                    errors.append({
                        "type": "homophone",
                        "position": i,
                        "detected": word,
                        "suggested": correct_word,
                        "confidence": 0.7
                    })
        
        # Check for technical term misrecognition
        for correct_term, alternatives in self.common_errors["technical_terms"].items():
            for alt in alternatives:
                if alt in text.lower():
                    errors.append({
                        "type": "technical_term",
                        "detected": alt,
                        "suggested": correct_term,
                        "confidence": 0.8
                    })
        
        # Check transcription confidence if available
        if transcription_data and transcription_data.get("word_details"):
            for word_info in transcription_data["word_details"]:
                if word_info["confidence"] < 0.6:
                    errors.append({
                        "type": "low_confidence",
                        "detected": word_info["word"],
                        "confidence": word_info["confidence"],
                        "time_range": (word_info["start_time"], word_info["end_time"])
                    })
        
        return errors
    
    def _extract_context_clues(self, text: str) -> List[str]:
        """Extract context clues from the input"""
        clues = []
        text_lower = text.lower()
        
        for context_type, patterns in self.context_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    clues.append(context_type)
                    break
        
        return list(set(clues))  # Remove duplicates
    
    def _classify_intent(self, text: str, context_clues: List[str]) -> str:
        """Classify user intent"""
        text_lower = text.lower()
        intent_scores = {}
        
        for intent, config in self.intent_classifiers.items():
            score = 0
            for pattern in config["patterns"]:
                if re.search(pattern, text_lower):
                    score += config["confidence_boost"]
            
            if score > 0:
                intent_scores[intent] = score
        
        # Boost based on context clues
        if "device_control" in context_clues:
            intent_scores["command"] = intent_scores.get("command", 0) + 0.3
        
        if "system_info" in context_clues:
            intent_scores["question"] = intent_scores.get("question", 0) + 0.2
        
        # Return highest scoring intent
        if intent_scores:
            return max(intent_scores.items(), key=lambda x: x[1])[0]
        
        return "general"
    
    def _generate_corrections(self, text: str, errors: List[Dict[str, Any]], context_clues: List[str]) -> List[str]:
        """Generate suggested corrections"""
        corrections = []
        
        if not errors:
            return corrections
        
        # Generate corrections for each error
        for error in errors:
            if error["type"] in ["homophone", "technical_term"]:
                corrected_text = text.replace(error["detected"], error["suggested"])
                corrections.append(corrected_text)
        
        # Generate context-aware alternatives
        if "device_control" in context_clues:
            # Look for command variations
            for command, variations in self.common_errors["command_variations"].items():
                for variation in variations:
                    if variation in text.lower() and command not in text.lower():
                        corrected = re.sub(r'\b' + re.escape(variation) + r'\b', command, text, flags=re.IGNORECASE)
                        corrections.append(corrected)
        
        # Remove duplicates and original text
        corrections = list(set(corrections))
        if text in corrections:
            corrections.remove(text)
        
        return corrections[:3]  # Return top 3 corrections
    
    def _calculate_confidence(self, transcription_data: Dict[str, Any], errors: List[Dict[str, Any]], context_clues: List[str]) -> float:
        """Calculate overall confidence in understanding"""
        base_confidence = 1.0
        
        # Reduce confidence based on transcription quality
        if transcription_data:
            transcription_confidence = transcription_data.get("confidence", 1.0)
            base_confidence *= transcription_confidence
        
        # Reduce confidence based on detected errors
        error_penalty = len(errors) * 0.1
        base_confidence -= error_penalty
        
        # Boost confidence if we have strong context clues
        if len(context_clues) >= 2:
            base_confidence += 0.1
        
        return max(0.1, min(1.0, base_confidence))
    
    def _classify_error_type(self, errors: List[Dict[str, Any]], transcription_data: Dict[str, Any]) -> str:
        """Classify the primary type of error"""
        if not errors:
            return "none"
        
        error_types = [error["type"] for error in errors]
        
        if "low_confidence" in error_types:
            return "transcription_quality"
        elif "homophone" in error_types:
            return "speech_recognition"
        elif "technical_term" in error_types:
            return "domain_specific"
        else:
            return "general"
    
    def generate_clarification_response(self, error_context: ErrorContext) -> str:
        """Generate appropriate clarification response"""
        if error_context.confidence > 0.8:
            return ""  # No clarification needed
        
        if error_context.error_type == "transcription_quality":
            return "I'm having trouble hearing you clearly. Could you please speak a bit louder or slower?"
        
        elif error_context.error_type == "speech_recognition" and error_context.suggested_corrections:
            correction = error_context.suggested_corrections[0]
            return f"I think I heard you correctly, but just to be sure - did you mean: '{correction}'?"
        
        elif error_context.error_type == "domain_specific":
            return "I caught most of that, but I want to make sure I understand the technical details correctly. Could you repeat the specific terms?"
        
        elif error_context.confidence < 0.5:
            return "I want to make sure I help you with exactly what you need. Could you rephrase that for me?"
        
        else:
            intent_clarifications = {
                "command": "I understand you want me to do something. Could you tell me specifically what action you'd like me to take?",
                "question": "I see you're asking about something. Could you clarify what information you're looking for?",
                "request": "I'd be happy to help with that. Could you provide a bit more detail about what you need?"
            }
            
            return intent_clarifications.get(error_context.user_intent, 
                "I want to make sure I understand correctly. Could you tell me more about what you need?")