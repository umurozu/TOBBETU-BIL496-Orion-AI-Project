"""
Shared portrait-aware image processing helpers.

Provides:
    - lazy face landmark detection through MediaPipe
    - reusable portrait masks (face, skin, eyes, mouth, forehead, under-eye)
    - deterministic image blending helpers used by multiple AI models
"""

from __future__ import annotations

from dataclasses import dataclass
import io
import logging
from pathlib import Path
from typing import Optional, Sequence

from PIL import Image as PILImage

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    _CV2_AVAILABLE = False

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    _MEDIAPIPE_AVAILABLE = True
except ImportError:
    mp = None
    python = None
    vision = None
    _MEDIAPIPE_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class FaceAnalysis:
    points: "np.ndarray"
    faceMask: "np.ndarray"
    skinMask: "np.ndarray"
    eyeMask: "np.ndarray"
    mouthMask: "np.ndarray"
    foreheadMask: "np.ndarray"
    underEyeMask: "np.ndarray"


class PortraitLandmarker:
    """Process-wide singleton for face landmark detection."""

    _landmarker = None
    _loadAttempted = False

    @classmethod
    def isAvailable(cls) -> bool:
        if cls._loadAttempted:
            return cls._landmarker is not None

        cls._loadAttempted = True
        if not (_CV2_AVAILABLE and _MEDIAPIPE_AVAILABLE):
            logger.warning(
                "PortraitLandmarker unavailable because OpenCV or MediaPipe is missing"
            )
            return False

        model_path = Path(__file__).resolve().parents[3] / "models" / "face_landmarker.task"
        if not model_path.exists():
            logger.warning("PortraitLandmarker model not found at %s", model_path)
            return False

        try:
            base_options = python.BaseOptions(model_asset_path=str(model_path))
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                num_faces=1,
            )
            cls._landmarker = vision.FaceLandmarker.create_from_options(options)
            logger.info("PortraitLandmarker initialized from %s", model_path)
        except Exception as exc:
            logger.error("Failed to initialize PortraitLandmarker: %s", exc)
            cls._landmarker = None

        return cls._landmarker is not None

    @classmethod
    def detectPoints(cls, rgb_image: "np.ndarray") -> Optional["np.ndarray"]:
        if not cls.isAvailable():
            return None

        try:
            height, width = rgb_image.shape[:2]
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_image)
            result = cls._landmarker.detect(mp_image)
            if not result.face_landmarks:
                return None

            face = result.face_landmarks[0]
            return np.array(
                [[int(point.x * width), int(point.y * height)] for point in face],
                dtype=np.int32,
            )
        except Exception as exc:
            logger.error("Face landmark detection failed: %s", exc)
            return None


LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_BROW = [70, 63, 105, 66, 107]
RIGHT_BROW = [300, 293, 334, 296, 336]
MOUTH = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291]


def decode_image_bytes(image_bytes: bytes) -> PILImage.Image:
    return PILImage.open(io.BytesIO(image_bytes))


def pil_to_rgb_alpha(pil_image: PILImage.Image) -> tuple["np.ndarray", "np.ndarray"]:
    rgba = np.array(pil_image.convert("RGBA"))
    return rgba[:, :, :3].astype(np.uint8), rgba[:, :, 3].astype(np.uint8)


def encode_image_bytes(
    rgb_image: "np.ndarray",
    alpha_channel: Optional["np.ndarray"] = None,
    image_format: str = "PNG",
    quality: int = 95,
) -> bytes:
    if alpha_channel is not None:
        output = PILImage.fromarray(
            np.dstack([rgb_image, alpha_channel]).astype(np.uint8),
            mode="RGBA",
        )
    else:
        output = PILImage.fromarray(rgb_image.astype(np.uint8), mode="RGB")

    buffer = io.BytesIO()
    save_kwargs = {}
    if image_format.upper() in {"JPEG", "JPG", "WEBP"}:
        save_kwargs["quality"] = quality
    output.save(buffer, format=image_format.upper(), **save_kwargs)
    return buffer.getvalue()


def resize_rgb_alpha(
    rgb_image: "np.ndarray",
    alpha_channel: "np.ndarray",
    scale: float,
    max_edge: Optional[int] = None,
) -> tuple["np.ndarray", "np.ndarray"]:
    interpolation = cv2.INTER_LANCZOS4 if scale >= 1 else cv2.INTER_AREA
    height, width = rgb_image.shape[:2]
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))

    if max_edge:
        largest_edge = max(new_width, new_height)
        if largest_edge > max_edge:
            reduction = max_edge / float(largest_edge)
            new_width = max(1, int(round(new_width * reduction)))
            new_height = max(1, int(round(new_height * reduction)))

    resized_rgb = cv2.resize(rgb_image, (new_width, new_height), interpolation=interpolation)
    resized_alpha = cv2.resize(alpha_channel, (new_width, new_height), interpolation=interpolation)
    return resized_rgb.astype(np.uint8), resized_alpha.astype(np.uint8)


def gaussian_soft_mask(mask: "np.ndarray", blur_size: int) -> "np.ndarray":
    if blur_size <= 1:
        return mask.astype(np.uint8)
    kernel = blur_size if blur_size % 2 == 1 else blur_size + 1
    return cv2.GaussianBlur(mask.astype(np.uint8), (kernel, kernel), 0)


