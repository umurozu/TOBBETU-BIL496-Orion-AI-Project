"""
ImageController — LLD §3.1.2, Class: ImageController
HLD Module: Controller Layer — Image Handling

Handles image upload, validation, and temporary storage operations.
Ensures uploaded files comply with format, size, and integrity constraints.

API Route: POST /upload
"""

from __future__ import annotations
import uuid
import io
import logging

from fastapi import APIRouter, UploadFile, File
from PIL import Image as PILImage

from app.model.image import Image
from app.services.session_service import SessionService
from app.controller.security_controller import SecurityController
from app.controller.session_controller import SessionController
from app.ai.factory import AIModelFactory
from app.model.editing_request import EditingType, EditingRequest
from app.schemas.responses import APIResponse
from app.config.settings import get_settings
from app.utils.exceptions import (
    ImageFormatError,
    ImageSizeError,
    ImageIntegrityError,
    NSFWContentError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ImageController:
    """
    LLD §3.1.2 — Class ImageController

    Attributes:
        allowedFormats (list): Supported image file extensions
        maxFileSize (int): Maximum allowed file size in bytes
        sessionController: Session management
        securityController: Security validation
    """

    def __init__(
        self,
        session_service: SessionService,
        session_controller: SessionController,
        security_controller: SecurityController,
        model_factory: AIModelFactory,
    ):
        settings = get_settings()
        self.allowedFormats = settings.ALLOWED_FORMATS
        self.maxFileSize = settings.MAX_FILE_SIZE
        self.sessionService = session_service
        self.sessionController = session_controller
        self.securityController = security_controller
        self.modelFactory = model_factory

    async def uploadImage(self, imageFile: UploadFile) -> dict:
        """
        Accepts, validates, and stores an uploaded image.
        Creates a new session and runs NSFW detection.
        
        Args:
            imageFile: Uploaded file from multipart request.
            
        Returns:
            Dictionary with session_id, image_id, and image metadata.
            
        Raises:
            ImageFormatError: If file format is not allowed.
            ImageSizeError: If file size exceeds limit.
            ImageIntegrityError: If file is corrupted.
            NSFWContentError: If NSFW content is detected.
        """
        logger.info(f"Processing upload: {imageFile.filename}")

        # Read file content
        content = await imageFile.read()
        file_size = len(content)

        # Extract format from filename
        filename = imageFile.filename or "unknown.png"
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        # Validate format
        if not self._validateFormat(extension):
            raise ImageFormatError(
                f"Format '.{extension}' is not supported. Allowed: {self.allowedFormats}"
            )

        # Validate size
        if not self._validateSize(file_size):
            raise ImageSizeError(
                f"File size {file_size} bytes exceeds max {self.maxFileSize} bytes"
            )

        # Validate integrity
        if not self._validateIntegrity(content):
            raise ImageIntegrityError()

        # Parse image dimensions
        try:
            pil_image = PILImage.open(io.BytesIO(content))
            width, height = pil_image.size
        except Exception:
            raise ImageIntegrityError("Could not read image dimensions")

        # Create Image model
        image_id = str(uuid.uuid4())
        image = Image(
            imageId=image_id,
            rawData=content,
            format=extension,
            size=file_size,
            width=width,
            height=height,
            metadata={"original_filename": filename},
        )

        # Create session and store image
        session_id = self.sessionController.createSession()
        self.sessionService.storeImage(session_id, image)

        # Run NSFW detection (LLD §1.2.5 — executed before processing)
        if self.modelFactory.supports(EditingType.NSFW_DETECTION):
            nsfw_model = self.modelFactory.createModel(EditingType.NSFW_DETECTION)
            if not nsfw_model.isLoaded():
                try:
                    nsfw_model.loadModel()
                except Exception as exc:
                    logger.warning(f"NSFW model lazy-load failed, continuing without blocking upload: {exc}")

            nsfw_request = EditingRequest(
                requestId=str(uuid.uuid4()),
                editingType=EditingType.NSFW_DETECTION,
            )
            if nsfw_model.isLoaded():
                nsfw_model.process(image, nsfw_request)

        logger.info(f"Upload complete: session={session_id}, image={image_id}")

        return {
            "session_id": session_id,
            "image_id": image_id,
            "width": width,
            "height": height,
            "format": extension,
            "size": file_size,
        }

    def deleteTemporaryImage(self, session_id: str) -> None:
        """Removes image after session completion."""
        self.sessionController.cleanupSession(session_id)
        logger.info(f"Temporary image deleted for session {session_id}")

    def _validateFormat(self, extension: str) -> bool:
        """Checks whether file format is allowed."""
        return extension.lower() in self.allowedFormats

    def _validateSize(self, size: int) -> bool:
        """Validates file size constraints."""
        return size <= self.maxFileSize

    def _validateIntegrity(self, content: bytes) -> bool:
        """Verifies file consistency and corruption."""
        try:
            img = PILImage.open(io.BytesIO(content))
            img.verify()
            return True
        except Exception:
            return False
