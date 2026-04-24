"""
User Model — LLD §3.1.1, Class: User
HLD Module: Model Layer — Core Domain

Represents a system user. Stores authentication state, session association,
and community-related information. Acts as the entry point for personalized
image processing workflows.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.model.session import Session
    from app.model.image import Image
    from app.model.community_image import CommunityImage


@dataclass
class User:
    """
    LLD §3.1.1 — Class User
    
    Attributes:
        userId (str): Unique identifier of the user
        authenticated (bool): Indicates authentication state
        activeSession (Optional[Session]): Associated active session
        uploadedImages (List[Image]): Images uploaded by the user
        sharedImages (List[CommunityImage]): Images shared to community
    """

    userId: str
    authenticated: bool = False
    activeSession: Optional["Session"] = None
    uploadedImages: List["Image"] = field(default_factory=list)
    sharedImages: List["CommunityImage"] = field(default_factory=list)

    def authenticate(self, token: str) -> None:
        """
        Authenticates user session.
        
        Args:
            token: Authentication token string.
        """
        # Token validation logic would be implemented here
        self.authenticated = True

    def logout(self) -> None:
        """Terminates authentication and invalidates active session."""
        self.authenticated = False
        if self.activeSession is not None:
            self.activeSession.invalidate()
            self.activeSession = None

    def uploadImage(self, image: "Image") -> None:
        """
        Registers an uploaded image to the user's collection.
        
        Args:
            image: Image instance to register.
        """
        self.uploadedImages.append(image)

    def shareImage(self, image: "CommunityImage") -> None:
        """
        Publishes an image to the community gallery.
        
        Args:
            image: CommunityImage instance to share.
        """
        self.sharedImages.append(image)
