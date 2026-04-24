"""
Model Package — LLD §2.1.1, §3.1.1
HLD Module: Model Layer

Contains core business logic and data representations of the Invisio system.
"""

from app.model.user import User
from app.model.session import Session
from app.model.image import Image
from app.model.editing_request import EditingRequest, EditingType
from app.model.mask import Mask
from app.model.result_image import ResultImage, ExportFormat
from app.model.community_image import CommunityImage
from app.model.refinement_tool import RefinementTool

# ORM models — imported so SQLAlchemy Base.metadata.create_all discovers them
from app.model.user_db import UserDB  # noqa: F401
from app.model.community_image_db import (  # noqa: F401
    CommunityImageDB,
    CommunityLikeDB,
    CommunityCommentDB,
)

__all__ = [
    "User",
    "Session",
    "Image",
    "EditingRequest",
    "EditingType",
    "Mask",
    "ResultImage",
    "ExportFormat",
    "CommunityImage",
    "RefinementTool",
    # ORM
    "UserDB",
    "CommunityImageDB",
    "CommunityLikeDB",
    "CommunityCommentDB",
]
