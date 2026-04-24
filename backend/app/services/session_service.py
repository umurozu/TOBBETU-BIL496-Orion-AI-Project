"""
Session Service — LLD §2.1.2 (SessionController), §1.1.5
HLD Module: Services Layer — Session Management

In-memory session store with automatic expiry cleanup.
No persistent storage — privacy-by-design (LLD §1.1.3).
"""

from __future__ import annotations
import uuid
import threading
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from app.model.session import Session
from app.model.image import Image
from app.model.result_image import ResultImage
from app.config.settings import get_settings
from app.utils.exceptions import SessionNotFoundError, SessionExpiredError

logger = logging.getLogger(__name__)


class SessionData:
    """Holds all data associated with a session."""

    def __init__(self, session: Session):
        self.session = session
        self.uploaded_image: Optional[Image] = None
        self.result_image: Optional[ResultImage] = None
        self.processing_status: str = "idle"  # idle, processing, completed, error


class SessionService:
    """
    In-memory session management service.
    
    Thread-safe container for active sessions.
    Provides session creation, validation, image storage, and cleanup.
    """

    def __init__(self):
        self._sessions: Dict[str, SessionData] = {}
        self._lock = threading.Lock()

    def createSession(self) -> str:
        """
        Creates a new session and returns the session ID.
        
        Returns:
            Unique session ID string.
        """
        session_id = str(uuid.uuid4())
        session = Session(sessionId=session_id)

        with self._lock:
            self._sessions[session_id] = SessionData(session=session)

        logger.info(f"Session created: {session_id}")
        return session_id

    def validateSession(self, session_id: str) -> bool:
        """
        Verifies session validity.
        
        Args:
            session_id: Session ID to validate.
            
        Returns:
            True if session is valid and not expired.
            
        Raises:
            SessionNotFoundError: If session does not exist.
            SessionExpiredError: If session has expired.
        """
        with self._lock:
            session_data = self._sessions.get(session_id)

        if session_data is None:
            raise SessionNotFoundError()

        if not session_data.session.isValid():
            # Cleanup expired session
            self.cleanupSession(session_id)
            raise SessionExpiredError()

        return True

    def getSessionData(self, session_id: str) -> SessionData:
        """
        Retrieves session data.
        
        Args:
            session_id: Session ID.
            
        Returns:
            SessionData instance.
        """
        self.validateSession(session_id)
        with self._lock:
            return self._sessions[session_id]

    def storeImage(self, session_id: str, image: Image) -> None:
        """
        Temporarily stores uploaded image in session.
        
        Args:
            session_id: Session ID.
            image: Image instance to store.
        """
        session_data = self.getSessionData(session_id)
        session_data.uploaded_image = image
        session_data.session.refresh()
        logger.info(f"Image stored in session {session_id}: {image.imageId}")

    def getImage(self, session_id: str) -> Optional[Image]:
        """
        Retrieves image from session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Image instance or None.
        """
        session_data = self.getSessionData(session_id)
        return session_data.uploaded_image

    def storeResult(self, session_id: str, result: ResultImage) -> None:
        """Stores processing result in session."""
        session_data = self.getSessionData(session_id)
        session_data.result_image = result
        session_data.processing_status = "completed"

    def getResult(self, session_id: str) -> Optional[ResultImage]:
        """Retrieves processing result from session."""
        session_data = self.getSessionData(session_id)
        return session_data.result_image

    def setProcessingStatus(self, session_id: str, status: str) -> None:
        """Updates session processing status."""
        session_data = self.getSessionData(session_id)
        session_data.processing_status = status

    def expireSession(self, session_id: str) -> None:
        """Terminates a session."""
        with self._lock:
            session_data = self._sessions.get(session_id)
            if session_data:
                session_data.session.invalidate()
                logger.info(f"Session expired: {session_id}")

    def cleanupSession(self, session_id: str) -> None:
        """
        Deletes session data permanently.
        Removes all image data from memory — privacy compliance.
        """
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                logger.info(f"Session cleaned up: {session_id}")

    def cleanupExpiredSessions(self) -> int:
        """
        Removes all expired sessions.
        Called periodically by background task.
        
        Returns:
            Number of sessions cleaned up.
        """
        expired = []
        with self._lock:
            for sid, data in self._sessions.items():
                if not data.session.isValid():
                    expired.append(sid)

        for sid in expired:
            self.cleanupSession(sid)

        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

        return len(expired)

    def getActiveSessionCount(self) -> int:
        """Returns count of currently active sessions."""
        with self._lock:
            return len(self._sessions)
