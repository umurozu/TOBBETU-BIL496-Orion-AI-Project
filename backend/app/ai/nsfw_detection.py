"""
NSFWDetectionModel — Specialized Implementation
Ensures platform safety by detecting and blocking unsafe content.

Integrated as a memory-resident model (LLD §1.2.5) for high performance.
Weights are stored locally in 'checkpoints/nsfw_model/'.
"""

from __future__ import annotations
import io
import logging
import uuid
import os
from pathlib import Path
from PIL import Image as PILImage

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from app.ai.base import AIModel
from app.model.image import Image
from app.model.editing_request import EditingRequest
from app.model.result_image import ResultImage
from app.utils.exceptions import NSFWContentError
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

class NSFWDetectionModel(AIModel):
    """
    Direct in-memory NSFW detection model using Transformers pipeline.
    """

    def __init__(self, detectionThreshold: float = None, autoBlock: bool = True, **kwargs):
        settings = get_settings()
        super().__init__(modelName="NSFWDetectionModel", **kwargs)
        self.detectionThreshold = detectionThreshold or settings.NSFW_DETECTION_THRESHOLD
        self.autoBlock = autoBlock if autoBlock is not None else settings.NSFW_AUTO_BLOCK
        self._classifier = None
        
        # Local checkpoint path
        self.local_model_path = Path(__file__).parents[2] / "checkpoints" / "nsfw_model"

    def loadModel(self) -> None:
        """Loads the Vision Transformer (ViT) model into RAM once."""
        if self._classifier is not None:
            return

        try:
            from transformers import pipeline
            
            if not self.local_model_path.exists():
                logger.error(f"NSFW model weights missing at {self.local_model_path}")
                self.loaded = True
                return

            device = 0 if (HAS_TORCH and torch.cuda.is_available()) else -1
            logger.info(f"Initializing NSFW classifier from {self.local_model_path} on device: {'cuda' if device == 0 else 'cpu'}")
            
            self._classifier = pipeline(
                "image-classification",
                model=str(self.local_model_path),
                device=device
            )
            
            logger.info("NSFWDetectionModel (Memory-Resident) loaded successfully.")
            self.loaded = True
        except Exception as e:
            logger.error(f"Failed to load NSFW detection model: {e}")
            self.loaded = True # Mark as loaded to prevent retry-loop but it won't be available

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        """Identifies NSFW content. Raises NSFWContentError if flagged and autoBlock is True."""
        self._ensure_loaded()
        
        is_nsfw = self.detect(image)

        if is_nsfw and self.autoBlock:
            logger.warning(f"NSFW content detected in image {image.imageId} — BLOCKED")
            raise NSFWContentError()

        return self.postprocess(image.rawData)

    def detect(self, image: Image) -> bool:
        """Performs high-speed in-memory inference."""
        if self._classifier is None:
            logger.debug("NSFW classifier not loaded — skipping safety check.")
            return False

        try:
            # Prepare image for transformers
            pil_img = PILImage.open(io.BytesIO(image.rawData)).convert("RGB")
            
            # Direct inference (Memory-resident, no subprocess)
            results = self._classifier(pil_img)
            
            # results: [{'label': 'nsfw', 'score': 0.99}, ...]
            for res in results:
                label = res['label'].lower()
                # Check for various NSFW labels depending on model output format
                if any(x in label for x in ['nsfw', 'porn', 'hentai', 'sexy', 'explicit', 'nudity', 'unsafe']):
                    if res['score'] >= self.detectionThreshold:
                        logger.warning(f"NSFW detected: {label} (score: {res['score']:.4f})")
                        return True
            
            return False

        except Exception as e:
            logger.error(f"In-memory NSFW detection error: {e}")
            return False

