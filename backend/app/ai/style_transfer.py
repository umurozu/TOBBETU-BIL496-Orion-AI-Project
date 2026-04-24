"""
StyleTransferModel — LLD §3.1.1, Class: StyleTransferModel (extends AIModel)
HLD Module: AI Processing Layer

Applies artistic style transformations using neural style transfer techniques.
"""

from __future__ import annotations
import uuid
import io
import logging
import subprocess
from pathlib import Path

from app.ai.base import AIModel
from app.model.image import Image
from app.model.editing_request import EditingRequest
from app.model.result_image import ResultImage

logger = logging.getLogger(__name__)


class StyleTransferModel(AIModel):
    """
    LLD §3.1.1 — Class StyleTransferModel (extends AIModel)

    Attributes:
        styleId (str): Selected artistic style identifier
        styleStrength (float): Controls blending ratio (0.0 to 1.0)
    """

    def __init__(self, **kwargs):
        super().__init__(modelName="AdaINStyleTransfer", version="1.0", **kwargs)
        self._get_model = None
        self._adain_base = Path(__file__).parent.parent.parent.parent / "models" / "pytorch-AdaIN"
        self._style_base = self._adain_base / "input" / "style"
        self._available = False

    def loadModel(self) -> None:
        """Initialize the AdaIN model instance."""
        try:
            from .inference_adain import get_adain_model
            self._get_model = get_adain_model
            self._get_model()
            self._available = True
            logger.info("AdaINStyleTransfer loaded successfully (direct inference)")
        except Exception as e:
            logger.error(f"Failed to load AdaIN weights: {e}")
        self.loaded = True

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        """
        Applies style transfer using the new direct inference engine.
        """
        self._ensure_loaded()

        if not self._available:
            logger.warning("AdaIN unavailable — returning original image")
            return self.postprocess(image.rawData)

        try:
            # Map style_id from UI to physical file
            style_id = request.getParameter("style_id") or "impressionist"
            style_file = "mondrian.jpg"
            if style_id == "sketch": style_file = "sketch.png"
            elif style_id == "candy": style_file = "candy.jpg"
            elif style_id == "asheville": style_file = "asheville.jpg"

            style_path = self._style_base / style_file
            if not style_path.exists():
                logger.warning(f"Style file {style_path} not found, using default")
                # Fallback to any file in style_base if possible
                files = list(self._style_base.glob("*.*"))
                if files: style_path = files[0]

            alpha = float(request.getParameter("intensity") or 1.0)

            # Get model singleton
            model = self._get_model()

            # Process content image from raw bytes
            from PIL import Image as PILImage
            content_pil = PILImage.open(io.BytesIO(image.rawData)).convert("RGB")
            content_tensor = model.preprocess(content_pil)
            
            # Process style image
            style_tensor = model.preprocess(str(style_path))

            # Perform style transfer
            output_tensor = model.style_transfer(content_tensor, style_tensor, alpha=alpha)

            # Convert back to bytes
            import torch
            from torchvision.utils import save_image
            output_buffer = io.BytesIO()
            save_image(output_tensor, output_buffer, format='PNG')
            result_bytes = output_buffer.getvalue()

            return self.postprocess(result_bytes)

        except Exception as e:
            logger.error(f"AdaIN direct inference error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self.postprocess(image.rawData)

