"""
AgeTransformationModel

Deterministic portrait transformation pipeline that can age or rejuvenate a
face without relying on external checkpoints. It uses face landmarks when
available and falls back to a global photographic filter when not.
"""

from __future__ import annotations

import hashlib
import logging

from app.ai.base import AIModel
from app.ai.portrait_processing import (
    FaceAnalysis,
    LEFT_EYE,
    RIGHT_EYE,
    analyze_portrait,
    apply_brightness_contrast,
    apply_clahe,
    apply_saturation,
    apply_temperature,
    apply_unsharp_mask,
    decode_image_bytes,
    encode_image_bytes,
    gaussian_soft_mask,
    masked_blend,
    pil_to_rgb_alpha,
)
from app.model.editing_request import EditingRequest, EditingType
from app.model.image import Image
from app.model.result_image import ResultImage
from app.services.mobile_sam_service import MobileSamService
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


class AgeTransformationModel(AIModel):
    def __init__(self, **kwargs):
        super().__init__(modelName="AgeTransformation", version="1.1.0", **kwargs)
        self._mobile_sam = MobileSamService()

    def loadModel(self) -> None:
        self.loaded = True
        logger.info("AgeTransformationModel ready with MobileSAM-enhanced deterministic pipeline")

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        self._ensure_loaded()

        intensity = self._validateFloat(request.getParameter("intensity") or 0.65, "intensity")
        rejuvenate = self._resolveMode(request)
        target_age = self._resolveTargetAge(request, intensity, rejuvenate)

        logger.info(
            "AgeTransformationModel: using enhanced deterministic pipeline rejuvenate=%s",
            rejuvenate,
        )

        pil_image = decode_image_bytes(image.rawData)
        rgb_image, alpha_channel = pil_to_rgb_alpha(pil_image)
        analysis = analyze_portrait(rgb_image)
        if analysis is None and _CV2_AVAILABLE:
            analysis = self._estimatePortraitAnalysis(rgb_image.shape[:2])

        if analysis is not None and _CV2_AVAILABLE:
            if rejuvenate:
                output_rgb = self._applyRejuvenation(rgb_image, analysis, intensity)
            else:
                output_rgb = self._applyAging(rgb_image, analysis, intensity, image.rawData)
        else:
            logger.info("AgeTransformationModel: portrait landmarks unavailable, using global fallback")
            if rejuvenate:
                output_rgb = apply_brightness_contrast(rgb_image, brightness=0.04 + (intensity * 0.05), contrast=-0.03)
                output_rgb = apply_temperature(output_rgb, intensity * 0.25)
                output_rgb = apply_saturation(output_rgb, intensity * 0.08)
            else:
                output_rgb = apply_brightness_contrast(rgb_image, brightness=-(0.03 + (intensity * 0.05)), contrast=0.10 + (intensity * 0.08))
                output_rgb = apply_saturation(output_rgb, -(0.08 + (intensity * 0.08)))
                output_rgb = apply_unsharp_mask(output_rgb, amount=0.15 + (intensity * 0.20), sigma=1.1)

        result_bytes = encode_image_bytes(output_rgb, alpha_channel, image_format="PNG")
        return self.postprocess(result_bytes)

    def unloadModel(self) -> None:
        super().unloadModel()

    def _applyAging(self, rgb_image, analysis, intensity: float, raw_bytes: bytes):
        # Enhance masks using MobileSAM if possible
        self._enhanceAnalysisWithMobileSAM(rgb_image, analysis)

        aged_rgb = apply_brightness_contrast(
            rgb_image,
            brightness=-(0.05 + (intensity * 0.06)),
            contrast=0.12 + (intensity * 0.18),
        )
        aged_rgb = apply_saturation(aged_rgb, -(0.10 + (intensity * 0.14)))
        aged_rgb = apply_temperature(aged_rgb, -(0.05 + (intensity * 0.18)))
        aged_rgb = masked_blend(rgb_image, aged_rgb, analysis.faceMask, strength=0.68 + (intensity * 0.22))

        skin_texture_rgb = apply_clahe(aged_rgb, clip_limit=1.5 + (intensity * 1.8))
        skin_texture_rgb = apply_unsharp_mask(
            skin_texture_rgb,
            amount=0.40 + (intensity * 0.55),
            sigma=0.85,
        )
        aged_rgb = masked_blend(
            aged_rgb,
            skin_texture_rgb,
            analysis.skinMask,
            strength=0.22 + (intensity * 0.20),
        )

        wrinkle_mask = self._buildWrinkleMask(rgb_image.shape[:2], analysis, raw_bytes, intensity)
        wrinkle_rgb = apply_brightness_contrast(aged_rgb, brightness=-0.22, contrast=0.22)
        aged_rgb = masked_blend(aged_rgb, wrinkle_rgb, wrinkle_mask, strength=0.58 + (intensity * 0.25))

        contour_shadow_mask = self._buildContourShadowMask(rgb_image.shape[:2], analysis)
        contour_shadow_rgb = apply_brightness_contrast(aged_rgb, brightness=-0.10, contrast=0.08)
        aged_rgb = masked_blend(
            aged_rgb,
            contour_shadow_rgb,
            contour_shadow_mask,
            strength=0.30 + (intensity * 0.22),
        )

        eye_shadow = apply_brightness_contrast(aged_rgb, brightness=-0.12)
        aged_rgb = masked_blend(aged_rgb, eye_shadow, analysis.underEyeMask, strength=0.68)

        # Final polish
        aged_rgb = apply_unsharp_mask(aged_rgb, amount=0.16 + (intensity * 0.24), sigma=1.0)
        return aged_rgb

    def _applyRejuvenation(self, rgb_image, analysis, intensity: float):
        # Enhance masks using MobileSAM if possible
        self._enhanceAnalysisWithMobileSAM(rgb_image, analysis)

        smoothed_rgb = cv2.bilateralFilter(
            rgb_image,
            d=0,
            sigmaColor=24 + int(44 * intensity),
            sigmaSpace=18 + int(22 * intensity),
        )
        rejuvenated_rgb = masked_blend(
            rgb_image,
            smoothed_rgb,
            analysis.skinMask,
            strength=0.40 + (intensity * 0.40),
        )

        brighter_face = apply_brightness_contrast(rejuvenated_rgb, brightness=0.05 + (intensity * 0.05), contrast=-0.02)
        rejuvenated_rgb = masked_blend(rejuvenated_rgb, brighter_face, analysis.faceMask, strength=0.35)

        brighter_under_eye = apply_brightness_contrast(rejuvenated_rgb, brightness=0.09 + (intensity * 0.04))
        rejuvenated_rgb = masked_blend(rejuvenated_rgb, brighter_under_eye, analysis.underEyeMask, strength=0.60)

        warmer_rgb = apply_temperature(rejuvenated_rgb, intensity * 0.28)
        warmer_rgb = apply_saturation(warmer_rgb, intensity * 0.10)
        rejuvenated_rgb = masked_blend(rejuvenated_rgb, warmer_rgb, analysis.faceMask, strength=0.30)

        feature_rgb = apply_unsharp_mask(rejuvenated_rgb, amount=0.20 + (intensity * 0.22), sigma=0.9)
        feature_mask = cv2.max(analysis.eyeMask, analysis.mouthMask)
        rejuvenated_rgb = masked_blend(rejuvenated_rgb, feature_rgb, feature_mask, strength=0.50)

        soft_skin = apply_brightness_contrast(rejuvenated_rgb, brightness=0.03 + (intensity * 0.03), contrast=-0.04)
        return masked_blend(rejuvenated_rgb, soft_skin, analysis.skinMask, strength=0.24 + (intensity * 0.20))

    def _enhanceAnalysisWithMobileSAM(self, rgb_image, analysis):
        """Uses MobileSAM to refine face and skin masks for better blending."""
        try:
            mobile_mask = self._mobile_sam.predict_portrait_mask(rgb_image, analysis.points)
            if int(mobile_mask.max()) > 0:
                # Refine faceMask
                analysis.faceMask = cv2.bitwise_and(analysis.faceMask, mobile_mask)
                # Refine skinMask
                analysis.skinMask = cv2.bitwise_and(analysis.skinMask, mobile_mask)
        except Exception as e:
            logger.debug("MobileSAM enhancement skipped: %s", e)

    def _buildWrinkleMask(self, shape, analysis, raw_bytes: bytes, intensity: float):
        wrinkle_canvas = np.zeros(shape, dtype=np.uint8)
        seed = int.from_bytes(hashlib.sha256(raw_bytes[:4096]).digest()[:8], "big")
        rng = np.random.default_rng(seed)

        self._drawForeheadLines(wrinkle_canvas, analysis, intensity, rng)
        self._drawUnderEyeLines(wrinkle_canvas, analysis, intensity)
        self._drawSmileLines(wrinkle_canvas, analysis, intensity)
        self._drawNasolabialLines(wrinkle_canvas, analysis, intensity)

        noise = rng.normal(128, 24, shape).astype(np.float32)
        noise = cv2.GaussianBlur(noise, (0, 0), sigmaX=1.15)
        noise = cv2.normalize(np.abs(noise - 128.0), None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        wrinkle_canvas = cv2.addWeighted(wrinkle_canvas, 0.75, noise, 0.25, 0)
        wrinkle_canvas = cv2.bitwise_and(wrinkle_canvas, analysis.faceMask)
        return gaussian_soft_mask(wrinkle_canvas, 17)

    def _drawForeheadLines(self, canvas, analysis, intensity: float, rng):
        ys, xs = np.where(analysis.foreheadMask > 0)
        if len(xs) == 0 or len(ys) == 0:
            return

        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        line_count = 3 + int(round(intensity * 3))

        for idx in range(line_count):
            y_pos = int(np.interp(idx, [0, max(1, line_count - 1)], [y_min + 4, y_max - 4]))
            y_pos += int(rng.integers(-3, 4))
            control_points = []
            for step in range(6):
                x_pos = int(np.interp(step, [0, 5], [x_min + 8, x_max - 8]))
                offset = int(rng.integers(-2, 3))
                control_points.append((x_pos, y_pos + offset))
            cv2.polylines(
                canvas,
                [np.array(control_points, dtype=np.int32)],
                isClosed=False,
                color=255,
                thickness=1 + int(intensity * 2),
            )

    def _drawUnderEyeLines(self, canvas, analysis, intensity: float):
        for indices in (LEFT_EYE, RIGHT_EYE):
            eye_points = analysis.points[indices]
            x_min, y_min = eye_points.min(axis=0)
            x_max, y_max = eye_points.max(axis=0)
            line_y = int(y_max + max(2, (y_max - y_min) * 0.5))
            line = np.array(
                [
                    (int(x_min), line_y),
                    (int((x_min + x_max) / 2), line_y + max(1, int(intensity * 2))),
                    (int(x_max), line_y),
                ],
                dtype=np.int32,
            )
            cv2.polylines(canvas, [line], isClosed=False, color=255, thickness=1 + int(intensity))

    def _drawSmileLines(self, canvas, analysis, intensity: float):
        left_corner = analysis.points[61]
        right_corner = analysis.points[291]
        face_height = int(analysis.points[:, 1].max() - analysis.points[:, 1].min())
        offset = max(8, int(face_height * 0.10))

        left_line = np.array(
            [
                (int(left_corner[0]), int(left_corner[1])),
                (int(left_corner[0] - offset * 0.55), int(left_corner[1] - offset * 0.45)),
                (int(left_corner[0] - offset * 0.90), int(left_corner[1] - offset * 0.90)),
            ],
            dtype=np.int32,
        )
        right_line = np.array(
            [
                (int(right_corner[0]), int(right_corner[1])),
                (int(right_corner[0] + offset * 0.55), int(right_corner[1] - offset * 0.45)),
                (int(right_corner[0] + offset * 0.90), int(right_corner[1] - offset * 0.90)),
            ],
            dtype=np.int32,
        )

        cv2.polylines(canvas, [left_line], isClosed=False, color=255, thickness=1 + int(intensity))
        cv2.polylines(canvas, [right_line], isClosed=False, color=255, thickness=1 + int(intensity))

    def _drawNasolabialLines(self, canvas, analysis, intensity: float):
        left_nose = analysis.points[98]
        right_nose = analysis.points[327]
        left_corner = analysis.points[61]
        right_corner = analysis.points[291]

        left_line = np.array(
            [
                (int(left_nose[0]), int(left_nose[1])),
                (int((left_nose[0] + left_corner[0]) / 2), int(left_nose[1] + (left_corner[1] - left_nose[1]) * 0.35)),
                (int(left_corner[0]), int(left_corner[1])),
            ],
            dtype=np.int32,
        )
        right_line = np.array(
            [
                (int(right_nose[0]), int(right_nose[1])),
                (int((right_nose[0] + right_corner[0]) / 2), int(right_nose[1] + (right_corner[1] - right_nose[1]) * 0.35)),
                (int(right_corner[0]), int(right_corner[1])),
            ],
            dtype=np.int32,
        )

        cv2.polylines(canvas, [left_line], isClosed=False, color=255, thickness=1 + int(intensity * 2))
        cv2.polylines(canvas, [right_line], isClosed=False, color=255, thickness=1 + int(intensity * 2))

    def _buildContourShadowMask(self, shape, analysis):
        shadow_mask = np.zeros(shape, dtype=np.uint8)
        face_mask = gaussian_soft_mask(analysis.faceMask, 31)
        eroded = cv2.erode(
            face_mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (35, 35)),
            iterations=1,
        )
        shadow_mask = cv2.subtract(face_mask, eroded)
        lower_band = np.zeros(shape, dtype=np.uint8)
        split_line = int(shape[0] * 0.35)
        lower_band[split_line:, :] = 255
        shadow_mask = cv2.bitwise_and(shadow_mask, lower_band)
        return gaussian_soft_mask(shadow_mask, 41)

    def _estimatePortraitAnalysis(self, shape) -> FaceAnalysis:
        height, width = shape
        center_x = width // 2
        center_y = int(height * 0.5)
        face_width = max(72, int(width * 0.42))
        face_height = max(96, int(height * 0.62))

        face_mask = np.zeros(shape, dtype=np.uint8)
        cv2.ellipse(
            face_mask,
            (center_x, center_y),
            (face_width // 2, face_height // 2),
            0,
            0,
            360,
            255,
            -1,
        )
        face_mask = gaussian_soft_mask(face_mask, 41)

        points = np.zeros((468, 2), dtype=np.int32)

        def _ellipse_points(cx: int, cy: int, radius_x: int, radius_y: int, count: int):
            angles = np.linspace(0, 2 * np.pi, count, endpoint=False)
            return np.array(
                [
                    (int(cx + np.cos(angle) * radius_x), int(cy + np.sin(angle) * radius_y))
                    for angle in angles
                ],
                dtype=np.int32,
            )

        left_eye_center = (center_x - int(face_width * 0.18), center_y - int(face_height * 0.14))
        right_eye_center = (center_x + int(face_width * 0.18), center_y - int(face_height * 0.14))
        eye_rx = max(10, int(face_width * 0.065))
        eye_ry = max(6, int(face_height * 0.032))

        left_eye_points = _ellipse_points(left_eye_center[0], left_eye_center[1], eye_rx, eye_ry, len(LEFT_EYE))
        right_eye_points = _ellipse_points(right_eye_center[0], right_eye_center[1], eye_rx, eye_ry, len(RIGHT_EYE))
        for idx, point in zip(LEFT_EYE, left_eye_points):
            points[idx] = point
        for idx, point in zip(RIGHT_EYE, right_eye_points):
            points[idx] = point

        left_brow_points = np.array(
            [
                (left_eye_center[0] - eye_rx, left_eye_center[1] - eye_ry - 10),
                (left_eye_center[0] - eye_rx // 2, left_eye_center[1] - eye_ry - 14),
                (left_eye_center[0], left_eye_center[1] - eye_ry - 16),
                (left_eye_center[0] + eye_rx // 2, left_eye_center[1] - eye_ry - 14),
                (left_eye_center[0] + eye_rx, left_eye_center[1] - eye_ry - 10),
            ],
            dtype=np.int32,
        )
        right_brow_points = np.array(
            [
                (right_eye_center[0] - eye_rx, right_eye_center[1] - eye_ry - 10),
                (right_eye_center[0] - eye_rx // 2, right_eye_center[1] - eye_ry - 14),
                (right_eye_center[0], right_eye_center[1] - eye_ry - 16),
                (right_eye_center[0] + eye_rx // 2, right_eye_center[1] - eye_ry - 14),
                (right_eye_center[0] + eye_rx, right_eye_center[1] - eye_ry - 10),
            ],
            dtype=np.int32,
        )
        for idx, point in zip([70, 63, 105, 66, 107], left_brow_points):
            points[idx] = point
        for idx, point in zip([300, 293, 334, 296, 336], right_brow_points):
            points[idx] = point

        mouth_center = (center_x, center_y + int(face_height * 0.20))
        mouth_rx = max(18, int(face_width * 0.16))
        mouth_ry = max(10, int(face_height * 0.05))
        mouth_points = _ellipse_points(mouth_center[0], mouth_center[1], mouth_rx, mouth_ry, 11)
        mouth_indices = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]
        for idx, point in zip(mouth_indices, mouth_points):
            points[idx] = point

        points[98] = np.array((center_x - max(10, int(face_width * 0.09)), center_y + int(face_height * 0.02)))
        points[327] = np.array((center_x + max(10, int(face_width * 0.09)), center_y + int(face_height * 0.02)))

        eye_mask = np.zeros(shape, dtype=np.uint8)
        cv2.ellipse(eye_mask, left_eye_center, (eye_rx + 4, eye_ry + 4), 0, 0, 360, 255, -1)
        cv2.ellipse(eye_mask, right_eye_center, (eye_rx + 4, eye_ry + 4), 0, 0, 360, 255, -1)
        eye_mask = gaussian_soft_mask(eye_mask, 25)

        mouth_mask = np.zeros(shape, dtype=np.uint8)
        cv2.ellipse(mouth_mask, mouth_center, (mouth_rx + 4, mouth_ry + 3), 0, 0, 360, 255, -1)
        mouth_mask = gaussian_soft_mask(mouth_mask, 21)

        brow_mask = np.zeros(shape, dtype=np.uint8)
        cv2.polylines(brow_mask, [left_brow_points], False, 255, thickness=8)
        cv2.polylines(brow_mask, [right_brow_points], False, 255, thickness=8)
        brow_mask = gaussian_soft_mask(brow_mask, 21)

        exclude_mask = cv2.max(eye_mask, mouth_mask)
        exclude_mask = cv2.max(exclude_mask, brow_mask)
        skin_mask = cv2.subtract(face_mask, exclude_mask)
        skin_mask = gaussian_soft_mask(skin_mask, 31)

        forehead_mask = np.zeros(shape, dtype=np.uint8)
        forehead_top = max(0, center_y - face_height // 2)
        forehead_bottom = center_y - int(face_height * 0.16)
        forehead_mask[forehead_top:forehead_bottom, :] = 255
        forehead_mask = cv2.bitwise_and(forehead_mask, face_mask)
        forehead_mask = gaussian_soft_mask(forehead_mask, 31)

        under_eye_mask = np.zeros(shape, dtype=np.uint8)
        band_height = max(14, int(face_height * 0.08))
        for eye_center in (left_eye_center, right_eye_center):
            cv2.ellipse(
                under_eye_mask,
                (eye_center[0], eye_center[1] + band_height // 2),
                (eye_rx + 10, eye_ry + band_height),
                0,
                0,
                360,
                255,
                -1,
            )
        under_eye_mask = cv2.bitwise_and(under_eye_mask, face_mask)
        under_eye_mask = gaussian_soft_mask(under_eye_mask, 25)

        return FaceAnalysis(
            points=points,
            faceMask=face_mask,
            skinMask=skin_mask,
            eyeMask=eye_mask,
            mouthMask=mouth_mask,
            foreheadMask=forehead_mask,
            underEyeMask=under_eye_mask,
        )

    def _resolveMode(self, request: EditingRequest) -> bool:
        if request.editingType == EditingType.REJUVENATION:
            return True

        mode = request.getParameter("mode")
        if isinstance(mode, str):
            normalized = mode.strip().lower()
            if normalized in {"young", "younger", "rejuvenate", "rejuvenation"}:
                return True
            if normalized in {"older", "old", "aging", "age"}:
                return False

        target_age = request.getParameter("target_age")
        if target_age is not None:
            try:
                return int(target_age) < 35
            except Exception:
                pass

        return bool(request.getParameter("rejuvenate"))

    def _resolveTargetAge(self, request: EditingRequest, intensity: float, rejuvenate: bool) -> int:
        raw_target_age = request.getParameter("target_age")
        if raw_target_age is not None:
            try:
                return max(0, min(100, int(raw_target_age)))
            except Exception as exc:
                raise ValidationError(
                    "target_age must be an integer between 0 and 100.",
                    "INVALID_TARGET_AGE",
                ) from exc

        if rejuvenate:
            return max(14, min(34, int(round(32 - (intensity * 14)))))
        return max(48, min(86, int(round(54 + (intensity * 28)))))

    def _validateFloat(self, raw_value: object, name: str) -> float:
        try:
            value = float(raw_value)
        except Exception as exc:
            raise ValidationError(f"{name} must be a number between 0 and 1.", f"INVALID_{name.upper()}") from exc

        if value < 0 or value > 1:
            raise ValidationError(f"{name} must be between 0 and 1.", f"INVALID_{name.upper()}")

        return value
