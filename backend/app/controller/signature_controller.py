"""
SignatureController

Detects whether an uploaded image contains the Invisio export signature.
"""

from __future__ import annotations

from fastapi import UploadFile

from app.services.signature_service import SignatureService
from app.utils.exceptions import ValidationError


class SignatureController:
    def __init__(self, signature_service: SignatureService):
        self.signatureService = signature_service

    async def detectSignature(self, image_file: UploadFile) -> dict:
        content = await image_file.read()
        if not content:
            raise ValidationError("No image data received.", "EMPTY_FILE")

        result = self.signatureService.detectSignature(content)
        return {
            "filename": image_file.filename or "uploaded_image",
            **result,
        }
