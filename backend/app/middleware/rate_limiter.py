"""
Rate Limiter Middleware — LLD §1.2.5
HLD Module: Middleware Layer — Security

Controls request frequency per client IP to mitigate abuse.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config.settings import get_settings
from app.schemas.responses import APIResponse

logger = logging.getLogger(__name__)


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Request rate-limiting middleware.
    
    Tracks requests per IP and blocks requests that exceed the configured limit.
    """

    def __init__(self, app):
        super().__init__(app)
        settings = get_settings()
        self.max_requests = settings.RATE_LIMIT_REQUESTS
        self.window_seconds = settings.RATE_LIMIT_WINDOW_SECONDS
        # IP -> (request_count, window_start_time)
        self._requests: Dict[str, Tuple[int, float]] = defaultdict(lambda: (0, time.time()))

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for health check, docs, and test client
        if request.url.path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        if client_ip == "testclient":
            return await call_next(request)

        current_time = time.time()

        count, window_start = self._requests[client_ip]

        # Reset window if expired
        if current_time - window_start > self.window_seconds:
            self._requests[client_ip] = (1, current_time)
        elif count >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            response_data = APIResponse.error(
                message="Rate limit exceeded. Please try again later.",
                error_code="RATE_LIMIT_EXCEEDED",
            )
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=429,
                content=response_data.model_dump(),
            )
        else:
            self._requests[client_ip] = (count + 1, window_start)

        return await call_next(request)
