"""
API Request Schemas — LLD §1.2.1, §1.2.3
HLD Module: Schema Layer

Pydantic models for API request validation.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


class ProcessRequest(BaseModel):
    """Request body for POST /process endpoint."""
    session_id: str = Field(..., description="Active session identifier")
    editing_type: str = Field(..., description="Editing operation type (e.g., 'enhancement', 'style_transfer')")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Operation-specific parameters")


class RefinementRequest(BaseModel):
    """Request body for mask refinement."""
    session_id: str = Field(..., description="Active session identifier")
    mask_data: Optional[str] = Field(None, description="Base64-encoded mask data")
    brush_size: int = Field(default=10, ge=1, le=100)
    brush_strength: float = Field(default=1.0, ge=0.0, le=1.0)


class DownloadRequest(BaseModel):
    """Request body for image download."""
    session_id: str = Field(..., description="Active session identifier")
    format: str = Field(default="png", description="Export format (jpeg, png, webp)")
