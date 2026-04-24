"""
Lightweight hair editing service.

Supports two flows:
    - active source-hair recolor using a portrait hair mask
    - legacy three-image transfer kept for compatibility
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import io
import logging
from pathlib import Path
import uuid

from PIL import Image as PILImage

from app.ai.u2net_segmentation import U2NetSegmentationModel
from app.ai.portrait_processing import (
    analyze_portrait,
    apply_brightness_contrast,
    apply_clahe,
    apply_saturation,
    apply_temperature,
    apply_unsharp_mask,
    encode_image_bytes,
    gaussian_soft_mask,
    masked_blend,
)
from app.config.hairstyle_catalog import (
    DEFAULT_HAIR_COLOR_ID,
    HAIR_COLOR_OPTIONS,
    HairColorSpec,
)
from app.config.settings import get_settings
from app.model.image import Image
from app.utils.exceptions import ProcessingError, ValidationError

from app.services.session_service import SessionService
from app.services.mobile_sam_service import MobileSamService

try:
    import cv2
    import numpy as np

    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    _CV2_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class PreparedHairImage:
    rgb: "np.ndarray"
    analysis: object | None
    face_box: tuple[int, int, int, int]
    hair_mask: "np.ndarray"


class HairInputValidator:
    def __init__(self, max_bytes: int):
        self._max_bytes = max_bytes

    def ensure_image(self, image_bytes: bytes, label: str) -> None:
        if not image_bytes:
            raise ValidationError(f"{label} image is required.", "MISSING_HAIR_INPUT")
        if len(image_bytes) > self._max_bytes:
            raise ValidationError(
                f"{label} image exceeds the {self._max_bytes // (1024 * 1024)} MB upload limit.",
                "HAIR_INPUT_TOO_LARGE",
            )

        try:
            with PILImage.open(io.BytesIO(image_bytes)) as candidate:
                candidate.verify()
        except Exception as exc:
            raise ValidationError(
                f"{label} image could not be decoded as a valid JPG or PNG.",
                "INVALID_HAIR_IMAGE",
            ) from exc


class HairPreprocessor:
    def __init__(self, max_edge: int):
        self._max_edge = max(256, int(max_edge))

    def prepare(self, image_bytes: bytes, label: str) -> PreparedHairImage:
        try:
            pil_image = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise ValidationError(
                f"{label} image could not be opened.",
                "INVALID_HAIR_IMAGE",
            ) from exc

        rgb = np.array(pil_image, dtype=np.uint8)
        rgb = self._resize(rgb)
        analysis = analyze_portrait(rgb)
        face_box = self._resolve_face_box(rgb, analysis)
        hair_mask = self._build_hair_mask(rgb, analysis, face_box)

        return PreparedHairImage(
            rgb=rgb,
            analysis=analysis,
            face_box=face_box,
            hair_mask=hair_mask,
        )

    def preparePresetAsset(self, image_bytes: bytes, label: str) -> PreparedHairImage:
        try:
            pil_image = PILImage.open(io.BytesIO(image_bytes)).convert("RGB")
        except Exception as exc:
            raise ValidationError(
                f"{label} preset could not be opened.",
                "INVALID_HAIR_IMAGE",
            ) from exc

        rgb = np.array(pil_image, dtype=np.uint8)
        rgb = self._resize(rgb)
        hair_mask = self._extract_preset_mask(rgb)
        if int(hair_mask.max()) == 0:
            raise ValidationError(
                f"{label} preset could not be isolated from its background.",
                "INVALID_HAIR_PRESET",
            )

        cropped_rgb, cropped_mask = self._crop_to_mask(rgb, hair_mask)
        crop_h, crop_w = cropped_rgb.shape[:2]
        return PreparedHairImage(
            rgb=cropped_rgb,
            analysis=None,
            face_box=(0, 0, max(1, crop_w - 1), max(1, crop_h - 1)),
            hair_mask=gaussian_soft_mask(cropped_mask, 17),
        )

    def _resize(self, rgb: "np.ndarray") -> "np.ndarray":
        height, width = rgb.shape[:2]
        largest_edge = max(height, width)
        if largest_edge <= self._max_edge:
            return rgb

        scale = self._max_edge / float(largest_edge)
        new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
        return cv2.resize(rgb, new_size, interpolation=cv2.INTER_AREA).astype(np.uint8)

    def _resolve_face_box(
        self,
        rgb: "np.ndarray",
        analysis: object | None,
    ) -> tuple[int, int, int, int]:
        height, width = rgb.shape[:2]
        if analysis is not None and getattr(analysis, "points", None) is not None:
            points = analysis.points
            x0 = int(np.clip(points[:, 0].min(), 0, width - 1))
            y0 = int(np.clip(points[:, 1].min(), 0, height - 1))
            x1 = int(np.clip(points[:, 0].max(), 0, width - 1))
            y1 = int(np.clip(points[:, 1].max(), 0, height - 1))
            if x1 > x0 and y1 > y0:
                return x0, y0, x1, y1

        fallback_w = int(width * 0.34)
        fallback_h = int(height * 0.38)
        center_x = width // 2
        center_y = int(height * 0.38)
        x0 = max(0, center_x - fallback_w // 2)
        y0 = max(0, center_y - fallback_h // 2)
        x1 = min(width - 1, x0 + fallback_w)
        y1 = min(height - 1, y0 + fallback_h)
        return x0, y0, x1, y1

    def _build_hair_mask(
        self,
        rgb: "np.ndarray",
        analysis: object | None,
        face_box: tuple[int, int, int, int],
    ) -> "np.ndarray":
        height, width = rgb.shape[:2]
        x0, y0, x1, y1 = face_box
        face_w = max(1, x1 - x0)
        face_h = max(1, y1 - y0)
        center_x = x0 + (face_w // 2)
        center_y = int(y0 + (face_h * 0.28))

        mask = np.zeros((height, width), dtype=np.uint8)
        axes = (
            max(20, int(face_w * 0.95)),
            max(28, int(face_h * 1.12)),
        )
        cv2.ellipse(mask, (center_x, center_y), axes, 0, 0, 360, 255, -1)

        side_axis_y = max(16, int(face_h * 0.58))
        side_axis_x = max(14, int(face_w * 0.22))
        side_y = int(y0 + face_h * 0.38)
        cv2.ellipse(mask, (int(x0 + face_w * 0.08), side_y), (side_axis_x, side_axis_y), 18, 0, 360, 255, -1)
        cv2.ellipse(mask, (int(x1 - face_w * 0.08), side_y), (side_axis_x, side_axis_y), -18, 0, 360, 255, -1)

        top_clip = max(0, int(y0 - face_h * 0.95))
        lower_clip = min(height, int(y1 + face_h * 0.22))
        clip_mask = np.zeros_like(mask)
        clip_mask[top_clip:lower_clip, :] = 255
        mask = cv2.bitwise_and(mask, clip_mask)

        face_mask = getattr(analysis, "faceMask", None)
        if face_mask is not None:
            face_core = cv2.erode(
                face_mask,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)),
                iterations=1,
            )
            mask = cv2.subtract(mask, face_core)

        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)),
            iterations=2,
        )
        return gaussian_soft_mask(mask, 31)

    def _extract_preset_mask(self, rgb: "np.ndarray") -> "np.ndarray":
        border = np.concatenate(
            [
                rgb[:20, :, :].reshape(-1, 3),
                rgb[-20:, :, :].reshape(-1, 3),
                rgb[:, :20, :].reshape(-1, 3),
                rgb[:, -20:, :].reshape(-1, 3),
            ],
            axis=0,
        )
        background_rgb = np.median(border, axis=0).astype(np.float32)
        diff = np.linalg.norm(
            rgb.astype(np.float32) - background_rgb[None, None, :],
            axis=2,
        )
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        saturation = hsv[:, :, 1]
        value = hsv[:, :, 2]

        mask = np.where(
            (diff > 18.0) | (value < 245) | ((saturation > 22) & (value < 252)),
            255,
            0,
        ).astype(np.uint8)
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
            iterations=1,
        )
        mask = cv2.morphologyEx(
            mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11)),
            iterations=2,
        )
        mask = self._keep_largest_component(mask)
        if int(mask.max()) == 0:
            return mask

        return cv2.dilate(
            mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
            iterations=1,
        )

    def _keep_largest_component(self, mask: "np.ndarray") -> "np.ndarray":
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if component_count <= 1:
            return mask

        largest_index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        filtered = np.where(labels == largest_index, 255, 0).astype(np.uint8)
        return filtered

    def _crop_to_mask(
        self,
        rgb: "np.ndarray",
        mask: "np.ndarray",
    ) -> tuple["np.ndarray", "np.ndarray"]:
        ys, xs = np.where(mask > 0)
        if len(xs) == 0 or len(ys) == 0:
            return rgb, mask

        height, width = rgb.shape[:2]
        x0 = max(0, int(xs.min()) - max(12, int(width * 0.02)))
        y0 = max(0, int(ys.min()) - max(12, int(height * 0.02)))
        x1 = min(width, int(xs.max()) + max(12, int(width * 0.02)) + 1)
        y1 = min(height, int(ys.max()) + max(12, int(height * 0.02)) + 1)
        return rgb[y0:y1, x0:x1].copy(), mask[y0:y1, x0:x1].copy()


class HairPoseAligner:
    def align(
        self,
        source: PreparedHairImage,
        reference: PreparedHairImage,
        scale_multiplier: float = 1.08,
        y_shift_ratio: float = 0.0,
        x_shift_ratio: float = 0.0,
    ) -> tuple["np.ndarray", "np.ndarray"]:
        dst_h, dst_w = source.rgb.shape[:2]

        sx0, sy0, sx1, sy1 = source.face_box
        rx0, ry0, rx1, ry1 = reference.face_box

        source_w = max(1, sx1 - sx0)
        source_h = max(1, sy1 - sy0)
        reference_w = max(1, rx1 - rx0)
        reference_h = max(1, ry1 - ry0)

        source_center = np.array([sx0 + source_w / 2.0, sy0 + source_h / 2.0], dtype=np.float32)
        reference_center = np.array([rx0 + reference_w / 2.0, ry0 + reference_h / 2.0], dtype=np.float32)

        scale = min(source_w / reference_w, source_h / reference_h) * float(scale_multiplier)
        transform = np.array(
            [
                [
                    scale,
                    0.0,
                    float(source_center[0] - (reference_center[0] * scale) + (source_w * float(x_shift_ratio))),
                ],
                [
                    0.0,
                    scale,
                    float(source_center[1] - (reference_center[1] * scale) + (source_h * float(y_shift_ratio))),
                ],
            ],
            dtype=np.float32,
        )

        aligned_rgb = cv2.warpAffine(
            reference.rgb,
            transform,
            (dst_w, dst_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REFLECT_101,
        )
        aligned_mask = cv2.warpAffine(
            reference.hair_mask,
            transform,
            (dst_w, dst_h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        return aligned_rgb.astype(np.uint8), aligned_mask.astype(np.uint8)


class HairPresetAssetAligner:
    def align(
        self,
        source: PreparedHairImage,
        preset: PreparedHairImage,
        width_ratio: float = 1.5,
        bottom_anchor_ratio: float = 0.2,
        y_shift_ratio: float = 0.0,
        x_shift_ratio: float = 0.0,
    ) -> tuple["np.ndarray", "np.ndarray"]:
        dst_h, dst_w = source.rgb.shape[:2]
        sx0, sy0, sx1, sy1 = source.face_box
        face_w = max(1, sx1 - sx0)
        face_h = max(1, sy1 - sy0)

        preset_h, preset_w = preset.rgb.shape[:2]
        target_w = max(40, int(round(face_w * float(width_ratio))))
        scale = target_w / float(max(1, preset_w))
        target_h = max(40, int(round(preset_h * scale)))
        interpolation = cv2.INTER_LANCZOS4 if scale >= 1.0 else cv2.INTER_AREA

        resized_rgb = cv2.resize(
            preset.rgb,
            (target_w, target_h),
            interpolation=interpolation,
        ).astype(np.uint8)
        resized_mask = cv2.resize(
            preset.hair_mask,
            (target_w, target_h),
            interpolation=interpolation,
        ).astype(np.uint8)

        center_x = int(round((sx0 + sx1) / 2.0 + (face_w * float(x_shift_ratio))))
        bottom_y = int(round(sy1 + (face_h * float(bottom_anchor_ratio)) + (face_h * float(y_shift_ratio))))
        left_x = center_x - (target_w // 2)
        top_y = bottom_y - target_h

        canvas_rgb = np.zeros((dst_h, dst_w, 3), dtype=np.uint8)
        canvas_mask = np.zeros((dst_h, dst_w), dtype=np.uint8)

        src_x0 = max(0, -left_x)
        src_y0 = max(0, -top_y)
        dst_x0 = max(0, left_x)
        dst_y0 = max(0, top_y)
        copy_w = min(target_w - src_x0, dst_w - dst_x0)
        copy_h = min(target_h - src_y0, dst_h - dst_y0)

        if copy_w <= 0 or copy_h <= 0:
            return canvas_rgb, canvas_mask

        canvas_rgb[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = resized_rgb[
            src_y0:src_y0 + copy_h,
            src_x0:src_x0 + copy_w,
        ]
        canvas_mask[dst_y0:dst_y0 + copy_h, dst_x0:dst_x0 + copy_w] = resized_mask[
            src_y0:src_y0 + copy_h,
            src_x0:src_x0 + copy_w,
        ]

        return canvas_rgb, canvas_mask


class HairShapeTransferStage:
    def __init__(self, blend_strength: float):
        self._blend_strength = max(0.25, min(1.0, float(blend_strength)))

    def run(
        self,
        source: PreparedHairImage,
        aligned_shape_rgb: "np.ndarray",
        aligned_shape_mask: "np.ndarray",
    ) -> tuple["np.ndarray", "np.ndarray"]:
        target_mask = cv2.bitwise_and(aligned_shape_mask, source.hair_mask)
        if int(target_mask.max()) == 0:
            target_mask = cv2.max(aligned_shape_mask, source.hair_mask)

        target_mask = cv2.morphologyEx(
            target_mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15)),
            iterations=1,
        )
        soft_mask = gaussian_soft_mask(target_mask, 35)
        shaped_rgb = masked_blend(
            source.rgb,
            aligned_shape_rgb,
            soft_mask,
            strength=self._blend_strength,
        )
        return shaped_rgb, soft_mask


class HairColorTransferStage:
    def __init__(self, color_strength: float):
        self._color_strength = max(0.0, min(1.0, float(color_strength)))

    def run(
        self,
        base_rgb: "np.ndarray",
        target_mask: "np.ndarray",
        aligned_color_rgb: "np.ndarray",
        aligned_color_mask: "np.ndarray",
    ) -> "np.ndarray":
        output = base_rgb.copy()
        target_indices = target_mask > 12
        color_indices = aligned_color_mask > 12
        if not np.any(target_indices) or not np.any(color_indices):
            return output

        base_lab = cv2.cvtColor(base_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        color_lab = cv2.cvtColor(aligned_color_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

        base_pixels = base_lab[target_indices]
        color_pixels = color_lab[color_indices]
        base_mean = base_pixels.mean(axis=0)
        base_std = np.clip(base_pixels.std(axis=0), 1.0, None)
        color_mean = color_pixels.mean(axis=0)
        color_std = np.clip(color_pixels.std(axis=0), 1.0, None)

        transferred = base_pixels.copy()
        transferred[:, 0] = ((transferred[:, 0] - base_mean[0]) / base_std[0]) * color_std[0] + color_mean[0]
        transferred[:, 1] = ((transferred[:, 1] - base_mean[1]) / base_std[1]) * color_std[1] + color_mean[1]
        transferred[:, 2] = ((transferred[:, 2] - base_mean[2]) / base_std[2]) * color_std[2] + color_mean[2]

        blended = (base_pixels * (1.0 - self._color_strength)) + (transferred * self._color_strength)
        base_lab[target_indices] = np.clip(blended, 0, 255)

        output = cv2.cvtColor(base_lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
        return output.astype(np.uint8)


class HairPaletteColorStage:
    def run(
        self,
        preset_rgb: "np.ndarray",
        preset_mask: "np.ndarray",
        color_spec: HairColorSpec,
    ) -> "np.ndarray":
        l_channel = cv2.cvtColor(preset_rgb, cv2.COLOR_RGB2LAB)[:, :, 0].astype(np.float32) / 255.0
        target_fill = np.zeros_like(preset_rgb, dtype=np.float32)
        target_fill[:] = np.array(color_spec.rgb, dtype=np.float32)
        shaded_target = np.clip(target_fill * (0.4 + (l_channel[:, :, None] * 0.85)), 0, 255).astype(np.uint8)

        recolored = masked_blend(preset_rgb, shaded_target, preset_mask, strength=color_spec.strength)

        if color_spec.warmth:
            warmed = apply_temperature(recolored, color_spec.warmth)
            recolored = masked_blend(recolored, warmed, preset_mask, strength=0.46)

        if color_spec.saturation:
            saturated = apply_saturation(recolored, color_spec.saturation)
            recolored = masked_blend(recolored, saturated, preset_mask, strength=0.52)

        if color_spec.brightness:
            brightened = apply_brightness_contrast(recolored, brightness=color_spec.brightness)
            recolored = masked_blend(recolored, brightened, preset_mask, strength=0.34)

        recolored = apply_unsharp_mask(recolored, amount=0.16, sigma=0.9)
        return recolored


class HairPresetOverlayStage:
    def __init__(self, blend_strength: float):
        self._blend_strength = max(0.25, min(1.0, float(blend_strength)))

    def run(
        self,
        source: PreparedHairImage,
        aligned_preset_rgb: "np.ndarray",
        aligned_preset_mask: "np.ndarray",
    ) -> tuple["np.ndarray", "np.ndarray"]:
        target_mask = aligned_preset_mask.copy()
        target_mask = cv2.morphologyEx(
            target_mask,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13)),
            iterations=2,
        )
        target_mask = cv2.dilate(
            target_mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
            iterations=1,
        )

        if source.analysis is not None:
            face_core = cv2.subtract(source.analysis.faceMask, source.analysis.foreheadMask)
            face_core = cv2.erode(
                face_core,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)),
                iterations=1,
            )
            target_mask = cv2.subtract(target_mask, face_core)

        target_mask = gaussian_soft_mask(target_mask, 27)
        overlay_rgb = masked_blend(
            source.rgb,
            aligned_preset_rgb,
            target_mask,
            strength=self._blend_strength,
        )

        if _CV2_AVAILABLE:
            softened = cv2.bilateralFilter(
                overlay_rgb,
                d=0,
                sigmaColor=26,
                sigmaSpace=18,
            )
            overlay_rgb = masked_blend(overlay_rgb, softened, target_mask, strength=0.28)

        return overlay_rgb, target_mask


class HairRefinementStage:
    def __init__(self, sharpen_amount: float):
        self._sharpen_amount = max(0.0, float(sharpen_amount))

    def run(
        self,
        source_rgb: "np.ndarray",
        shaped_and_colored_rgb: "np.ndarray",
        target_mask: "np.ndarray",
    ) -> "np.ndarray":
        refined = shaped_and_colored_rgb.copy()
        smooth_mask = gaussian_soft_mask(target_mask, 41)

        enhanced = apply_clahe(refined, clip_limit=2.2)
        enhanced = apply_unsharp_mask(enhanced, amount=self._sharpen_amount, sigma=1.05)

        refined = masked_blend(refined, enhanced, smooth_mask, strength=0.34)
        refined = masked_blend(source_rgb, refined, smooth_mask, strength=0.94)
        return refined


class HairInferencePipeline:
    def __init__(self, settings):
        self._validator = HairInputValidator(settings.MAX_FILE_SIZE)
        self._preprocessor = HairPreprocessor(settings.HAIR_TRANSFER_MAX_EDGE)
        self._aligner = HairPoseAligner()
        self._shape_stage = HairShapeTransferStage(settings.HAIR_TRANSFER_BLEND_STRENGTH)
        self._color_stage = HairColorTransferStage(settings.HAIR_TRANSFER_COLOR_STRENGTH)
        self._refine_stage = HairRefinementStage(settings.HAIR_TRANSFER_SHARPEN_AMOUNT)

    def run(
        self,
        source_image_bytes: bytes,
        shape_reference_bytes: bytes,
        color_reference_bytes: bytes,
    ) -> bytes:
        for label, image_bytes in (
            ("Source", source_image_bytes),
            ("Shape reference", shape_reference_bytes),
            ("Color reference", color_reference_bytes),
        ):
            self._validator.ensure_image(image_bytes, label)

        source = self._preprocessor.prepare(source_image_bytes, "Source")
        shape_reference = self._preprocessor.prepare(shape_reference_bytes, "Shape reference")
        color_reference = self._preprocessor.prepare(color_reference_bytes, "Color reference")

        return self.runPrepared(
            source=source,
            shape_reference=shape_reference,
            color_reference=color_reference,
        )

    def runPrepared(
        self,
        source: PreparedHairImage,
        shape_reference: PreparedHairImage,
        color_reference: PreparedHairImage,
    ) -> bytes:
        aligned_shape_rgb, aligned_shape_mask = self._aligner.align(source, shape_reference)
        aligned_color_rgb, aligned_color_mask = self._aligner.align(source, color_reference)

        shaped_rgb, target_mask = self._shape_stage.run(source, aligned_shape_rgb, aligned_shape_mask)
        colored_rgb = self._color_stage.run(shaped_rgb, target_mask, aligned_color_rgb, aligned_color_mask)
        refined_rgb = self._refine_stage.run(source.rgb, colored_rgb, target_mask)

        return encode_image_bytes(refined_rgb, image_format="PNG")


class HairstyleTryOnService:
    def __init__(self):
        if not _CV2_AVAILABLE:
            raise ProcessingError(
                "OpenCV is required for hairstyle generation but is not available.",
                "HAIRSTYLE_DEPENDENCY_ERROR",
            )

        self.settings = get_settings()
        self._project_root = Path(__file__).resolve().parents[3]
        self._preset_dir = self._project_root / "public" / "hairstyles"
        self._validator = HairInputValidator(self.settings.MAX_FILE_SIZE)
        self._preprocessor = HairPreprocessor(self.settings.HAIR_TRANSFER_MAX_EDGE)
        self._aligner = HairPoseAligner()
        self._preset_aligner = HairPresetAssetAligner()
        self._colorize_preset = HairPaletteColorStage()
        self._overlay_stage = HairPresetOverlayStage(self.settings.HAIRSTYLE_STRENGTH)
        self._refine_stage = HairRefinementStage(max(0.6, self.settings.HAIR_TRANSFER_SHARPEN_AMOUNT))
        self._pipeline = HairInferencePipeline(self.settings)
        self._preset_cache: dict[str, PreparedHairImage] = {}
        self._subjectSegmenter = U2NetSegmentationModel()
        self._mobileSam = MobileSamService()
        self._subjectMaskCache: dict[str, "np.ndarray"] = {}

    def listPresets(self) -> list[dict]:
        # Shape overlays are intentionally disabled in the active product flow.
        return []

    def listColorOptions(self) -> list[dict]:
        return [
            {
                "id": color.id,
                "label": color.label,
                "swatch": color.swatch,
            }
            for color in HAIR_COLOR_OPTIONS
        ]

    def generateHairstyle(
        self,
        image_bytes: bytes,
        style_id: str,
        hair_color: str,
        user_mask_b64: str | None = None,
        brush_size: int | None = None,
    ) -> bytes:
        logger.info("Running source-hair recolor color=%s", hair_color)
        try:
            self._validator.ensure_image(image_bytes, "Source")
            source = self._preprocessor.prepare(image_bytes, "Source")
            color_spec = self._resolveColor(hair_color)
            target_mask = self._build_source_recolor_mask(
                source,
                image_bytes,
                user_mask_b64=user_mask_b64,
                brush_size=brush_size,
            )
            recolored_rgb = self._colorize_preset.run(source.rgb.copy(), target_mask, color_spec)

            if _CV2_AVAILABLE:
                softened = cv2.bilateralFilter(
                    recolored_rgb,
                    d=0,
                    sigmaColor=18,
                    sigmaSpace=12,
                )
                recolored_rgb = masked_blend(recolored_rgb, softened, target_mask, strength=0.18)

            refined_rgb = self._refine_stage.run(source.rgb, recolored_rgb, target_mask)
            return encode_image_bytes(refined_rgb, image_format="PNG")
        except ValidationError:
            raise
        except Exception as exc:
            logger.error("Hair recolor generation failed: %s", exc, exc_info=True)
            raise ProcessingError(
                "Hair recolor failed. Try a portrait-style image and another color.",
                "HAIRSTYLE_GENERATION_FAILED",
            ) from exc

    def generateHairTransfer(
        self,
        source_image_bytes: bytes,
        shape_reference_bytes: bytes,
        color_reference_bytes: bytes,
    ) -> bytes:
        logger.info("Running legacy 3-input hair transfer pipeline")
        try:
            for label, image_bytes in (
                ("Source", source_image_bytes),
                ("Shape reference", shape_reference_bytes),
                ("Color reference", color_reference_bytes),
            ):
                self._validator.ensure_image(image_bytes, label)

            remote_url = (self.settings.REMOTE_INFERENCE_URL or "").strip()
            if remote_url:
                try:
                    return self._run_remote_hairfastgan_swap(
                        source_image_bytes=source_image_bytes,
                        shape_reference_bytes=shape_reference_bytes,
                        color_reference_bytes=color_reference_bytes,
                    )
                except Exception as exc:
                    logger.warning("Remote HairFastGAN swap failed, falling back to local pipeline: %s", exc)

            source = self._preprocessor.prepare(source_image_bytes, "Source")
            shape_reference = self._preprocessor.prepare(shape_reference_bytes, "Shape reference")
            color_reference = self._preprocessor.prepare(color_reference_bytes, "Color reference")

            return self._pipeline.runPrepared(
                source=source,
                shape_reference=shape_reference,
                color_reference=color_reference,
            )
        except ValidationError:
            raise
        except Exception as exc:
            logger.error("Hair transfer pipeline failed: %s", exc, exc_info=True)
            raise ProcessingError(
                "Hair transfer failed. Make sure all three images are portrait-friendly inputs and try again.",
                "HAIR_TRANSFER_FAILED",
            ) from exc

    def _run_remote_hairfastgan_swap(
        self,
        source_image_bytes: bytes,
        shape_reference_bytes: bytes,
        color_reference_bytes: bytes,
    ) -> bytes:
        remote_base = (self.settings.REMOTE_INFERENCE_URL or "").strip().rstrip("/")
        endpoint = f"{remote_base}/v1/hairfastgan/swap"

        headers: dict[str, str] = {}
        api_key = (self.settings.REMOTE_INFERENCE_API_KEY or "").strip()
        if api_key:
            headers["X-API-Key"] = api_key

        data = {"align": "true"}
        files = {
            "face_image": ("face", source_image_bytes, "application/octet-stream"),
            "shape_image": ("shape", shape_reference_bytes, "application/octet-stream"),
            "color_image": ("color", color_reference_bytes, "application/octet-stream"),
        }

        import httpx

        read_timeout = float(getattr(self.settings, "REMOTE_INFERENCE_HAIRFASTGAN_TIMEOUT_SECONDS", 300.0) or 300.0)
        timeout = httpx.Timeout(read_timeout, connect=10.0)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, data=data, files=files, headers=headers)
            response.raise_for_status()
            return response.content

    def _resolveColor(self, color_id: str | None) -> HairColorSpec:
        resolved_id = (color_id or DEFAULT_HAIR_COLOR_ID).strip().lower()
        for color in HAIR_COLOR_OPTIONS:
            if color.id == resolved_id:
                return color
        raise ValidationError("Selected hair color is not available.", "UNKNOWN_HAIR_COLOR")

    def _build_source_recolor_mask(
        self,
        source: PreparedHairImage,
        image_bytes: bytes,
        user_mask_b64: str | None = None,
        brush_size: int | None = None,
    ) -> "np.ndarray":
        detected_mask = np.where(source.hair_mask > 18, 255, 0).astype(np.uint8)
        height, width = detected_mask.shape

        user_seed_mask = self._decode_user_mask(user_mask_b64, width, height)
        if user_seed_mask is not None and int(user_seed_mask.max()) > 0:
            # El titremelerini engellemek için düzleştirme ve ovalleştirme (Smoothing & Rounding)
            base_kernel_size = 19
            if brush_size is not None and brush_size > 0:
                base_kernel_size = min(35, max(5, int(brush_size * 1.5)))
                if base_kernel_size % 2 == 0:
                    base_kernel_size += 1
            
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (base_kernel_size, base_kernel_size))
            
            smoothed_mask = cv2.morphologyEx(
                user_seed_mask,
                cv2.MORPH_CLOSE,
                kernel,
                iterations=2,
            )
            smoothed_mask = cv2.morphologyEx(
                smoothed_mask,
                cv2.MORPH_OPEN,
                kernel,
                iterations=2,
            )
            
            base_mask = cv2.dilate(
                smoothed_mask,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                iterations=1,
            )
            return gaussian_soft_mask(base_mask, 21)

        subject_mask = self._get_subject_mask(
            image_bytes=image_bytes,
            width=width,
            height=height,
        )
        
        # Build head ROI based on face landmarks
        head_roi = self._build_head_roi(source.face_box, width, height)
        
        # Face core mask (skin area to exclude)
        face_core = self._build_face_core_mask(source, width, height)
        
        # Primary Strategy: Use MobileSAM if available and has landmarks
        if source.analysis is not None and source.analysis.points is not None:
            try:
                # Get high-precision hair mask from MobileSAM
                sam_mask = self._mobileSam.predict_hair_mask(source.rgb, source.analysis.points)
                if int(sam_mask.max()) > 0:
                    # Apply ROI and clean up skin bleed
                    if face_core is not None:
                        sam_mask = cv2.subtract(sam_mask, face_core)
                    
                    # ROI removed to let the model handle full length hair
                    # sam_mask = cv2.bitwise_and(sam_mask, head_roi)
                    
                    # Small morphological closing to fill gaps in strands
                    sam_mask = cv2.morphologyEx(
                        sam_mask,
                        cv2.MORPH_CLOSE,
                        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                    )
                    
                    return gaussian_soft_mask(sam_mask, 15)
            except Exception as e:
                logger.warning("MobileSAM masking failed, falling back to hybrid: %s", e)

        # Secondary Strategy: Use MobileSAM prompts derived from face box when landmarks are missing
        try:
            sam_mask = self._mobileSam.predict_hair_mask_from_face_box(source.rgb, source.face_box)
            if int(sam_mask.max()) > 0:
                if face_core is not None:
                    sam_mask = cv2.subtract(sam_mask, face_core)

                sam_mask = cv2.morphologyEx(
                    sam_mask,
                    cv2.MORPH_CLOSE,
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                )

                return gaussian_soft_mask(sam_mask, 15)
        except Exception as e:
            logger.warning("MobileSAM face-box masking failed, falling back to hybrid: %s", e)

        # Hybrid Strategy (Fallback):
        # 1. If we have a subject mask, use it as the main boundary.
        # 2. Subtract the face core from it.
        # 3. Intersect with head ROI to remove body/background.
        if subject_mask is not None:
            # Start with subject (person) mask
            base_candidate = subject_mask.copy()
            
            # Remove face
            if face_core is not None:
                base_candidate = cv2.subtract(base_candidate, face_core)
            
            # Keep only head area
            base_candidate = cv2.bitwise_and(base_candidate, head_roi)
            
            # Clean up
            base_candidate = cv2.morphologyEx(
                base_candidate,
                cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
            )
            
            detected_mask = base_candidate
        else:
            # Fallback to ellipse-based if U2Net fails
            detected_mask = cv2.bitwise_and(detected_mask, head_roi)
            if face_core is not None:
                detected_mask = cv2.subtract(detected_mask, face_core)
        
        base_mask = detected_mask.copy()
        auto_seed_mask = self._build_hair_seed_mask(source, detected_mask)
        
        if int(auto_seed_mask.max()) > 0:
            # Refine using color/spatial awareness (GrabCut)
            refined_mask = self._refine_seeded_hair_mask(
                source.rgb,
                detected_mask,
                auto_seed_mask,
            )
            if int(refined_mask.max()) > 0:
                base_mask = refined_mask

        base_mask = cv2.morphologyEx(
            base_mask,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
            iterations=1,
        )
        base_mask = cv2.dilate(
            base_mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
            iterations=1,
        )

        return gaussian_soft_mask(base_mask, 21)

    def get_hair_mask(self, image_bytes: bytes) -> "np.ndarray":
        """
        API for human-in-the-loop flow: returns the raw MobileSAM hair mask.
        """
        source = self._preprocessor.prepare(image_bytes, "Source")
        height, width = source.rgb.shape[:2]
        
        # Face core mask (skin area to exclude)
        face_core = self._build_face_core_mask(source, width, height)
        
        if source.analysis is not None and source.analysis.points is not None:
            try:
                sam_mask = self._mobileSam.predict_hair_mask(source.rgb, source.analysis.points)
                if int(sam_mask.max()) > 0:
                    if face_core is not None:
                        sam_mask = cv2.subtract(sam_mask, face_core)
                    
                    sam_mask = cv2.morphologyEx(
                        sam_mask,
                        cv2.MORPH_CLOSE,
                        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                    )
                    return sam_mask
            except Exception as e:
                logger.warning("MobileSAM masking failed in get_hair_mask: %s", e)

        try:
            sam_mask = self._mobileSam.predict_hair_mask_from_face_box(source.rgb, source.face_box)
            if int(sam_mask.max()) > 0:
                if face_core is not None:
                    sam_mask = cv2.subtract(sam_mask, face_core)

                sam_mask = cv2.morphologyEx(
                    sam_mask,
                    cv2.MORPH_CLOSE,
                    cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                )
                return sam_mask
        except Exception as e:
            logger.warning("MobileSAM face-box masking failed in get_hair_mask: %s", e)
        
        # Fallback to subject mask
        subject_mask = self._get_subject_mask(image_bytes, width, height)
        if subject_mask is not None:
            if face_core is not None:
                subject_mask = cv2.subtract(subject_mask, face_core)
            # Use generous ROI for fallback
            head_roi = self._build_head_roi(source.face_box, width, height)
            return cv2.bitwise_and(subject_mask, head_roi)
            
        return np.zeros((height, width), dtype=np.uint8)

    def _build_face_core_mask(
        self,
        source: PreparedHairImage,
        width: int,
        height: int,
    ) -> "np.ndarray | None":
        if source.analysis is not None:
            face_core = cv2.subtract(source.analysis.faceMask, source.analysis.foreheadMask)
            return cv2.erode(
                np.where(face_core > 24, 255, 0).astype(np.uint8),
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)),
                iterations=1,
            )

        x0, y0, x1, y1 = source.face_box
        face_w = max(1, x1 - x0)
        face_h = max(1, y1 - y0)
        if face_w < 8 or face_h < 8:
            return None

        face_core = np.zeros((height, width), dtype=np.uint8)
        center = (
            int((x0 + x1) / 2),
            int(y0 + face_h * 0.58),
        )
        axes = (
            max(16, int(face_w * 0.34)),
            max(20, int(face_h * 0.36)),
        )
        cv2.ellipse(face_core, center, axes, 0, 0, 360, 255, -1)
        return face_core

    def _decode_user_mask(
        self,
        user_mask_b64: str | None,
        width: int,
        height: int,
    ) -> "np.ndarray | None":
        if not user_mask_b64 or not isinstance(user_mask_b64, str):
            return None

        try:
            raw_mask = user_mask_b64
            if raw_mask.startswith("data:image"):
                raw_mask = raw_mask.split(",", 1)[1]

            decoded = base64.b64decode(raw_mask)
            with PILImage.open(io.BytesIO(decoded)) as mask_image:
                mask = mask_image.convert("L")
                if mask.size != (width, height):
                    mask = mask.resize((width, height), PILImage.Resampling.LANCZOS)

            mask_np = np.array(mask, dtype=np.uint8)
            mask_np = np.where(mask_np > 32, 255, 0).astype(np.uint8)
            if int(mask_np.max()) == 0:
                return None

            return cv2.morphologyEx(
                mask_np,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
                iterations=1,
            )
        except Exception as exc:
            logger.warning("Hair recolor brush mask could not be decoded: %s", exc)
            return None

    def _build_head_roi(
        self,
        face_box: tuple[int, int, int, int],
        width: int,
        height: int,
    ) -> "np.ndarray":
        x0, y0, x1, y1 = face_box
        face_w = max(1, x1 - x0)
        face_h = max(1, y1 - y0)

        roi = np.zeros((height, width), dtype=np.uint8)
        # Head ROI should cover from the top of the head down to the shoulders/chest
        top = max(0, int(y0 - face_h * 1.2))
        bottom = min(height, int(y1 + face_h * 1.6)) # Extended significantly for long hair
        left = max(0, int(x0 - face_w * 0.8)) # Slightly wider too
        right = min(width, int(x1 + face_w * 0.8))
        roi[top:bottom, left:right] = 255
        
        return roi

    def _build_hair_seed_mask(
        self,
        source: PreparedHairImage,
        candidate_mask: "np.ndarray",
    ) -> "np.ndarray":
        height, width = candidate_mask.shape
        x0, y0, x1, y1 = source.face_box
        face_w = max(1, x1 - x0)
        face_h = max(1, y1 - y0)

        seed_region = np.zeros((height, width), dtype=np.uint8)
        seed_left = max(0, int(x0 + face_w * 0.12))
        seed_right = min(width, int(x1 - face_w * 0.12))
        seed_top = max(0, int(y0 - face_h * 0.42))
        seed_bottom = min(height, int(y0 + face_h * 0.08))
        seed_region[seed_top:seed_bottom, seed_left:seed_right] = 255

        seed_mask = cv2.bitwise_and(candidate_mask, seed_region)
        if int(seed_mask.max()) == 0:
            fallback_top = max(0, int(y0 - face_h * 0.55))
            fallback_bottom = min(height, int(y0 + face_h * 0.18))
            fallback = np.zeros((height, width), dtype=np.uint8)
            fallback[fallback_top:fallback_bottom, seed_left:seed_right] = 255
            seed_mask = cv2.bitwise_and(candidate_mask, fallback)

        return cv2.dilate(
            seed_mask,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
            iterations=1,
        )

    def _build_hair_color_mask(
        self,
        rgb: "np.ndarray",
        candidate_mask: "np.ndarray",
        seed_mask: "np.ndarray",
    ) -> "np.ndarray":
        seed_pixels = rgb[seed_mask > 0]
        if len(seed_pixels) < 12:
            return candidate_mask.copy()

        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        seed_lab = lab[seed_mask > 0]
        seed_mean = seed_lab.mean(axis=0)
        seed_std = np.clip(seed_lab.std(axis=0), 1.0, None)
        tolerance = np.array(
            [
                max(16.0, seed_std[0] * 2.3 + 10.0),
                max(10.0, seed_std[1] * 2.1 + 8.0),
                max(10.0, seed_std[2] * 2.1 + 8.0),
            ],
            dtype=np.float32,
        )

        delta = np.abs(lab - seed_mean[None, None, :])
        match = np.all(delta <= tolerance[None, None, :], axis=2)
        match = np.where(match & (candidate_mask > 0), 255, 0).astype(np.uint8)

        if int(match.max()) == 0:
            return candidate_mask.copy()

        return cv2.morphologyEx(
            match,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
            iterations=1,
        )

    def _refine_seeded_hair_mask(
        self,
        rgb: "np.ndarray",
        candidate_mask: "np.ndarray",
        seed_mask: "np.ndarray",
        brush_size: int | None = None,
    ) -> "np.ndarray":
        """
        Refines the hair mask using cv2.grabCut for higher precision.
        Uses the candidate_mask (U2Net + ROI) as probable foreground and 
        seed_mask as definite foreground.
        """
        if not _CV2_AVAILABLE or int(seed_mask.max()) == 0:
            return candidate_mask.copy()

        height, width = candidate_mask.shape
        
        # GrabCut setup
        mask = np.zeros((height, width), dtype=np.uint8)
        
        # 1. Mark Probable Background (outside our candidate area)
        mask.fill(cv2.GC_BGD)
        
        # 2. Mark Probable Foreground (inside our candidate area)
        mask[candidate_mask > 0] = cv2.GC_PR_FGD
        
        # 3. Mark Definite Foreground (inside our seed area)
        # We dilate the seed slightly to be more confident
        seed_dilated = cv2.dilate(
            seed_mask, 
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        )
        mask[seed_dilated > 0] = cv2.GC_FGD
        
        # 4. GrabCut execution
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)
        
        # Use a rect that covers the candidate area
        y_indices, x_indices = np.where(candidate_mask > 0)
        if len(y_indices) == 0:
            return candidate_mask.copy()
            
        rect = (
            int(x_indices.min()), 
            int(y_indices.min()), 
            int(x_indices.max() - x_indices.min()), 
            int(y_indices.max() - y_indices.min())
        )
        
        try:
            cv2.grabCut(rgb, mask, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_MASK)
            
            # Create final mask (keep definite and probable foreground)
            final_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)
            
            # Post-process for smoothness
            final_mask = cv2.morphologyEx(
                final_mask,
                cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
            )
            return final_mask
        except Exception as e:
            logger.warning("GrabCut refinement failed, falling back to iterative color growing: %s", e)
            # Fallback to the old color-growing logic if GrabCut fails
            return self._grow_hair_mask_from_seed(rgb, candidate_mask, seed_mask, brush_size)

    def _build_brush_guided_hair_mask(
        self,
        rgb: "np.ndarray",
        candidate_mask: "np.ndarray",
        user_seed_mask: "np.ndarray",
        brush_size: int | None = None,
    ) -> "np.ndarray":
        clipped_seed = cv2.bitwise_and(candidate_mask, user_seed_mask)
        if int(clipped_seed.max()) == 0:
            clipped_seed = user_seed_mask.copy()

        guided_mask = self._refine_seeded_hair_mask(
            rgb,
            candidate_mask,
            clipped_seed,
            brush_size=brush_size,
        )
        if int(guided_mask.max()) == 0:
            return guided_mask

        return cv2.bitwise_or(guided_mask, clipped_seed)

    def _grow_hair_mask_from_seed(
        self,
        rgb: "np.ndarray",
        candidate_mask: "np.ndarray",
        seed_mask: "np.ndarray",
        brush_size: int | None = None,
    ) -> "np.ndarray":
        region = cv2.bitwise_and(candidate_mask, seed_mask)
        if int(region.max()) == 0:
            return region

        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        kernel_size = max(3, min(11, ((int(brush_size or 12) // 10) * 2) + 3))
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))

        for step in range(6):
            region_indices = region > 0
            if int(region_indices.sum()) < 8:
                break

            frontier = cv2.dilate(region, kernel, iterations=1)
            frontier = cv2.bitwise_and(frontier, candidate_mask)
            frontier = cv2.subtract(frontier, region)
            frontier_indices = frontier > 0
            if not np.any(frontier_indices):
                break

            region_lab = lab[region_indices]
            region_mean = region_lab.mean(axis=0)
            region_std = np.clip(region_lab.std(axis=0), 1.0, None)
            tolerance = np.array(
                [
                    max(18.0, region_std[0] * 2.4 + 8.0 + (step * 2.0)),
                    max(12.0, region_std[1] * 2.2 + 7.0 + (step * 1.5)),
                    max(12.0, region_std[2] * 2.2 + 7.0 + (step * 1.5)),
                ],
                dtype=np.float32,
            )

            frontier_lab = lab[frontier_indices]
            accepted = np.all(
                np.abs(frontier_lab - region_mean[None, :]) <= tolerance[None, :],
                axis=1,
            )
            if not np.any(accepted):
                continue

            frontier_coords = np.argwhere(frontier_indices)
            accepted_mask = np.zeros_like(region)
            accepted_coords = frontier_coords[accepted]
            accepted_mask[accepted_coords[:, 0], accepted_coords[:, 1]] = 255
            region = cv2.bitwise_or(region, accepted_mask)

        region = cv2.morphologyEx(
            region,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
            iterations=1,
        )
        return self._keep_seed_connected_components(region, seed_mask)

    def _keep_seed_connected_components(
        self,
        candidate_mask: "np.ndarray",
        seed_mask: "np.ndarray",
    ) -> "np.ndarray":
        component_count, labels, stats, _ = cv2.connectedComponentsWithStats(candidate_mask, connectivity=8)
        if component_count <= 1:
            return candidate_mask

        seed_labels = {
            int(label)
            for label in np.unique(labels[seed_mask > 0])
            if int(label) > 0
        }
        if not seed_labels:
            return candidate_mask

        kept = np.zeros_like(candidate_mask)
        for label in seed_labels:
            if stats[label, cv2.CC_STAT_AREA] < 24:
                continue
            kept[labels == label] = 255
        return kept

    def _get_subject_mask(
        self,
        image_bytes: bytes,
        width: int,
        height: int,
    ) -> "np.ndarray | None":
        cache_key = hashlib.sha1(image_bytes).hexdigest()
        cached = self._subjectMaskCache.get(cache_key)
        if cached is not None:
            return cached.copy()

        try:
            if not self._subjectSegmenter.isLoaded():
                self._subjectSegmenter.loadModel()

            image = Image(
                imageId=f"hair-mask-{uuid.uuid4().hex[:8]}",
                rawData=image_bytes,
                format="png",
                size=len(image_bytes),
                width=width,
                height=height,
            )
            generated = self._subjectSegmenter.generateMask(image).maskData
            if generated.shape != (height, width):
                generated = cv2.resize(generated, (width, height), interpolation=cv2.INTER_LINEAR)

            subject_mask = np.where(generated > 20, 255, 0).astype(np.uint8)
            subject_mask = cv2.morphologyEx(
                subject_mask,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
                iterations=1,
            )
            self._subjectMaskCache[cache_key] = subject_mask.copy()
            if len(self._subjectMaskCache) > 8:
                oldest_key = next(iter(self._subjectMaskCache))
                self._subjectMaskCache.pop(oldest_key, None)
            return subject_mask
        except Exception as exc:
            logger.warning("Subject mask helper unavailable for hair recolor: %s", exc)
            return None
