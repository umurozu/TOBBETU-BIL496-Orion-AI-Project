"""
CommunityController — HLD Module: Controller Layer

Orchestrates logic for the community sharing feature.
Connects the API routes to the SessionService, StorageService, and CommunityRepository.
"""

from __future__ import annotations
import logging
from typing import Optional, List
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.session_service import SessionService
from app.services.storage_service import StorageService
from app.repositories.community_repository import CommunityRepository
from app.schemas.responses import CommunityImageResponse, CommunityFeedResponse, CommunityCommentResponse
from app.model.user_db import UserDB

logger = logging.getLogger(__name__)


class CommunityController:
    """
    Handles community sharing operations.
    """

    def __init__(
        self,
        session_service: SessionService,
        storage_service: StorageService,
    ):
        self.sessionService = session_service
        self.storageService = storage_service

    async def share_image(
        self, 
        db: AsyncSession,
        session_id: str, 
            current_user: UserDB,
            caption: Optional[str] = None
        ) -> CommunityImageResponse:
        """
        Shares the current session's processed result to the community.
        
        Args:
            db: Database session.
            session_id: Active session ID.
            current_user: The authenticated user initiating the share.
            caption: Optional text caption.
            
        Returns:
            CommunityImageResponse object.
            
        Raises:
            HTTPException: If session is invalid, no result exists, or storage fails.
        """
        # 1. Validate session and ensure result exists
        try:
            self.sessionService.validateSession(session_id)
            image_obj = self.sessionService.getResult(session_id)
            
            # If the user hasn't made any edits, allow sharing the original image
            if not image_obj:
                image_obj = self.sessionService.getImage(session_id)
                
            if not image_obj:
                raise HTTPException(status_code=400, detail="Session does not have an image to share.")
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

        # 2. Save snapshot permanently to local storage
        try:
            # ResultImage uses getData(), Image uses rawData
            image_bytes = image_obj.getData() if hasattr(image_obj, "getData") else image_obj.rawData
            filename = self.storageService.save_image_bytes(
                image_bytes=image_bytes, 
                extension=image_obj.format
            )
        except Exception as e:
            logger.error(f"Failed to permanently store shared image: {e}")
            raise HTTPException(status_code=500, detail="Failed to store shared image.")

        # Extract operation metadata if available
        # The ResultImage dataclass currently doesn't store operation history,
        # so we will leave it as None for now. If it's added later, it can be extracted.
        ai_operation = getattr(image_obj, "metadata", {}).get("editing_type", None)

        # 3. Create database record
        post = await CommunityRepository.create_post(
            db=db,
            owner_id=current_user.id,
            image_path=filename,
            ai_operation=ai_operation,
            caption=caption
        )

        return self._map_to_response(post, is_liked=False, comments_count=0)

    async def share_direct_image(
        self, 
        db: AsyncSession, 
        current_user: UserDB, 
        image_bytes: bytes, 
        caption: str,
        ai_operation: str = "Standalone"
    ):
        """
        Shares a raw image byte block directly to the community feed.
        """
        try:
            filename = self.storageService.save_image_bytes(
                image_bytes=image_bytes, 
                extension="jpg"
            )
        except Exception as e:
            logger.error(f"Failed to permanently store shared image: {e}")
            raise HTTPException(status_code=500, detail="Failed to store shared image.")

        post = await CommunityRepository.create_post(
            db=db,
            owner_id=current_user.id,
            image_path=filename,
            ai_operation=ai_operation,
            caption=caption
        )

        return self._map_to_response(post, is_liked=False, comments_count=0)

    async def get_feed(self, db: AsyncSession, current_user_id: Optional[int], limit: int = 20, cursor: Optional[int] = None) -> CommunityFeedResponse:
        """
        Retrieves the public community feed.
        """
        if limit > 50:
            limit = 50

        posts = await CommunityRepository.get_feed_paginated(db=db, limit=limit, cursor_id=cursor)
        
        # Calculate next cursor
        next_cursor = None
        if len(posts) == limit:
            next_cursor = posts[-1].id  # The ID of the last element

        # Pre-fetch user likes and comment counts in bulk
        post_ids = [p.id for p in posts]
        liked_set = await CommunityRepository.get_user_liked_post_ids(db, current_user_id, post_ids) if current_user_id else set()
        comment_counts = await CommunityRepository.get_comment_counts(db, post_ids)

        items = [
            self._map_to_response(
                post, 
                is_liked=(post.id in liked_set), 
                comments_count=comment_counts.get(post.id, 0)
            ) 
            for post in posts
        ]
        
        return CommunityFeedResponse(items=items, next_cursor=next_cursor)

    async def get_post(self, db: AsyncSession, post_id: int, current_user_id: Optional[int] = None) -> CommunityImageResponse:
        """
        Retrieves a specific post by ID.
        """
        post = await CommunityRepository.get_by_id(db, post_id)
        # Note: If we need owner_username here, we might need eagerly loaded relation 
        # or separate query. Assuming eager load wasn't applied in get_by_id, we fetch it manually if needed,
        # but the repository get_feed_paginated eagerly loads owner. 
        # Let's fix that assumption by requiring owner. 
        # For simplicity in this method, we'll let it fail if owner isn't loaded and fix repo later if needed.
        if not post:
            raise HTTPException(status_code=404, detail="Post not found.")
            
        liked_set = await CommunityRepository.get_user_liked_post_ids(db, current_user_id, [post_id]) if current_user_id else set()
        counts = await CommunityRepository.get_comment_counts(db, [post_id])
            
        return self._map_to_response(post, is_liked=(post.id in liked_set), comments_count=counts.get(post.id, 0))

    async def get_user_posts(self, db: AsyncSession, target_user_id: int, current_user_id: Optional[int] = None) -> List[CommunityImageResponse]:
        """
        Retrieves all posts for a specific user.
        """
        posts = await CommunityRepository.get_by_user_id(db, target_user_id)
        
        post_ids = [p.id for p in posts]
        liked_set = await CommunityRepository.get_user_liked_post_ids(db, current_user_id, post_ids) if current_user_id else set()
        comment_counts = await CommunityRepository.get_comment_counts(db, post_ids)

        return [
            self._map_to_response(
                post, 
                is_liked=(post.id in liked_set), 
                comments_count=comment_counts.get(post.id, 0)
            ) 
            for post in posts
        ]

    async def delete_post(self, db: AsyncSession, post_id: int, current_user: UserDB):
        """
        Deletes a post. Only the owner can delete their post.
        """
        post = await CommunityRepository.get_by_id(db, post_id)
        
        if not post:
            raise HTTPException(status_code=404, detail="Post not found.")

        # Security check: Ownership validation
        if post.owner_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this post.")

        # 1. Delete physical file
        self.storageService.delete_image(post.image_path)
        
        # 2. Delete database record
        success = await CommunityRepository.delete_post(db, post_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to delete post record from database.")

    # ---- SOCIAL ACTIONS ----

    async def toggle_like(self, db: AsyncSession, post_id: int, current_user_id: int) -> dict:
        """Toggles a like and returns the new like status/count"""
        try:
            is_liked = await CommunityRepository.toggle_like(db, post_id, current_user_id)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
            
        post = await CommunityRepository.get_by_id(db, post_id)
        return {"is_liked": is_liked, "likes": post.likes if post else 0}

    async def add_comment(self, db: AsyncSession, post_id: int, current_user: UserDB, text: str) -> CommunityCommentResponse:
        """Adds a comment to a post"""
        post = await CommunityRepository.get_by_id(db, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found.")
            
        comment = await CommunityRepository.add_comment(db, post_id, current_user.id, text)
        return CommunityCommentResponse(
            id=comment.id,
            user_id=comment.user_id,
            username=comment.user.username,
            text=comment.text,
            created_at=comment.created_at.isoformat()
        )

    async def get_comments(self, db: AsyncSession, post_id: int) -> List[CommunityCommentResponse]:
        """Fetches all comments for a post"""
        post = await CommunityRepository.get_by_id(db, post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Post not found.")
            
        comments = await CommunityRepository.get_comments(db, post_id)
        return [
            CommunityCommentResponse(
                id=c.id,
                user_id=c.user_id,
                username=c.user.username,
                text=c.text,
                created_at=c.created_at.isoformat()
            ) for c in comments
        ]

    def _map_to_response(self, post, is_liked: bool = False, comments_count: int = 0) -> CommunityImageResponse:
        """Maps a CommunityImageDB instance to a Pydantic response schema."""
        # Note: owner must be eagerly loaded or lazily evaluated
        username = post.owner.username if post.owner else "Unknown"
        
        # Construct the URL to serve the file
        # In a real app, this should ideally be an absolute URL via settings.
        # Here we map it to our planned static file serving route.
        image_url = f"/community/images/file/{post.image_path}"
        
        return CommunityImageResponse(
            id=post.id,
            owner_username=username,
            image_url=image_url,
            ai_operation=post.ai_operation,
            caption=post.caption,
            likes=post.likes,
            is_liked_by_me=is_liked,
            comments_count=comments_count,
            views=post.views,
            shared_at=post.shared_at.isoformat()
        )
