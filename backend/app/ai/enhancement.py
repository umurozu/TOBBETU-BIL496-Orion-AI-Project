"""
EnhancementModel

Refactors the previous placeholder into a runnable resolution-enhancement
pipeline. If an OpenCV super-resolution checkpoint is configured and present,
it will be used. Otherwise the model falls back to a deterministic CPU
upscaling pipeline with denoising, luminance recovery, and sharpening.
"""

from __future__ import annotations

import logging
from pathlib import Path

from app.ai.base import AIModel
from app.ai.portrait_processing import (
    apply_clahe,
    apply_unsharp_mask,
    decode_image_bytes,
    encode_image_bytes,
    pil_to_rgb_alpha,
    resize_rgb_alpha,
)
from app.config.settings import get_settings
from app.model.editing_request import EditingRequest
from app.model.image import Image
from app.model.result_image import ResultImage
from app.utils.exceptions import ValidationError

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    _CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


class EnhancementModel(AIModel):
    def __init__(self, **kwargs):
        super().__init__(modelName="ResolutionEnhancement", version="2.0.0", **kwargs)
        settings = get_settings()
        self._settings = settings
        self._backendRoot = Path(__file__).resolve().parents[2]
        self._superResPath = self._resolveModelPath(settings.SUPER_RES_MODEL_PATH)
        self._superRes = None
        self._available = False

    def loadModel(self) -> None:
        if not _CV2_AVAILABLE:
            logger.warning("EnhancementModel: OpenCV is not available, using minimal fallback")
            self.loaded = True
            return

        if self._superResPath and self._superResPath.exists():
            try:
                self._superRes = cv2.dnn_superres.DnnSuperResImpl_create()
                self._superRes.readModel(str(self._superResPath))
                self._superRes.setModel(self._settings.SUPER_RES_MODEL_NAME, 4)
                self._available = True
                logger.info("EnhancementModel loaded external super-resolution model from %s", self._superResPath)
            except Exception as exc:
                logger.warning("EnhancementModel could not initialize configured super-resolution model: %s", exc)
                self._superRes = None
                self._available = False
        else:
            logger.info(
                "EnhancementModel using deterministic CPU fallback. Add a model at %s to enable OpenCV super-resolution.",
                self._superResPath,
            )

        self.loaded = True

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        self._ensure_loaded()

        upscale = self._validateScale(request.getParameter("upscale") or 2, image)
        denoise = self._validateFloat(request.getParameter("denoise") or 0.2, "denoise")
        detail_param = request.getParameter("detail_boost")
        if detail_param is None:
            legacy_sharpness = request.getParameter("sharpness")
            if legacy_sharpness is not None:
                detail_param = max(0.0, min(float(legacy_sharpness) / 2.0, 1.0))
            else:
                detail_param = 0.45

        detail_boost = self._validateFloat(detail_param, "detail_boost")

        pil_image = decode_image_bytes(image.rawData)
        rgb_image, alpha_channel = pil_to_rgb_alpha(pil_image)

        if self._available and self._superRes is not None:
            enhanced_rgb, enhanced_alpha = self._runOpenCvSuperRes(rgb_image, alpha_channel, upscale)
        else:
            enhanced_rgb, enhanced_alpha = resize_rgb_alpha(
                rgb_image,
                alpha_channel,
                scale=float(upscale),
                max_edge=self._settings.SUPER_RES_MAX_OUTPUT_EDGE,
            )

        if denoise > 0 and _CV2_AVAILABLE:
            strength = max(1, int(denoise * 10))
            enhanced_bgr = cv2.cvtColor(enhanced_rgb, cv2.COLOR_RGB2BGR)
            enhanced_bgr = cv2.fastNlMeansDenoisingColored(
                enhanced_bgr,
                None,
                h=3 + (strength * 2),
                hColor=3 + (strength * 2),
                templateWindowSize=7,
                searchWindowSize=21,
            )
            enhanced_rgb = cv2.cvtColor(enhanced_bgr, cv2.COLOR_BGR2RGB)

        enhanced_rgb = apply_clahe(enhanced_rgb, clip_limit=1.2 + (detail_boost * 2.2))
        enhanced_rgb = apply_unsharp_mask(
            enhanced_rgb,
            amount=0.35 + (detail_boost * 1.25),
            sigma=1.0,
        )

        result_bytes = encode_image_bytes(enhanced_rgb, enhanced_alpha, image_format="PNG")
        return self.postprocess(result_bytes)

    def _runOpenCvSuperRes(
        self,
        rgb_image: "np.ndarray",
        alpha_channel: "np.ndarray",
        upscale: int,
    ) -> tuple["np.ndarray", "np.ndarray"]:
        bgr_image = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
        upscaled_bgr = self._superRes.upsample(bgr_image)
        upscaled_rgb = cv2.cvtColor(upscaled_bgr, cv2.COLOR_BGR2RGB)

        if upscale != 4:
            scale = upscale / 4.0
            upscaled_rgb, upscaled_alpha = resize_rgb_alpha(
                upscaled_rgb,
                cv2.resize(alpha_channel, (upscaled_rgb.shape[1], upscaled_rgb.shape[0]), interpolation=cv2.INTER_LANCZOS4),
                scale=scale,
                max_edge=self._settings.SUPER_RES_MAX_OUTPUT_EDGE,
            )
        else:
            upscaled_alpha = cv2.resize(
                alpha_channel,
                (upscaled_rgb.shape[1], upscaled_rgb.shape[0]),
                interpolation=cv2.INTER_LANCZOS4,
            )

        return upscaled_rgb.astype(np.uint8), upscaled_alpha.astype(np.uint8)

    def _resolveModelPath(self, configured_path: str) -> Path:
        if not configured_path:
            return self._backendRoot / "checkpoints" / "superres" / "EDSR_x4.pb"

        candidate = Path(configured_path)
        if candidate.is_absolute():
            return candidate
        return self._backendRoot / candidate

    def _validateScale(self, raw_scale: object, image: Image) -> int:
        try:
            scale = int(raw_scale)
        except Exception as exc:
            raise ValidationError("Upscale value must be an integer between 1 and 4.", "INVALID_UPSCALE") from exc

        if scale < 1 or scale > self._settings.SUPER_RES_MAX_SCALE:
            raise ValidationError(
                f"Upscale value must be between 1 and {self._settings.SUPER_RES_MAX_SCALE}.",
                "INVALID_UPSCALE",
            )

        max_edge = max(image.width or 0, image.height or 0)
        projected_edge = max_edge * scale
        if projected_edge > self._settings.SUPER_RES_MAX_OUTPUT_EDGE:
            raise ValidationError(
                f"Requested upscale would create an image larger than {self._settings.SUPER_RES_MAX_OUTPUT_EDGE}px on one side.",
                "UPSCALE_TOO_LARGE",
            )

        return scale

    def _validateFloat(self, raw_value: object, name: str) -> float:
        try:
            value = float(raw_value)
        except Exception as exc:
            raise ValidationError(f"{name} must be a number between 0 and 1.", f"INVALID_{name.upper()}") from exc

        if value < 0 or value > 1:
            raise ValidationError(f"{name} must be between 0 and 1.", f"INVALID_{name.upper()}")

        return value
