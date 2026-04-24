"""Controller for hairstyle preset and transfer flows."""

from __future__ import annotations

import base64
import uuid

from fastapi import UploadFile

from app.controller.session_controller import SessionController
from app.model.result_image import ResultImage
from app.services.hairstyle_service import HairstyleTryOnService
from app.services.session_service import SessionService
from app.utils.exceptions import ValidationError


class HairstyleController:
    def __init__(
        self,
        hairstyle_service: HairstyleTryOnService,
        session_service: SessionService,
        session_controller: SessionController,
    ):
        self.hairstyleService = hairstyle_service
        self.sessionService = session_service
        self.sessionController = session_controller

    def listPresets(self) -> dict:
        return {
            "items": self.hairstyleService.listPresets(),
            "color_options": self.hairstyleService.listColorOptions(),
        }

    async def generateHairstyle(
        self,
        image_file: UploadFile,
        style_id: str | None,
        hair_color: str,
    ) -> tuple[bytes, str, str]:
        content = await image_file.read()
        if not content:
            raise ValidationError("Source image is required.", "MISSING_HAIR_INPUT")

        result_bytes = self.hairstyleService.generateHairstyle(
            image_bytes=content,
            style_id=style_id or "",
            hair_color=hair_color,
        )
        return result_bytes, "image/png", "hairstyle-preview.png"

    async def generateHairTransfer(
        self,
        session_id: str,
        shape_reference_file: UploadFile,
        color_reference_file: UploadFile,
    ) -> dict:
        self.sessionController.validateSession(session_id)

        source_image = self.sessionService.getImage(session_id)
        if source_image is None:
            raise ValidationError("No source image found in session. Upload first.", "NO_IMAGE")

        shape_content = await shape_reference_file.read()
        color_content = await color_reference_file.read()
        if not shape_content:
            raise ValidationError("Shape reference image is required.", "MISSING_SHAPE_REFERENCE")
        if not color_content:
            raise ValidationError("Color reference image is required.", "MISSING_COLOR_REFERENCE")

        self.sessionService.setProcessingStatus(session_id, "processing")
        result_bytes = self.hairstyleService.generateHairTransfer(
            source_image_bytes=source_image.rawData,
            shape_reference_bytes=shape_content,
            color_reference_bytes=color_content,
        )
        result = ResultImage(
            resultId=str(uuid.uuid4()),
            processedData=result_bytes,
            format="png",
        )
        self.sessionService.storeResult(session_id, result)

        return {
            "session_id": session_id,
            "result_id": result.resultId,
            "result_image": base64.b64encode(result.getData()).decode("utf-8"),
            "format": result.format,
        }
