"""
Authentication Service — Business Logic Layer
HLD Module: Service Layer — Auth

Handles:
    - Password hashing / verification (bcrypt via passlib)
    - JWT access & refresh token creation / validation
    - User registration & login orchestration
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.model.user_db import UserDB
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import UnauthorizedError, ValidationError

logger = logging.getLogger(__name__)

# ---- Password hashing context ----
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Stateless authentication service.
    All methods are static — no per-instance state.
    """

    # ========== Password Utilities ==========

    @staticmethod
    def hash_password(plain: str) -> str:
        """Returns bcrypt hash of the given plaintext password."""
        return pwd_context.hash(plain)

    @staticmethod
    def verify_password(plain: str, hashed: str) -> bool:
        """Verifies plaintext against bcrypt hash."""
        return pwd_context.verify(plain, hashed)

    # ========== JWT Token Utilities ==========

    @staticmethod
    def create_access_token(
        data: Dict[str, Any],
        expires_delta: Optional[timedelta] = None,
    ) -> str:
        """
        Creates a short-lived JWT access token.

        The payload always includes:
            sub  — user identifier (str)
            exp  — expiration timestamp
            type — "access"
        """
        settings = get_settings()
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + (
            expires_delta
            or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Creates a long-lived JWT refresh token."""
        settings = get_settings()
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

    @staticmethod
    def decode_token(token: str) -> Dict[str, Any]:
        """
        Decodes and validates a JWT token.
        Raises UnauthorizedError on any failure.
        """
        settings = get_settings()
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except JWTError as exc:
            logger.warning("JWT decode failed: %s", exc)
            raise UnauthorizedError("Invalid or expired token")

    # ========== User Operations ==========

    @staticmethod
    async def register(
        db: AsyncSession,
        email: str,
        username: str,
        password: str,
        consent_given: bool = False,
    ) -> UserDB:
        """
        Registers a new user.
        Raises ValidationError if email/username taken or consent missing.
        """
        if not consent_given:
            raise ValidationError("You must agree to the Terms and Privacy Policy", error_code="CONSENT_REQUIRED")
            
        if await UserRepository.get_by_email(db, email):
            raise ValidationError("Email is already registered", error_code="EMAIL_TAKEN")
        if await UserRepository.get_by_username(db, username):
            raise ValidationError("Username is already taken", error_code="USERNAME_TAKEN")

        hashed = AuthService.hash_password(password)
        user = await UserRepository.create(
            db, email=email, username=username, hashed_password=hashed,
            consent_at=datetime.now(timezone.utc)
        )
        return user

    @staticmethod
    async def delete_account(db: AsyncSession, user_id: int) -> None:
        """Deletes user account (GDPR Hard Delete)."""
        success = await UserRepository.delete(db, user_id)
        if not success:
            raise ValidationError("User not found or already deleted", error_code="USER_NOT_FOUND")

    @staticmethod
    async def authenticate(
        db: AsyncSession,
        email: str,
        password: str,
    ) -> UserDB:
        """
        Validates credentials and returns the user.
        Raises UnauthorizedError on failure.
        """
        user = await UserRepository.get_by_email(db, email)
        if user is None or not AuthService.verify_password(
            password, user.hashed_password
        ):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated")
        return user

    @staticmethod
    def generate_tokens(user: UserDB) -> Dict[str, str]:
        """
        Returns a dict with access_token and refresh_token for the given user.
        """
        payload = {"sub": str(user.id), "username": user.username}
        return {
            "access_token": AuthService.create_access_token(payload),
            "refresh_token": AuthService.create_refresh_token(payload),
            "token_type": "bearer",
        }

    @staticmethod
    async def get_current_user(db: AsyncSession, token: str) -> UserDB:
        """
        Extracts user from a valid access token.
        Raises UnauthorizedError if token is invalid or user doesn't exist.
        """
        payload = AuthService.decode_token(token)
        if payload.get("type") != "access":
            raise UnauthorizedError("Invalid token type")
        user_id = payload.get("sub")
        if user_id is None:
            raise UnauthorizedError("Token payload is missing subject")
        user = await UserRepository.get_by_id(db, int(user_id))
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or deactivated")
        return user
