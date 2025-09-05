"""
Voice Service - Advanced Speech Processing with Noise Cancellation
"""
import os
import tempfile
import asyncio
import json
import numpy as np
from typing import Optional, Dict, Any, List
import httpx
from google.cloud import speech
from dotenv import load_dotenv
import librosa
import noisereduce as nr
from scipy.io import wavfile
import webrtcvad

load_dotenv()

class AdvancedVoiceService:
    def __init__(self):
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.default_voice_id = "mxTlDrtKZzOqgjtBw4hM"  # Zendaya's voice
        self.speech_client = None
        self.vad = webrtcvad.Vad(3)  # Aggressive VAD for noise filtering
        self._initialize()
    
    def _initialize(self):
        """Initialize advanced voice services"""
        # Initialize Google Speech-to-Text with enhanced settings
        if self.google_credentials and os.path.exists(self.google_credentials):
            try:
                self.speech_client = speech.SpeechClient()
                print("✅ Advanced Google Speech-to-Text initialized")
            except Exception as e:
                print(f"❌ Google Speech-to-Text initialization failed: {e}")
        else:
            print("Warning: Google Speech-to-Text not configured")
        
        # Check ElevenLabs
        if self.elevenlabs_api_key:
            print("✅ ElevenLabs TTS configured with noise-optimized settings")
        else:
            print("Warning: ELEVENLABS_API_KEY not found")
    
    def is_ready(self) -> bool:
        """Check if voice services are ready"""
        return bool(self.elevenlabs_api_key)
    
    async def preprocess_audio(self, audio_data: bytes) -> bytes:
        """Advanced audio preprocessing with noise cancellation"""
        try:
            # Save audio to temporary file for processing
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name
            
            # Load audio with librosa for advanced processing
            audio, sr = librosa.load(temp_path, sr=16000)
            
            # Apply noise reduction
            reduced_noise = nr.reduce_noise(y=audio, sr=sr, prop_decrease=0.8)
            
            # Apply voice activity detection to remove silence
            audio_int16 = (reduced_noise * 32767).astype(np.int16)
            frame_duration = 30  # ms
            frame_size = int(sr * frame_duration / 1000)
            
            # Filter out non-speech segments
            filtered_audio = []
            for i in range(0, len(audio_int16) - frame_size, frame_size):
                frame = audio_int16[i:i + frame_size]
                if self.vad.is_speech(frame.tobytes(), sr):
                    filtered_audio.extend(frame)
            
            # Convert back to bytes
            if filtered_audio:
                filtered_array = np.array(filtered_audio, dtype=np.int16)
                
                # Save processed audio
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as processed_file:
                    wavfile.write(processed_file.name, sr, filtered_array)
                    
                    # Read processed audio as bytes
                    with open(processed_file.name, 'rb') as f:
                        processed_data = f.read()
                    
                    os.unlink(processed_file.name)
                    os.unlink(temp_path)
                    
                    return processed_data
            
            os.unlink(temp_path)
            return audio_data  # Return original if processing fails
            
        except Exception as e:
            print(f"Audio preprocessing error: {e}")
            return audio_data  # Return original audio on error
    
    async def transcribe_with_context(self, audio_data: bytes, context_phrases: List[str] = None) -> Dict[str, Any]:
        """Enhanced transcription with context awareness and error detection"""
        if not self.speech_client:
            raise Exception("Speech-to-Text service not available")
        
        try:
            # Preprocess audio for better quality
            processed_audio = await self.preprocess_audio(audio_data)
            
            # Enhanced recognition config
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-US",
                alternative_language_codes=["en-GB", "en-AU", "en-CA"],
                enable_automatic_punctuation=True,
                enable_word_time_offsets=True,
                enable_word_confidence=True,
                max_alternatives=3,
                profanity_filter=False,
                use_enhanced=True,
                model="latest_long",
                speech_contexts=[
                    speech.SpeechContext(
                        phrases=context_phrases or [
                            "Zendaya", "JARVIS", "artificial intelligence", 
                            "system control", "device management", "smart home"
                        ],
                        boost=20.0
                    )
                ]
            )
            
            audio = speech.RecognitionAudio(content=processed_audio)
            
            # Perform enhanced transcription
            response = self.speech_client.recognize(config=config, audio=audio)
            
            # Process results with confidence analysis
            results = []
            for result in response.results:
                alternative = result.alternatives[0]
                
                # Calculate word-level confidence
                word_confidences = []
                for word_info in alternative.words:
                    word_confidences.append({
                        "word": word_info.word,
                        "confidence": word_info.confidence,
                        "start_time": word_info.start_time.total_seconds(),
                        "end_time": word_info.end_time.total_seconds()
                    })
                
                results.append({
                    "transcript": alternative.transcript,
                    "confidence": alternative.confidence,
                    "words": word_confidences,
                    "alternatives": [alt.transcript for alt in result.alternatives[1:]]
                })
            
            # Determine if clarification is needed
            needs_clarification = self._analyze_transcription_quality(results)
            
            return {
                "transcript": results[0]["transcript"] if results else "",
                "confidence": results[0]["confidence"] if results else 0.0,
                "needs_clarification": needs_clarification,
                "alternatives": results[0]["alternatives"] if results else [],
                "word_details": results[0]["words"] if results else [],
                "quality_score": self._calculate_quality_score(results)
            }
            
        except Exception as e:
            raise Exception(f"Enhanced transcription failed: {str(e)}")
    
    def _analyze_transcription_quality(self, results: List[Dict]) -> bool:
        """Analyze if transcription needs clarification"""
        if not results:
            return True
        
        primary_result = results[0]
        
        # Check overall confidence
        if primary_result["confidence"] < 0.7:
            return True
        
        # Check for low-confidence words
        low_confidence_words = [
            word for word in primary_result["words"] 
            if word["confidence"] < 0.6
        ]
        
        if len(low_confidence_words) > len(primary_result["words"]) * 0.3:
            return True
        
        # Check transcript length (too short might indicate incomplete capture)
        if len(primary_result["transcript"].split()) < 3:
            return True
        
        return False
    
    def _calculate_quality_score(self, results: List[Dict]) -> float:
        """Calculate overall transcription quality score"""
        if not results:
            return 0.0
        
        primary_result = results[0]
        
        # Base score from confidence
        score = primary_result["confidence"]
        
        # Adjust for word-level confidence consistency
        word_confidences = [word["confidence"] for word in primary_result["words"]]
        if word_confidences:
            confidence_std = np.std(word_confidences)
            score *= (1 - min(confidence_std, 0.3))  # Penalize high variance
        
        # Adjust for transcript completeness
        word_count = len(primary_result["transcript"].split())
        if word_count >= 5:
            score *= 1.1  # Bonus for complete sentences
        elif word_count < 3:
            score *= 0.8  # Penalty for fragments
        
        return min(score, 1.0)
    
    async def synthesize_with_emotion(self, text: str, emotion: str = "confident", voice_id: Optional[str] = None) -> Optional[str]:
        """Enhanced speech synthesis with emotional intelligence"""
        if not self.elevenlabs_api_key:
            return None
        
        voice_id = voice_id or self.default_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        # Emotional voice settings
        emotion_settings = {
            "confident": {"stability": 0.7, "similarity_boost": 0.8, "style": 0.3},
            "helpful": {"stability": 0.6, "similarity_boost": 0.75, "style": 0.2},
            "concerned": {"stability": 0.5, "similarity_boost": 0.7, "style": 0.4},
            "excited": {"stability": 0.4, "similarity_boost": 0.8, "style": 0.6},
            "calm": {"stability": 0.8, "similarity_boost": 0.7, "style": 0.1}
        }
        
        settings = emotion_settings.get(emotion, emotion_settings["confident"])
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.elevenlabs_api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                **settings,
                "use_speaker_boost": True
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=headers)
                
                if response.status_code == 200:
                    # Save audio to temporary file
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    temp_file.write(response.content)
                    temp_file.close()
                    
                    # Return file path (in production, return cloud URL)
                    return f"/audio/{os.path.basename(temp_file.name)}"
                else:
                    print(f"ElevenLabs API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Enhanced speech synthesis error: {e}")
            return None
    
    async def generate_clarification_question(self, transcription_result: Dict[str, Any]) -> str:
        """Generate intelligent clarification questions"""
        if not transcription_result.get("needs_clarification"):
            return ""
        
        transcript = transcription_result.get("transcript", "")
        confidence = transcription_result.get("confidence", 0.0)
        alternatives = transcription_result.get("alternatives", [])
        
        if confidence < 0.3:
            return "I'm having trouble hearing you clearly. Could you please repeat that?"
        
        if confidence < 0.6 and alternatives:
            return f"I heard '{transcript}', but I'm not entirely certain. Did you mean that, or perhaps '{alternatives[0]}'?"
        
        low_confidence_words = [
            word["word"] for word in transcription_result.get("word_details", [])
            if word["confidence"] < 0.5
        ]
        
        if low_confidence_words:
            return f"I caught most of that, but I'm unsure about '{' '.join(low_confidence_words)}'. Could you clarify?"
        
        return "I want to make sure I understand correctly. Could you rephrase that?"