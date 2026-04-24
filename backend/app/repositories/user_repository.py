"""
User Repository — Data Access Layer (Repository Pattern)
HLD Module: Model Layer — Persistence

Encapsulates all database queries related to the User entity.
No business logic — only CRUD operations.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.user_db import UserDB

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for User persistence operations.

    All methods receive an AsyncSession, keeping the repository
    stateless and easily testable.
    """

    # ---- READ ----

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: int) -> Optional[UserDB]:
        """Fetch a user by primary key."""
        result = await db.execute(select(UserDB).where(UserDB.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[UserDB]:
        """Fetch a user by email address."""
        result = await db.execute(
            select(UserDB).where(UserDB.email == email.lower())
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_username(db: AsyncSession, username: str) -> Optional[UserDB]:
        """Fetch a user by username."""
        result = await db.execute(
            select(UserDB).where(UserDB.username == username)
        )
        return result.scalar_one_or_none()

    # ---- CREATE ----

    @staticmethod
    async def create(
        db: AsyncSession,
        email: str,
        username: str,
        hashed_password: str,
        consent_at: Optional[datetime] = None,
    ) -> UserDB:
        """
        Persist a new user row. Caller is responsible for hashing
        the password before calling this method.
        """
        user = UserDB(
            email=email.lower(),
            username=username,
            hashed_password=hashed_password,
            consent_at=consent_at,
        )
        db.add(user)
        await db.flush()   # assigns id without committing
        await db.refresh(user)
        logger.info("Created user id=%s email=%s", user.id, user.email)
        return user

    @staticmethod
    async def delete(db: AsyncSession, user_id: int) -> bool:
        """Hard-delete: permanently removes the user."""
        user = await UserRepository.get_by_id(db, user_id)
        if user is None:
            return False
        await db.delete(user)
        await db.flush()
        return True

    # ---- UPDATE ----

    @staticmethod
    async def deactivate(db: AsyncSession, user_id: int) -> bool:
        """Soft-delete: marks user as inactive."""
        user = await UserRepository.get_by_id(db, user_id)
        if user is None:
            return False
        user.is_active = False
        await db.flush()
        return True

    @staticmethod
    async def update_password(
        db: AsyncSession, user_id: int, new_hashed_password: str
    ) -> bool:
        """Updates user's hashed password."""
        user = await UserRepository.get_by_id(db, user_id)
        if user is None:
            return False
        user.hashed_password = new_hashed_password
        await db.flush()
        return True