def masked_blend(
    base_rgb: "np.ndarray",
    effect_rgb: "np.ndarray",
    mask: "np.ndarray",
    strength: float = 1.0,
) -> "np.ndarray":
    mask_float = np.clip(mask.astype(np.float32) / 255.0, 0.0, 1.0)
    mask_float = (mask_float * float(strength))[:, :, None]
    blended = (base_rgb.astype(np.float32) * (1.0 - mask_float)) + (
        effect_rgb.astype(np.float32) * mask_float
    )
    return np.clip(blended, 0, 255).astype(np.uint8)


def apply_clahe(rgb_image: "np.ndarray", clip_limit: float = 2.0) -> "np.ndarray":
    lab = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=max(0.1, clip_limit), tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    return cv2.cvtColor(cv2.merge([l_channel, a_channel, b_channel]), cv2.COLOR_LAB2RGB)


def apply_unsharp_mask(
    rgb_image: "np.ndarray",
    amount: float = 1.0,
    sigma: float = 1.1,
) -> "np.ndarray":
    if amount <= 0:
        return rgb_image.copy()

    blurred = cv2.GaussianBlur(rgb_image, (0, 0), sigmaX=max(0.1, sigma))
    sharpened = cv2.addWeighted(
        rgb_image.astype(np.float32),
        1.0 + amount,
        blurred.astype(np.float32),
        -amount,
        0,
    )
    return np.clip(sharpened, 0, 255).astype(np.uint8)


def apply_saturation(rgb_image: "np.ndarray", delta: float) -> "np.ndarray":
    hsv = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * (1.0 + delta), 0, 255)
    return cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB)


def apply_temperature(rgb_image: "np.ndarray", warmth: float) -> "np.ndarray":
    rgb = rgb_image.astype(np.float32)
    rgb[:, :, 0] = np.clip(rgb[:, :, 0] + (warmth * 24.0), 0, 255)
    rgb[:, :, 2] = np.clip(rgb[:, :, 2] - (warmth * 18.0), 0, 255)
    return rgb.astype(np.uint8)


def apply_brightness_contrast(
    rgb_image: "np.ndarray",
    brightness: float = 0.0,
    contrast: float = 0.0,
) -> "np.ndarray":
    alpha = 1.0 + contrast
    beta = brightness * 255.0
    adjusted = cv2.convertScaleAbs(rgb_image, alpha=alpha, beta=beta)
    return adjusted.astype(np.uint8)


def _scaled_polygon(points: "np.ndarray", expand: float) -> "np.ndarray":
    if len(points) == 0:
        return points
    center = points.mean(axis=0)
    scaled = center + (points - center) * expand
    return scaled.astype(np.int32)


def polygon_mask(
    shape: tuple[int, int],
    points: "np.ndarray",
    indices: Optional[Sequence[int]] = None,
    expand: float = 1.0,
    blur_size: int = 0,
) -> "np.ndarray":
    mask = np.zeros(shape, dtype=np.uint8)
    polygon = points if indices is None else points[list(indices)]
    if polygon.size == 0:
        return mask

    polygon = _scaled_polygon(polygon.astype(np.float32), expand)
    hull = cv2.convexHull(polygon)
    cv2.fillConvexPoly(mask, hull, 255)
    return gaussian_soft_mask(mask, blur_size)


def analyze_portrait(rgb_image: "np.ndarray") -> Optional[FaceAnalysis]:
    if not _CV2_AVAILABLE:
        return None

    points = PortraitLandmarker.detectPoints(rgb_image)
    if points is None or len(points) == 0:
        return None

    shape = rgb_image.shape[:2]
    face_mask = polygon_mask(shape, points, expand=1.08, blur_size=41)

    eye_mask = cv2.bitwise_or(
        polygon_mask(shape, points, LEFT_EYE, expand=1.55, blur_size=25),
        polygon_mask(shape, points, RIGHT_EYE, expand=1.55, blur_size=25),
    )
    mouth_mask = polygon_mask(shape, points, MOUTH, expand=1.30, blur_size=25)
    brow_mask = cv2.bitwise_or(
        polygon_mask(shape, points, LEFT_BROW, expand=1.60, blur_size=21),
        polygon_mask(shape, points, RIGHT_BROW, expand=1.60, blur_size=21),
    )

    exclude_mask = cv2.max(eye_mask, mouth_mask)
    exclude_mask = cv2.max(exclude_mask, brow_mask)
    skin_mask = cv2.subtract(face_mask, exclude_mask)
    skin_mask = gaussian_soft_mask(skin_mask, 31)

    face_y_min = int(points[:, 1].min())
    brow_y = int(points[LEFT_BROW + RIGHT_BROW, 1].mean())
    eye_y = int(points[LEFT_EYE + RIGHT_EYE, 1].mean())
    face_y_max = int(points[:, 1].max())

    forehead_band = np.zeros(shape, dtype=np.uint8)
    forehead_top = max(0, face_y_min)
    forehead_bottom = max(forehead_top + 1, brow_y - max(6, (brow_y - face_y_min) // 8))
    forehead_band[forehead_top:forehead_bottom, :] = 255
    forehead_mask = cv2.bitwise_and(face_mask, forehead_band)
    forehead_mask = gaussian_soft_mask(forehead_mask, 31)

    under_eye_band = np.zeros(shape, dtype=np.uint8)
    band_height = max(10, int((face_y_max - face_y_min) * 0.12))
    band_top = min(shape[0], eye_y)
    band_bottom = min(shape[0], eye_y + band_height)
    under_eye_band[band_top:band_bottom, :] = 255
    dilated_eyes = cv2.dilate(
        eye_mask,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (17, 17)),
        iterations=1,
    )
    under_eye_mask = cv2.bitwise_and(dilated_eyes, under_eye_band)
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
