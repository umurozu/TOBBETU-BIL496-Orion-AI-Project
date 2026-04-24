"""
Community Repository — Data Access Layer (Repository Pattern)
HLD Module: Model Layer — Persistence

Encapsulates all database queries related to the CommunityImageDB entity.
"""

import logging
from typing import Optional, List, Tuple

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.model.community_image_db import CommunityImageDB, CommunityLikeDB, CommunityCommentDB
from app.model.user_db import UserDB

logger = logging.getLogger(__name__)


class CommunityRepository:
    """
    Repository for CommunityImageDB operations.
    """

    # ---- READ ----

    @staticmethod
    async def get_by_id(db: AsyncSession, post_id: int) -> Optional[CommunityImageDB]:
        """Fetch a single post by its ID."""
        result = await db.execute(
            select(CommunityImageDB)
            .options(joinedload(CommunityImageDB.owner))
            .where(CommunityImageDB.id == post_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_feed_paginated(
        db: AsyncSession, 
        limit: int = 20, 
        cursor_id: Optional[int] = None
    ) -> List[CommunityImageDB]:
        """
        Fetch the public feed ordered by shared_at DESC.
        Uses cursor-based pagination (last seen post_id) for scalability.
        Eagerly loads the owner relationship to prevent N+1 queries.
        """
        stmt = select(CommunityImageDB).options(joinedload(CommunityImageDB.owner))
        
        if cursor_id:
            # For descending order, we want items older (smaller ID) than the cursor
            stmt = stmt.where(CommunityImageDB.id < cursor_id)
            
        stmt = stmt.order_by(desc(CommunityImageDB.id)).limit(limit)
        
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> List[CommunityImageDB]:
        """Fetch all posts shared by a specific user."""
        stmt = (
            select(CommunityImageDB)
            .options(joinedload(CommunityImageDB.owner))
            .where(CommunityImageDB.owner_id == user_id)
            .order_by(desc(CommunityImageDB.id))
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    # ---- CREATE ----

    @staticmethod
    async def create_post(
        db: AsyncSession,
        owner_id: int,
        image_path: str,
        ai_operation: Optional[str] = None,
        caption: Optional[str] = None,
    ) -> CommunityImageDB:
        """Persist a new community post."""
        post = CommunityImageDB(
            owner_id=owner_id,
            image_path=image_path,
            ai_operation=ai_operation,
            caption=caption,
        )
        db.add(post)
        await db.flush()
        
        # Fresh retrieval with eager loading immediately after create to populate .owner automatically 
        # allowing instantaneous response mapping formatting without error.
        result = await db.execute(
            select(CommunityImageDB)
            .options(joinedload(CommunityImageDB.owner))
            .where(CommunityImageDB.id == post.id)
        )
        post_with_owner = result.scalar_one()

        logger.info(f"Created community post id={post_with_owner.id} owner={owner_id}")
        return post_with_owner

    # ---- DELETE ----

    @staticmethod
    async def delete_post(db: AsyncSession, post_id: int) -> bool:
        """
        Hard-deletes a post. 
        Note: The actual file deletion should happen in the controller via StorageService.
        """
        post = await CommunityRepository.get_by_id(db, post_id)
        if post:
            await db.delete(post)
            await db.flush()
            logger.info(f"Deleted community post id={post_id}")
            return True
        return False

    # ---- SOCIAL FEATURES ----

    @staticmethod
    async def toggle_like(db: AsyncSession, post_id: int, user_id: int) -> bool:
        """
        Toggles a like for a user on a post.
        Returns:
            True if the post is now liked.
            False if the post is now unliked.
        """
        stmt = select(CommunityLikeDB).where(
            (CommunityLikeDB.post_id == post_id) & (CommunityLikeDB.user_id == user_id)
        )
        result = await db.execute(stmt)
        existing_like = result.scalar_one_or_none()

        post = await CommunityRepository.get_by_id(db, post_id)
        if not post:
            raise ValueError("Post not found")

        is_liked = False
        if existing_like:
            await db.delete(existing_like)
            post.likes = max(0, post.likes - 1)
        else:
            new_like = CommunityLikeDB(post_id=post_id, user_id=user_id)
            db.add(new_like)
            post.likes += 1
            is_liked = True

        await db.flush()
        return is_liked

    @staticmethod
    async def add_comment(db: AsyncSession, post_id: int, user_id: int, text: str) -> CommunityCommentDB:
        """Adds a comment to a post."""
        comment = CommunityCommentDB(post_id=post_id, user_id=user_id, text=text)
        db.add(comment)
        await db.flush()

        # Eager load the user relation to return instantly
        result = await db.execute(
            select(CommunityCommentDB)
            .options(joinedload(CommunityCommentDB.user))
            .where(CommunityCommentDB.id == comment.id)
        )
        return result.scalar_one()

    @staticmethod
    async def get_comments(db: AsyncSession, post_id: int) -> List[CommunityCommentDB]:
        """Fetches all comments for a given post."""
        stmt = (
            select(CommunityCommentDB)
            .options(joinedload(CommunityCommentDB.user))
            .where(CommunityCommentDB.post_id == post_id)
            .order_by(CommunityCommentDB.created_at)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_user_liked_post_ids(db: AsyncSession, user_id: int, post_ids: List[int]) -> set[int]:
        """Returns a set of post IDs from the requested list that the user has liked."""
        if not post_ids:
            return set()
        stmt = select(CommunityLikeDB.post_id).where(
            (CommunityLikeDB.user_id == user_id) & (CommunityLikeDB.post_id.in_(post_ids))
        )
        result = await db.execute(stmt)
        return set(result.scalars().all())

    @staticmethod
    async def get_comment_counts(db: AsyncSession, post_ids: List[int]) -> dict[int, int]:
        """Returns a dictionary mapping post_id to its total comment count."""
        if not post_ids:
            return {}
        from sqlalchemy import func
        stmt = (
            select(CommunityCommentDB.post_id, func.count(CommunityCommentDB.id))
            .where(CommunityCommentDB.post_id.in_(post_ids))
            .group_by(CommunityCommentDB.post_id)
        )
        result = await db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}
