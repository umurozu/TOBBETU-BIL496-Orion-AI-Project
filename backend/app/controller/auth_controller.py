"""
Authentication Controller — LLD §2.1.1
HLD Module: Controller Layer — Auth

Handles authentication-related HTTP logic:
    POST /auth/register  → Create new user account
    POST /auth/login     → Authenticate and issue tokens
    POST /auth/refresh   → Refresh access token
    GET  /auth/me        → Get current user profile
"""

import logging
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.utils.exceptions import UnauthorizedError

logger = logging.getLogger(__name__)


class AuthController:
    """
    Thin controller — delegates to AuthService for business logic.
    Each method receives db session from route-level dependency injection.
    """

    # ---- Register ----
    async def register(
        self, db: AsyncSession, email: str, username: str, password: str, consent_given: bool = False
    ) -> Dict[str, Any]:
        """
        Creates a new user and returns JWT tokens.
        """
        user = await AuthService.register(db, email, username, password, consent_given)
        tokens = AuthService.generate_tokens(user)
        logger.info("User registered: id=%s email=%s", user.id, user.email)
        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
            },
            **tokens,
        }

    # ---- Login ----
    async def login(
        self, db: AsyncSession, email: str, password: str
    ) -> Dict[str, Any]:
        """
        Authenticates credentials and returns JWT tokens.
        Raises UnauthorizedError (→ 401) on failure.
        """
        user = await AuthService.authenticate(db, email, password)
        tokens = AuthService.generate_tokens(user)
        logger.info("User logged in: id=%s email=%s", user.id, user.email)
        return tokens

    # ---- Refresh Token ----
    async def refresh(
        self, db: AsyncSession, refresh_token: str
    ) -> Dict[str, Any]:
        """
        Validates refresh token and issues a new access token pair.
        """
        payload = AuthService.decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type — expected refresh token")

        user_id = payload.get("sub")
        if user_id is None:
            raise UnauthorizedError("Token payload is missing subject")

        user = await UserRepository.get_by_id(db, int(user_id))
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or deactivated")

        tokens = AuthService.generate_tokens(user)
        logger.info("Tokens refreshed for user id=%s", user.id)
        return tokens

    # ---- Unregister ----
    async def unregister(self, db: AsyncSession, user_id: int) -> Dict[str, Any]:
        """
        Deletes the current user's account (Hard Delete).
        """
        await AuthService.delete_account(db, user_id)
        logger.info("User deleted account: id=%s", user_id)
        return {"status": "deleted", "message": "Account successfully removed."}

    # ---- Current User ----
    async def me(self, db: AsyncSession, token: str) -> Dict[str, Any]:
        """
        Returns the profile of the currently authenticated user.
        """
        user = await AuthService.get_current_user(db, token)
        return {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }
