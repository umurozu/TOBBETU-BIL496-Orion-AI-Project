"""
Authentication Schemas — Request & Response Models
HLD Module: Schema Layer — Auth

Pydantic models for authentication API endpoints.
"""

from pydantic import BaseModel, Field, EmailStr


# ---- Request Schemas ----

class RegisterRequest(BaseModel):
    """POST /auth/register request body."""
    email: EmailStr = Field(..., description="User email address")
    username: str = Field(
        ..., min_length=3, max_length=50, description="Unique username"
    )
    password: str = Field(
        ..., min_length=6, max_length=128, description="User password (min 6 chars)"
    )
    consent_given: bool = Field(False, description="Whether the user agreed to Terms and Privacy Policy")


class LoginRequest(BaseModel):
    """POST /auth/login request body."""
    email: EmailStr = Field(..., description="Registered email address")
    password: str = Field(..., description="User password")


class RefreshRequest(BaseModel):
    """POST /auth/refresh request body."""
    refresh_token: str = Field(..., description="Valid refresh token")


# ---- Response Schemas ----

class TokenResponse(BaseModel):
    """Token pair returned on login / register / refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    """Public user profile data."""
    id: int
    email: str
    username: str
    is_active: bool
    created_at: str  # ISO-8601

    class Config:
        from_attributes = True
