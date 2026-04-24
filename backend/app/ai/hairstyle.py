"""
HairstyleModel

Wraps the hairstyle try-on service behind the shared AIModel interface so the
feature can run through the standard /process pipeline.
"""

from __future__ import annotations

import logging

from app.ai.base import AIModel
from app.model.editing_request import EditingRequest
from app.model.image import Image
from app.model.result_image import ResultImage
from app.services.hairstyle_service import HairstyleTryOnService

logger = logging.getLogger(__name__)


class HairstyleModel(AIModel):
    def __init__(self, hairstyle_service: HairstyleTryOnService, **kwargs):
        super().__init__(modelName="HairstyleTryOn", version="1.0.0", **kwargs)
        self._hairstyleService = hairstyle_service

    def loadModel(self) -> None:
        # Keep startup light; the underlying pipeline is cached lazily by the service.
        self.loaded = True
        logger.info("HairstyleModel ready and bound to cached hairstyle service")

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        self._ensure_loaded()
        hair_color = str(request.getParameter("hair_color") or "natural_black")
        mask_data = request.getParameter("mask_data")
        brush_size = request.getParameter("brush_size")
        resolved_brush_size = None
        if brush_size is not None:
            try:
                resolved_brush_size = int(brush_size)
            except Exception:
                resolved_brush_size = None
        result_bytes = self._hairstyleService.generateHairstyle(
            image_bytes=image.rawData,
            style_id="",
            hair_color=hair_color,
            user_mask_b64=mask_data if isinstance(mask_data, str) else None,
            brush_size=resolved_brush_size,
        )
        return self.postprocess(result_bytes)

    def generateMask(self, image: Image) -> Mask:
        """
        Generates a high-precision hair mask using MobileSAM.
        """
        from app.model.mask import Mask
        import numpy as np
        
        mask_np = self._hairstyleService.get_hair_mask(image.rawData)
        return Mask(
            maskData=mask_np,
            confidenceScore=0.95,
            width=image.width,
            height=image.height
        )
