"""
Custom Exception Classes — LLD §1.2.4
HLD Module: Error Handling

Error categories:
- ValidationError: invalid image format, size exceeded
- ProcessingError: model inference failure
- SystemError: internal server issues

Error responses follow:
{
    "status": "error",
    "message": "Human-readable description",
    "error_code": "SYSTEM_DEFINED_CODE"
}

Errors MUST NOT expose internal stack traces or model implementation details.
"""


class InvisioBaseError(Exception):
    """Base exception for all Invisio errors."""

    def __init__(self, message: str, error_code: str, status_code: int = 500):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(InvisioBaseError):
    """Raised for input validation failures (format, size, integrity)."""

    def __init__(self, message: str, error_code: str = "VALIDATION_ERROR"):
        super().__init__(message=message, error_code=error_code, status_code=400)


class ImageFormatError(ValidationError):
    """Raised when image format is not allowed."""

    def __init__(self, message: str = "Unsupported image format"):
        super().__init__(message=message, error_code="INVALID_FORMAT")


class ImageSizeError(ValidationError):
    """Raised when image exceeds maximum file size."""

    def __init__(self, message: str = "File size exceeds maximum limit"):
        super().__init__(message=message, error_code="FILE_TOO_LARGE")


class ImageIntegrityError(ValidationError):
    """Raised when image file is corrupted or invalid."""

    def __init__(self, message: str = "Image file is corrupted or unreadable"):
        super().__init__(message=message, error_code="FILE_CORRUPTED")


class NSFWContentError(ValidationError):
    """Raised when NSFW content is detected."""

    def __init__(self, message: str = "NSFW content detected. This image cannot be processed for safety reasons."):
        super().__init__(message=message, error_code="NSFW_DETECTED")


class ProcessingError(InvisioBaseError):
    """Raised when AI model inference or processing fails."""

    def __init__(self, message: str, error_code: str = "PROCESSING_ERROR"):
        super().__init__(message=message, error_code=error_code, status_code=500)


class ModelNotFoundError(ProcessingError):
    """Raised when requested AI model type is not registered."""

    def __init__(self, message: str = "Requested editing model is not available"):
        super().__init__(message=message, error_code="MODEL_NOT_FOUND")


class ModelNotLoadedError(ProcessingError):
    """Raised when AI model weights are not loaded."""

    def __init__(self, message: str = "AI model is not initialized"):
        super().__init__(message=message, error_code="MODEL_NOT_LOADED")


class SessionError(InvisioBaseError):
    """Raised for session-related failures."""

    def __init__(self, message: str, error_code: str = "SESSION_ERROR"):
        super().__init__(message=message, error_code=error_code, status_code=400)


class SessionNotFoundError(SessionError):
    """Raised when session ID is invalid or not found."""

    def __init__(self, message: str = "Session not found"):
        super().__init__(message=message, error_code="SESSION_NOT_FOUND")


class SessionExpiredError(SessionError):
    """Raised when session has expired."""

    def __init__(self, message: str = "Session has expired"):
        super().__init__(message=message, error_code="SESSION_EXPIRED")


class RateLimitError(InvisioBaseError):
    """Raised when rate limit is exceeded."""

    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(message=message, error_code="RATE_LIMIT_EXCEEDED", status_code=429)


class UnauthorizedError(InvisioBaseError):
    """Raised for unauthorized access attempts."""

    def __init__(self, message: str = "Unauthorized access"):
        super().__init__(message=message, error_code="UNAUTHORIZED", status_code=401)
