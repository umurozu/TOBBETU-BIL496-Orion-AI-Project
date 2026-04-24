"""
Image Model — LLD §3.1.1, Class: Image
HLD Module: Model Layer — Core Domain

Represents an uploaded image entity. Stores metadata and raw image data
used for AI processing.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import io

from app.config.settings import get_settings
from app.utils.exceptions import ImageFormatError, ImageSizeError


@dataclass
class Image:
    """
    LLD §3.1.1 — Class Image
    
    Attributes:
        imageId (str): Unique identifier
        rawData (bytes): Raw pixel data
        format (str): Image file format (JPG, PNG)
        size (int): File size in bytes
        width (int): Image width
        height (int): Image height
        metadata (Dict[str, Any]): Additional image metadata
    """

    imageId: str
    rawData: bytes
    format: str
    size: int
    width: int = 0
    height: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validateFormat(self) -> bool:
        """
        Validates image format against allowed formats from settings.
        
        Returns:
            True if format is valid.
            
        Raises:
            ImageFormatError: If format is not in allowed list.
        """
        settings = get_settings()
        normalized_format = self.format.lower().strip(".")
        if normalized_format not in settings.ALLOWED_FORMATS:
            raise ImageFormatError(
                f"Format '{self.format}' is not supported. "
                f"Allowed: {settings.ALLOWED_FORMATS}"
            )
        return True

    def validateSize(self, maxSize: Optional[int] = None) -> bool:
        """
        Validates file size against maximum allowed size.
        
        Args:
            maxSize: Maximum file size in bytes. Uses settings default if None.
            
        Returns:
            True if size is valid.
            
        Raises:
            ImageSizeError: If file exceeds maximum size.
        """
        settings = get_settings()
        limit = maxSize or settings.MAX_FILE_SIZE
        if self.size > limit:
            raise ImageSizeError(
                f"File size {self.size} bytes exceeds maximum {limit} bytes"
            )
        return True

    def normalize(self) -> None:
        """
        Applies preprocessing normalization.
        Converts to RGB format and standard tensor representation
        for model compatibility (LLD §1.2.3).
        
        This method prepares the image for AI model input by:
        - Converting to RGB color space
        - Applying resizing if needed
        """
        try:
            from PIL import Image as PILImage

            img = PILImage.open(io.BytesIO(self.rawData))

            # Convert to RGB if necessary
            if img.mode != "RGB":
                img = img.convert("RGB")

            self.width = img.width
            self.height = img.height

            # Save back normalized data
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            self.rawData = buffer.getvalue()
            self.size = len(self.rawData)

        except Exception as e:
            from app.utils.exceptions import ImageIntegrityError
            raise ImageIntegrityError(
                f"Failed to normalize image: {str(e)}"
            )
