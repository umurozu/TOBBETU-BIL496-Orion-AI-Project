"""
BeautificationModel

Portrait enhancement pipeline that runs inside the existing backend without
depending on external repositories or checkpoints. It uses face landmarks
when available and gracefully falls back to a global enhancement pass.
"""

from __future__ import annotations

import logging

from app.ai.base import AIModel
from app.ai.portrait_processing import (
    analyze_portrait,
    apply_brightness_contrast,
    apply_clahe,
    apply_saturation,
    apply_temperature,
    apply_unsharp_mask,
    decode_image_bytes,
    encode_image_bytes,
    masked_blend,
    pil_to_rgb_alpha,
)
from app.model.editing_request import EditingRequest
from app.model.image import Image
from app.model.result_image import ResultImage
from app.utils.exceptions import ValidationError

try:
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    _CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


class BeautificationModel(AIModel):
    def __init__(self, **kwargs):
        super().__init__(modelName="PortraitBeautification", version="2.0.0", **kwargs)

    def loadModel(self) -> None:
        self.loaded = True
        logger.info("BeautificationModel ready with portrait-aware CPU pipeline")

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        self._ensure_loaded()

        skin_smoothing = self._validateFloat(
            request.getParameter("skin_smoothing")
            if request.getParameter("skin_smoothing") is not None
            else request.getParameter("smoothing") or 0.55,
            "skin_smoothing",
        )
        detail_boost = self._validateFloat(
            request.getParameter("detail_boost") or 0.45,
            "detail_boost",
        )
        tone_balance = self._validateFloat(
            request.getParameter("tone_balance") or 0.4,
            "tone_balance",
        )

        pil_image = decode_image_bytes(image.rawData)
        rgb_image, alpha_channel = pil_to_rgb_alpha(pil_image)
        analysis = analyze_portrait(rgb_image)

        if analysis is not None and _CV2_AVAILABLE:
            smoothed_rgb = cv2.bilateralFilter(
                rgb_image,
                d=0,
                sigmaColor=28 + int(52 * skin_smoothing),
                sigmaSpace=18 + int(24 * skin_smoothing),
            )
            output_rgb = masked_blend(
                rgb_image,
                smoothed_rgb,
                analysis.skinMask,
                strength=0.35 + (skin_smoothing * 0.55),
            )

            warm_rgb = apply_temperature(output_rgb, tone_balance * 0.45)
            warm_rgb = apply_saturation(warm_rgb, tone_balance * 0.12)
            output_rgb = masked_blend(output_rgb, warm_rgb, analysis.faceMask, strength=0.35)

            bright_under_eye = apply_brightness_contrast(output_rgb, brightness=0.05 + (tone_balance * 0.04))
            output_rgb = masked_blend(output_rgb, bright_under_eye, analysis.underEyeMask, strength=0.5)

            feature_rgb = apply_clahe(output_rgb, clip_limit=1.1 + (detail_boost * 1.8))
            feature_rgb = apply_unsharp_mask(feature_rgb, amount=0.4 + (detail_boost * 0.9), sigma=0.9)
            feature_mask = cv2.max(analysis.eyeMask, analysis.mouthMask)
            output_rgb = masked_blend(output_rgb, feature_rgb, feature_mask, strength=0.6)

            output_rgb = apply_unsharp_mask(output_rgb, amount=0.12 + (detail_boost * 0.25), sigma=1.1)
        else:
            logger.info("BeautificationModel: portrait landmarks unavailable, applying global fallback enhancement")
            output_rgb = apply_clahe(rgb_image, clip_limit=1.35)
            output_rgb = apply_temperature(output_rgb, tone_balance * 0.28)
            output_rgb = apply_unsharp_mask(output_rgb, amount=0.18 + (detail_boost * 0.32), sigma=1.0)

        result_bytes = encode_image_bytes(output_rgb, alpha_channel, image_format="PNG")
        return self.postprocess(result_bytes)

    def _validateFloat(self, raw_value: object, name: str) -> float:
        try:
            value = float(raw_value)
        except Exception as exc:
            raise ValidationError(f"{name} must be a number between 0 and 1.", f"INVALID_{name.upper()}") from exc

        if value < 0 or value > 1:
            raise ValidationError(f"{name} must be between 0 and 1.", f"INVALID_{name.upper()}")

        return value
