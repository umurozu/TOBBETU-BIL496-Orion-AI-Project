"""
Community Post ORM Model — SQLAlchemy Declarative Model
HLD Module: Model Layer — Data Access

Maps to the 'community_posts' table in the database.
Stores metadata for images shared to the public community feed.
Uses the separate table approach to preserve snapshots and separate concerns.
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.config.database import Base


class CommunityImageDB(Base):
    """
    ORM model for the 'community_posts' table.
    Represents a snapshot of a processed image shared publicly.
    """

    __tablename__ = "community_posts"

    # Identity
    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    
    # Ownership (Assuming the user table is named 'users')
    owner_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # The physical path or URL to the permanently stored image
    image_path = Column(String(255), nullable=False)
    
    # Contextual Metadata
    ai_operation = Column(String(50), nullable=True)
    caption = Column(Text, nullable=True)
    
    # Social Engagements (for future improvements)
    likes = Column(Integer, default=0, nullable=False)
    views = Column(Integer, default=0, nullable=False)
    
    # Audit timestamps
    shared_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True  # Index enables fast order by shared_at DESC for feed
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    # Defining a relationship back to the user to easily fetch username for the feed
    # Assumes UserDB is mapped to the "users" table.
    owner = relationship("UserDB", backref="shared_posts")
    post_likes = relationship("CommunityLikeDB", back_populates="post", cascade="all, delete-orphan")
    post_comments = relationship("CommunityCommentDB", back_populates="post", cascade="all, delete-orphan", order_by="desc(CommunityCommentDB.created_at)")

    def __repr__(self) -> str:
        return f"<CommunityImageDB(id={self.id}, owner_id={self.owner_id}, shared_at='{self.shared_at}')>"


class CommunityLikeDB(Base):
    """
    ORM model for recording user likes on community posts.
    """
    __tablename__ = "community_likes"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Ensure a user can only like a post once
    __table_args__ = (UniqueConstraint('post_id', 'user_id', name='_post_user_uc'),)

    post = relationship("CommunityImageDB", back_populates="post_likes")
    user = relationship("UserDB")


class CommunityCommentDB(Base):
    """
    ORM model for user comments on community posts.
    """
    __tablename__ = "community_comments"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    post_id = Column(Integer, ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    post = relationship("CommunityImageDB", back_populates="post_comments")
    user = relationship("UserDB")
