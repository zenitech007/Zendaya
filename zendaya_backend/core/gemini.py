import os
import logging
from typing import Optional
import google.generativeai as genai
from zendaya_backend.core.config import settings

logger = logging.getLogger(__name__)

class GeminiService:
    """
    A service for interacting with the Google Gemini Pro model using the official
    google-generativeai library.
    """
    def __init__(self):
        """
        Initializes the Gemini Service, configuring the API key and setting up the model.
        """
        self.api_key = settings.gemini_api_key
        self.model = self._initialize_model()

    def _initialize_model(self) -> Optional[genai.GenerativeModel]:
        """
        Configures the genai library with the API key and initializes the GenerativeModel.
        """
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set. GeminiService will be disabled.")
            return None
        try:
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel('gemini-pro')
            logger.info("Gemini model 'gemini-pro' initialized successfully.")
            return model
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {str(e)}", exc_info=True)
            return None

    async def generate_response(self, prompt: str) -> Optional[str]:
        """
        Asynchronously generates a response from the Gemini model for a given prompt.

        Args:
            prompt: The text prompt to send to the model.

        Returns:
            The generated text response, or None if an error occurs or the model
            is not initialized.
        """
        if not self.model:
            logger.error("Cannot generate response because Gemini model is not initialized.")
            return "The Gemini AI service is not configured."
            
        try:
            # The official library's async method is generate_content_async
            response = await self.model.generate_content_async(prompt)
            # Access the text directly from the response part
            return response.parts[0].text
        except Exception as e:
            logger.error(f"Error generating response from Gemini: {str(e)}", exc_info=True)
            return "I'm sorry, I encountered an issue while processing your request."

    def is_ready(self) -> bool:
        """
        Checks if the service is properly initialized and ready to use.
        """
        return self.model is not None
