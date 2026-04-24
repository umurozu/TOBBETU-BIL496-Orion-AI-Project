"""
Session Model — LLD §3.1.1, Class: Session
HLD Module: Model Layer — Session Management

Represents an active user session. Maintains expiration control and
session validity to support security requirements.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from app.config.settings import get_settings


@dataclass
class Session:
    """
    LLD §3.1.1 — Class Session
    
    Attributes:
        sessionId (str): Unique session identifier
        createdAt (datetime): Session creation timestamp
        expiresAt (datetime): Expiration timestamp
        valid (bool): Session validity flag
    """

    sessionId: str
    createdAt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expiresAt: datetime = field(default=None)
    valid: bool = True

    def __post_init__(self):
        if self.expiresAt is None:
            settings = get_settings()
            self.expiresAt = self.createdAt + timedelta(
                seconds=settings.SESSION_TIMEOUT_SECONDS
            )

    def isValid(self) -> bool:
        """
        Checks session validity.
        
        Returns:
            True if session is valid and not expired.
        """
        if not self.valid:
            return False
        if datetime.now(timezone.utc) > self.expiresAt:
            self.valid = False
            return False
        return True

    def invalidate(self) -> None:
        """Terminates session by setting validity to False."""
        self.valid = False

    def refresh(self) -> None:
        """Extends expiration time from current moment."""
        settings = get_settings()
        self.expiresAt = datetime.now(timezone.utc) + timedelta(
            seconds=settings.SESSION_TIMEOUT_SECONDS
        )
        self.valid = True
