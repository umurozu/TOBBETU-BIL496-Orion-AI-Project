"""
API Response Schemas — LLD §1.2.1
HLD Module: Schema Layer

Standardized API response envelope:
{
    "status": "success | error",
    "message": "descriptive message",
    "data": { ... }
}

Error responses include error_code (LLD §1.2.4).
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, Dict


class APIResponse(BaseModel):
    """
    Standardized API response wrapper.
    All endpoints return this format.
    """
    status: str = Field(..., description="Response status: 'success' or 'error'")
    message: str = Field(..., description="Human-readable response message")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Response payload")
    error_code: Optional[str] = Field(default=None, description="System error code (only for errors)")

    @classmethod
    def success(cls, message: str = "Operation completed successfully", data: Optional[Dict[str, Any]] = None) -> "APIResponse":
        """Creates a success response."""
        return cls(status="success", message=message, data=data)

    @classmethod
    def error(cls, message: str, error_code: str, data: Optional[Dict[str, Any]] = None) -> "APIResponse":
        """Creates an error response."""
        return cls(status="error", message=message, error_code=error_code, data=data)


class UploadResponseData(BaseModel):
    """Data payload for upload response."""
    session_id: str
    image_id: str
    width: int
    height: int
    format: str
    size: int


class ProcessResponseData(BaseModel):
    """Data payload for process response."""
    session_id: str
    result_id: str
    result_image: str  # Base64-encoded result image
    format: str


class StatusResponseData(BaseModel):
    """Data payload for status check response."""
    session_id: str
    status: str  # "active", "processing", "expired"
    has_image: bool
    has_result: bool
    expires_at: Optional[str] = None


# ------------------------------------------------------------------
# Community Response Schemas — LLD §3.2.1, Class: CommunityView
# ------------------------------------------------------------------

class CommunityImageResponse(BaseModel):
    """Data payload for a single community post."""
    id: int
    owner_username: str
    image_url: str
    ai_operation: Optional[str] = None
    caption: Optional[str] = None
    likes: int
    is_liked_by_me: bool = False
    comments_count: int = 0
    views: int
    shared_at: str


class CommunityCommentResponse(BaseModel):
    """Data payload for a single comment on a community post."""
    id: int
    user_id: int
    username: str
    text: str
    created_at: str


class CommunityFeedResponse(BaseModel):
    """Data payload for paginated community feed."""
    items: list[CommunityImageResponse]
    next_cursor: Optional[int] = None
