"""
Storage Service
HLD Module: Services Layer — Persistent Storage

Handles saving images permanently to the local file system.
This is used specifically to save snapshots of ResultImages when users
choose to share them to the community.
"""

from __future__ import annotations
import os
import uuid
import logging
import io

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class StorageService:
    """
    Local file storage service.
    """

    def __init__(self):
        settings = get_settings()
        # Defaulting to "data/community_images" if not provided in settings
        self.storage_dir = getattr(settings, "COMMUNITY_STORAGE_DIR", "data/community_images")
        self._ensure_storage_dir()

    def _ensure_storage_dir(self):
        """Ensures the storage directory exists."""
        if not os.path.exists(self.storage_dir):
            os.makedirs(self.storage_dir, exist_ok=True)
            logger.info(f"Created storage directory at {self.storage_dir}")

    def save_image_bytes(self, image_bytes: bytes, extension: str = "png") -> str:
        """
        Saves raw bytes to a file in the storage directory.
        
        Args:
            image_bytes: The image byte content.
            extension: File extension (e.g., 'png', 'jpg').
            
        Returns:
            The relative URL or path mapping to the saved file.
        """
        filename = f"{uuid.uuid4()}.{extension}"
        filepath = os.path.join(self.storage_dir, filename)

        try:
            with open(filepath, "wb") as f:
                f.write(image_bytes)
            logger.info(f"Saved image to {filepath}")
            # Returning the filename so it can be served via a dedicated endpoint
            return filename
        except IOError as e:
            logger.error(f"Failed to save image to {filepath}: {e}")
            from app.utils.exceptions import ImageIntegrityError
            raise ImageIntegrityError(f"Failed to save file to disk: {e}")

    def get_image_path(self, filename: str) -> str:
        """
        Returns the absolute path to a saved image.
        """
        # Ensure that filename doesn't contain directory traversal sequences
        safe_filename = os.path.basename(filename)
        return os.path.join(self.storage_dir, safe_filename)

    def delete_image(self, filename: str) -> bool:
        """
        Deletes an image from the storage directory.
        """
        if not filename:
            return False
            
        filepath = self.get_image_path(filename)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted image {filepath}")
                return True
            return False
        except IOError as e:
            logger.error(f"Failed to delete image {filepath}: {e}")
            return False
