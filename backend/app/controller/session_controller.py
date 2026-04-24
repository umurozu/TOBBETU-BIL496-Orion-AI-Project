"""
SessionController — LLD §3.1.2, Class: SessionController
HLD Module: Controller Layer — Session Management

Manages session lifecycle, temporary image storage, and cleanup operations
to ensure privacy compliance.

API Route: GET /status/{session_id}
"""

import logging
from fastapi import APIRouter

from app.services.session_service import SessionService
from app.controller.security_controller import SecurityController
from app.schemas.responses import APIResponse, StatusResponseData

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionController:
    """
    LLD §3.1.2 — Class SessionController

    Attributes:
        sessionService: In-memory session store
        securityController: Security interceptor
    """

    def __init__(self, session_service: SessionService, security_controller: SecurityController):
        self.sessionService = session_service
        self.securityController = security_controller

    def createSession(self) -> str:
        """
        Initializes a new session.
        
        Returns:
            New session ID.
        """
        return self.sessionService.createSession()

    def validateSession(self, session_id: str) -> bool:
        """
        Verifies session validity.
        
        Args:
            session_id: Session ID to check.
            
        Returns:
            True if session is valid.
        """
        return self.sessionService.validateSession(session_id)

    def getStatus(self, session_id: str) -> dict:
        """
        Returns session status information.
        
        Args:
            session_id: Session ID.
            
        Returns:
            Status dictionary with session info.
        """
        session_data = self.sessionService.getSessionData(session_id)
        return {
            "session_id": session_id,
            "status": session_data.processing_status,
            "has_image": session_data.uploaded_image is not None,
            "has_result": session_data.result_image is not None,
            "expires_at": session_data.session.expiresAt.isoformat(),
        }

    def expireSession(self, session_id: str) -> None:
        """Terminates a session."""
        self.sessionService.expireSession(session_id)

    def cleanupSession(self, session_id: str) -> None:
        """Deletes session data permanently."""
        self.sessionService.cleanupSession(session_id)
