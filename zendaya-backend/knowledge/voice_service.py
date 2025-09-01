"""
Voice Service - Speech-to-Text and Text-to-Speech
"""
import os
import tempfile
import asyncio
from typing import Optional
import httpx
from google.cloud import speech
from dotenv import load_dotenv

load_dotenv()

class VoiceService:
    def __init__(self):
        self.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")
        self.google_credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.default_voice_id = "mxTlDrtKZzOqgjtBw4hM"  # Zendaya's voice
        self.speech_client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize voice services"""
        # Initialize Google Speech-to-Text
        if self.google_credentials and os.path.exists(self.google_credentials):
            try:
                self.speech_client = speech.SpeechClient()
                print("✅ Google Speech-to-Text initialized")
            except Exception as e:
                print(f"❌ Google Speech-to-Text initialization failed: {e}")
        else:
            print("Warning: Google Speech-to-Text not configured")
        
        # Check ElevenLabs
        if self.elevenlabs_api_key:
            print("✅ ElevenLabs TTS configured")
        else:
            print("Warning: ELEVENLABS_API_KEY not found")
    
    def is_ready(self) -> bool:
        """Check if voice services are ready"""
        return bool(self.elevenlabs_api_key)
    
    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio to text using Google Speech-to-Text"""
        if not self.speech_client:
            raise Exception("Speech-to-Text service not available")
        
        try:
            # Configure recognition
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.WEBM_OPUS,
                sample_rate_hertz=48000,
                language_code="en-US",
                enable_automatic_punctuation=True,
            )
            
            audio = speech.RecognitionAudio(content=audio_data)
            
            # Perform transcription
            response = self.speech_client.recognize(config=config, audio=audio)
            
            # Extract transcript
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript
            
            return transcript.strip()
            
        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")
    
    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> Optional[str]:
        """Synthesize text to speech using ElevenLabs"""
        if not self.elevenlabs_api_key:
            return None
        
        voice_id = voice_id or self.default_voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.elevenlabs_api_key
        }
        
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=data, headers=headers)
                
                if response.status_code == 200:
                    # Save audio to temporary file and return URL
                    # In production, you'd upload to cloud storage
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    temp_file.write(response.content)
                    temp_file.close()
                    
                    # Return file path (in production, return cloud URL)
                    return f"/audio/{os.path.basename(temp_file.name)}"
                else:
                    print(f"ElevenLabs API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Speech synthesis error: {e}")
            return None