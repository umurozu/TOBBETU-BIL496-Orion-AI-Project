"""
Security Middleware — LLD §1.2.5
HLD Module: Middleware Layer — Security

MIME validation and security header enforcement.
"""

import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Security middleware that:
    - Adds security headers to all responses
    - Validates content type for upload endpoints
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # MIME validation for upload endpoint
        if request.url.path == "/upload" and request.method == "POST":
            content_type = request.headers.get("content-type", "")
            if "multipart/form-data" not in content_type:
                from fastapi.responses import JSONResponse
                from app.schemas.responses import APIResponse
                response_data = APIResponse.error(
                    message="Invalid content type. Expected multipart/form-data.",
                    error_code="INVALID_CONTENT_TYPE",
                )
                return JSONResponse(
                    status_code=400,
                    content=response_data.model_dump(),
                )

        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"

        return response
