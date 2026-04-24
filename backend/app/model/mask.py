"""
Mask Model — LLD §3.1.1, Class: Mask
HLD Module: Model Layer — Core Domain

Represents segmentation mask data used in region-based editing operations
such as inpainting and refinement.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    from app.model.image import Image


@dataclass
class Mask:
    """
    LLD §3.1.1 — Class Mask

    Attributes:
        maskData (np.ndarray): Pixel-level mask values (2D array, 0-255)
        confidenceScore (float): AI confidence metric (0.0 to 1.0)
        width (int): Mask width
        height (int): Mask height
    """

    maskData: np.ndarray
    confidenceScore: float
    width: int
    height: int

    def refine(self, brushInput: np.ndarray) -> None:
        """
        Applies refinement operations based on brush input.
        
        Merges user-drawn brush data into the existing mask.
        Non-zero brush pixels override corresponding mask pixels.
        
        Args:
            brushInput: 2D numpy array of brush modifications (same dimensions as mask).
        """
        if brushInput.shape != self.maskData.shape:
            raise ValueError(
                f"Brush input dimensions {brushInput.shape} do not match "
                f"mask dimensions {self.maskData.shape}"
            )
        # Apply brush: non-zero brush values override mask values
        non_zero = brushInput > 0
        self.maskData[non_zero] = brushInput[non_zero]

    def validateDimensions(self, image: "Image") -> bool:
        """
        Ensures mask dimensions are compatible with the source image.
        
        Args:
            image: Source Image instance.
            
        Returns:
            True if mask dimensions match image dimensions.
        """
        return self.width == image.width and self.height == image.height

    def to_bytes(self) -> bytes:
        """Serializes mask data to bytes for transmission."""
        return self.maskData.tobytes()

    @classmethod
    def from_bytes(cls, data: bytes, width: int, height: int, confidence: float = 1.0) -> "Mask":
        """
        Creates a Mask instance from raw bytes.
        
        Args:
            data: Raw mask bytes.
            width: Mask width.
            height: Mask height.
            confidence: Confidence score.
            
        Returns:
            Mask instance.
        """
        if len(data) == width * height:
            mask_array = np.frombuffer(data, dtype=np.uint8).reshape((height, width))
        else:
            import io
            from PIL import Image as PILImage
            try:
                img = PILImage.open(io.BytesIO(data)).convert("L")
                if img.size != (width, height):
                    img = img.resize((width, height), PILImage.Resampling.NEAREST)
                mask_array = np.array(img, dtype=np.uint8)
            except Exception:
                mask_array = np.zeros((height, width), dtype=np.uint8)
        return cls(
            maskData=mask_array,
            confidenceScore=confidence,
            width=width,
            height=height,
        )
