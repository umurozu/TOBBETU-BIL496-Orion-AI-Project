"""
Centralized export pipeline for downloadable results.

Keeps the processing result untouched in memory and applies watermarking
only when the user requests a final downloadable file.
"""

from __future__ import annotations

import io

from PIL import Image as PILImage

from app.model.result_image import ExportFormat, ResultImage
from app.services.signature_service import SignatureService
from app.services.watermark_service import WatermarkService


class ExportService:
    def __init__(
        self,
        watermark_service: WatermarkService | None = None,
        signature_service: SignatureService | None = None,
    ):
        self.watermarkService = watermark_service or WatermarkService()
        self.signatureService = signature_service or SignatureService(self.watermarkService)

    def exportResult(self, image: ResultImage, export_format: ExportFormat) -> bytes:
        watermarked = self.watermarkService.applyWatermark(image.getData())
        signed = self.signatureService.embedSignature(watermarked)
        return self._encodeImage(signed, export_format)

    def _encodeImage(self, image: PILImage.Image, export_format: ExportFormat) -> bytes:
        buffer = io.BytesIO()

        if export_format == ExportFormat.JPEG:
            if image.mode == "RGBA":
                background = PILImage.new("RGB", image.size, (255, 255, 255))
                background.paste(image, mask=image.getchannel("A"))
                image = background
            else:
                image = image.convert("RGB")
            image.save(buffer, format="JPEG", quality=95, subsampling=0)
        elif export_format == ExportFormat.PNG:
            image.save(buffer, format="PNG")
        elif export_format == ExportFormat.WEBP:
            image.save(buffer, format="WEBP", quality=92, method=6)

        return buffer.getvalue()
