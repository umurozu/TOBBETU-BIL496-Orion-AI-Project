"""
CommunityImage Model — LLD §3.1.1, Class: CommunityImage
HLD Module: Model Layer — Core Domain

Represents images shared within the community.
Extends ResultImage with social interaction attributes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.model.result_image import ResultImage


@dataclass
class CommunityImage(ResultImage):
    """
    LLD §3.1.1 — Class CommunityImage (extends ResultImage)

    Attributes:
        likeCount (int): Number of likes
        viewCount (int): Number of views
        ownerId (str): Owner user identifier
        sharedAt (datetime): Share timestamp
    """

    likeCount: int = 0
    viewCount: int = 0
    ownerId: str = ""
    sharedAt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def incrementLikes(self) -> None:
        """Increases like count by one."""
        self.likeCount += 1

    def incrementViews(self) -> None:
        """Increases view count by one."""
        self.viewCount += 1
