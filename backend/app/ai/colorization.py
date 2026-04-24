"""
ColorizationModel

Wraps the invisio ECCV16 colorization pipeline in mainproject's AI model
interface while keeping the existing /process contract unchanged.
"""

from __future__ import annotations

import logging

from app.ai.base import AIModel
from app.model.editing_request import EditingRequest
from app.model.image import Image
from app.model.result_image import ResultImage
from app.services.eccv_colorization_service import InvisioEccvColorizationService
from app.utils.exceptions import ProcessingError

logger = logging.getLogger(__name__)


class ColorizationModel(AIModel):
    def __init__(self, **kwargs):
        super().__init__(modelName="InvisioECCV16Colorization", version="2.0.0", **kwargs)
        self._service = InvisioEccvColorizationService()

    def loadModel(self) -> None:
        if not self._service.isConfigured():
            logger.error(
                "Invisio ECCV16 assets are missing; colorization cannot be initialized"
            )
            raise ProcessingError(
                "Colorization assets are missing or incomplete on the backend.",
                error_code="COLORIZATION_UNAVAILABLE",
            )

        try:
            self._service.warmup()
        except Exception as exc:
            logger.error("Invisio ECCV16 warmup failed", exc_info=True)
            raise ProcessingError(
                "Colorization model failed to initialize.",
                error_code="COLORIZATION_INIT_FAILED",
            ) from exc

        logger.info("ColorizationModel ready with invisio ECCV16 pipeline")
        self.loaded = True

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        self._ensure_loaded()

        try:
            result_bytes = self._service.colorize(image.rawData)
            return self.postprocess(result_bytes)
        except Exception as exc:
            logger.error("Invisio ECCV16 colorization failed", exc_info=True)
            raise ProcessingError(
                "Colorization failed while processing the image.",
                error_code="COLORIZATION_FAILED",
            ) from exc

    def unloadModel(self) -> None:
        self._service.release()
        super().unloadModel()
