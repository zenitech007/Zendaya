from fastapi import Request, status
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ErrorAnalysis:
    error_type: str
    description: str
    suggested_fix: str
    confidence: float

class ErrorUnderstandingEngine:
    """Engine for analyzing and understanding various types of errors"""
    
    def __init__(self):
        self.error_patterns: Dict[str, str] = {}
        self._initialize_patterns()
    
    def _initialize_patterns(self):
        """Initialize known error patterns and their descriptions"""
        self.error_patterns = {
            "ImportError": "Module or package not found",
            "TypeError": "Operation or function applied to inappropriate type",
            "ValueError": "Operation or function received argument with right type but inappropriate value",
            # Add more patterns as needed
        }
    
    async def analyze_error(self, error_message: str) -> Optional[ErrorAnalysis]:
        """
        Analyze an error message and provide understanding and potential fixes
        
        Args:
            error_message: The error message to analyze
            
        Returns:
            ErrorAnalysis object containing the analysis or None if analysis fails
        """
        try:
            # Basic error type detection
            error_type = next(
                (key for key in self.error_patterns.keys() if key in error_message), 
                "Unknown"
            )
            
            return ErrorAnalysis(
                error_type=error_type,
                description=self.error_patterns.get(error_type, "Unknown error type"),
                suggested_fix="Please check documentation or consult developer",
                confidence=0.7 if error_type != "Unknown" else 0.3
            )
            
        except Exception as e:
            logger.error(f"Error during error analysis: {str(e)}")
            return None

async def enhanced_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Enhanced error handler with structured logging"""
    request_id = getattr(request.state, "request_id", "unknown")
    error_context = {
        "request_id": request_id,
        "path": request.url.path,
        "method": request.method,
        "error": str(exc)
    }
    
    logger.error("Request failed", extra=error_context)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
            "type": exc.__class__.__name__
        }
    )