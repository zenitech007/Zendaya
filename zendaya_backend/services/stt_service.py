# zendaya_backend/services/stt_service.py
import whisper
import io
import asyncio
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class STTService:
    """
    A service for transcribing audio using OpenAI's Whisper model.
    """
    def __init__(self, model_name: str = "base.en"):
        """
        Initializes the STTService and loads the Whisper model.

        Args:
            model_name (str): The name of the Whisper model to load.
                              Options: "tiny.en", "base.en", "small.en", "medium.en"
                              (Use ".en" models for English-only, they are faster)
        """
        self.model = None
        self.model_name = model_name
        try:
            logger.info(f"Loading Whisper STT model '{self.model_name}'...")
            # Load the model. This will download it the first time it's run.
            self.model = whisper.load_model(self.model_name)
            logger.info("✅ Whisper STT model loaded successfully.")
        except Exception as e:
            logger.error(f"🚨 Failed to load Whisper model: {e}")
            logger.error("Please ensure you have run 'pip install openai-whisper' and have ffmpeg installed.")

    async def transcribe(self, audio_bytes: bytes) -> Optional[str]:
        """
        Transcribes the given audio bytes into text.

        Args:
            audio_bytes (bytes): The raw audio data.

        Returns:
            Optional[str]: The transcribed text, or None if transcription fails.
        """
        if not self.model:
            logger.error("Cannot transcribe: Whisper model is not loaded.")
            return None

        try:
            # Whisper works with file-like objects. We use an in-memory
            # BytesIO object. Naming it ".wav" helps Whisper process it.
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "stream.wav"

            # Run the blocking transcription in a separate thread
            result = await asyncio.to_thread(
                self.model.transcribe,
                audio_file,
                fp16=False # Set to True if you have a GPU and CUDA installed
            )
            
            transcribed_text = result.get("text", "").strip()
            logger.info(f"Transcription result: '{transcribed_text}'")
            return transcribed_text

        except Exception as e:
            logger.error(f"Error during audio transcription: {e}")
            return None