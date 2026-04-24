"""
ResultImage Model — LLD §3.1.1, Class: ResultImage
HLD Module: Model Layer — Core Domain

Represents the output of an AI processing operation.
Provides export functionality in different formats.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import io


class ExportFormat(str, Enum):
    """Supported export formats for result images."""
    JPEG = "jpeg"
    PNG = "png"
    WEBP = "webp"


@dataclass
class ResultImage:
    """
    LLD §3.1.1 — Class ResultImage

    Attributes:
        resultId (str): Unique result identifier
        processedData (bytes): Processed image data
        format (str): Output format
        generatedAt (datetime): Generation timestamp
    """

    resultId: str
    processedData: bytes
    format: str = "png"
    generatedAt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def export(self, export_format: ExportFormat) -> bytes:
        """
        Converts image to specified format.
        
        Args:
            export_format: Target ExportFormat (JPEG, PNG, WEBP).
            
        Returns:
            Image bytes in the requested format.
        """
        from PIL import Image as PILImage

        img = PILImage.open(io.BytesIO(self.processedData))
        buffer = io.BytesIO()

        if export_format == ExportFormat.JPEG:
            # JPEG requires RGB mode
            if img.mode == "RGBA":
                img = img.convert("RGB")
            img.save(buffer, format="JPEG", quality=95)
        elif export_format == ExportFormat.PNG:
            img.save(buffer, format="PNG")
        elif export_format == ExportFormat.WEBP:
            img.save(buffer, format="WEBP", quality=90)

        return buffer.getvalue()

    def getData(self) -> bytes:
        """
        Returns processed image bytes.
        
        Returns:
            Raw processed image data.
        """
        return self.processedData
