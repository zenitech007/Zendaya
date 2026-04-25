"""
Custom exception handlers for the Zendaya AI Backend
"""
from typing import Dict, Any
from datetime import datetime
import traceback
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import logging

logger = logging.getLogger(__name__)


class ZendayaException(Exception):
    """Base exception for Zendaya AI system"""
    def __init__(self, message: str, error_code: str = "ZENDAYA_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class AIServiceException(ZendayaException):
    """Exception for AI service errors"""
    def __init__(self, message: str, service: str):
        self.service = service
        super().__init__(message, f"AI_SERVICE_ERROR_{service.upper()}")


class DeviceControlException(ZendayaException):
    """Exception for device control errors"""
    def __init__(self, message: str, device_type: str):
        self.device_type = device_type
        super().__init__(message, f"DEVICE_CONTROL_ERROR_{device_type.upper()}")


class VoiceProcessingException(ZendayaException):
    """Exception for voice processing errors"""
    def __init__(self, message: str, stage: str):
        self.stage = stage
        super().__init__(message, f"VOICE_PROCESSING_ERROR_{stage.upper()}")


def create_error_response(
    status_code: int,
    message: str,
    error_code: str = "UNKNOWN_ERROR",
    details: Dict[str, Any] = None
) -> JSONResponse:
    """Create standardized error response"""
    error_response = {
        "error": {
            "code": error_code,
            "message": message,
            "status_code": status_code,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    }
    
    if details:
        error_response["error"]["details"] = details
    
    return JSONResponse(
        status_code=status_code,
        content=error_response
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code=f"HTTP_ERROR_{exc.status_code}",
        details={"path": str(request.url)}
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle validation errors"""
    logger.error(f"Validation Error: {exc.errors()}")
    
    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        message="Validation error in request data",
        error_code="VALIDATION_ERROR",
        details={
            "path": str(request.url),
            "errors": exc.errors()
        }
    )


async def zendaya_exception_handler(request: Request, exc: ZendayaException) -> JSONResponse:
    """Handle custom Zendaya exceptions"""
    logger.error(f"Zendaya Exception: {exc.error_code} - {exc.message}")
    
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message=exc.message,
        error_code=exc.error_code,
        details={"path": str(request.url)}
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle general exceptions with full traceback logging"""
    # Log full exception details with traceback
    error_traceback = traceback.format_exc()
    logger.error(
        f"Unexpected error occurred:\n"
        f"Path: {request.url}\n"
        f"Method: {request.method}\n"
        f"Exception Type: {type(exc).__name__}\n"
        f"Exception Message: {str(exc)}\n"
        f"Traceback:\n{error_traceback}",
        exc_info=True
    )

    # In debug mode, include traceback in response
    details = {"path": str(request.url), "method": request.method}

    from zendaya_backend.core.config import settings
    if settings.debug:
        details["exception_type"] = type(exc).__name__
        details["traceback"] = error_traceback.split("\n")

    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        message="An unexpected error occurred. Please try again later.",
        error_code="INTERNAL_SERVER_ERROR",
        details=details
    )
