"""
MobileSAM-based high-precision segmentation service.
"""

from __future__ import annotations

import io
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image as PILImage

try:
    import torch

    _TORCH_AVAILABLE = True
except ImportError:  # pragma: no cover
    torch = None
    _TORCH_AVAILABLE = False

try:
    from mobile_sam import sam_model_registry, SamPredictor
    _MOBILE_SAM_AVAILABLE = True
except ImportError:
    _MOBILE_SAM_AVAILABLE = False

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class MobileSamService:
    def __init__(self):
        self.settings = get_settings()
        self.device = self.settings.DEVICE
        self.model_type = "vit_t"
        
        # Path to mobile_sam.pt
        self.model_path = Path(__file__).resolve().parents[3] / "models" / "mobile_sam.pt"
        self._predictor: Optional[SamPredictor] = None
        self._loaded = False

    def load_model(self):
        if self._loaded:
            return
        
        if not _MOBILE_SAM_AVAILABLE:
            logger.error("MobileSAM library not installed.")
            return

        if not self.model_path.exists():
            logger.error(f"MobileSAM weights not found at {self.model_path}")
            return

        try:
            sam = sam_model_registry[self.model_type](checkpoint=str(self.model_path))
            sam.to(device=self.device)
            sam.eval()
            self._predictor = SamPredictor(sam)
            self._loaded = True
            logger.info(f"MobileSAM model loaded on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load MobileSAM: {e}")

    def _remoteConfigured(self) -> bool:
        return bool((self.settings.REMOTE_INFERENCE_URL or "").strip())

    def _build_hair_prompts_from_face_box(
        self,
        face_box: tuple[int, int, int, int],
        width: int,
        height: int,
    ) -> tuple[list[list[float]], list[int]]:
        x0, y0, x1, y1 = (int(face_box[0]), int(face_box[1]), int(face_box[2]), int(face_box[3]))
        x0 = max(0, min(width - 1, x0))
        x1 = max(0, min(width - 1, x1))
        y0 = max(0, min(height - 1, y0))
        y1 = max(0, min(height - 1, y1))

        face_w = float(max(1, x1 - x0))
        face_h = float(max(1, y1 - y0))
        center_x = float((x0 + x1) / 2.0)

        def clamp_point(x: float, y: float) -> list[float]:
            return [float(max(0, min(width - 1, x))), float(max(0, min(height - 1, y)))]

        # Positives: above the forehead and around the head/hair silhouette.
        pt_hair_top = clamp_point(center_x, y0 - face_h * 0.22)
        pt_hair_l = clamp_point(x0 + face_w * 0.22, y0 - face_h * 0.12)
        pt_hair_r = clamp_point(x1 - face_w * 0.22, y0 - face_h * 0.12)

        pt_side_l = clamp_point(x0 - face_w * 0.10, y0 + face_h * 0.30)
        pt_side_r = clamp_point(x1 + face_w * 0.10, y0 + face_h * 0.30)

        pt_low_l = clamp_point(x0 - face_w * 0.14, y0 + face_h * 0.90)
        pt_low_r = clamp_point(x1 + face_w * 0.14, y0 + face_h * 0.90)

        # Negatives: face interior (eyes/nose/mouth) to reduce skin bleeding.
        pt_nose = clamp_point(center_x, y0 + face_h * 0.58)
        pt_eye_l = clamp_point(x0 + face_w * 0.34, y0 + face_h * 0.40)
        pt_eye_r = clamp_point(x0 + face_w * 0.66, y0 + face_h * 0.40)
        pt_mouth = clamp_point(center_x, y0 + face_h * 0.76)

        input_points = [
            pt_hair_top,
            pt_hair_l,
            pt_hair_r,
            pt_side_l,
            pt_side_r,
            pt_low_l,
            pt_low_r,
            pt_nose,
            pt_eye_l,
            pt_eye_r,
            pt_mouth,
            [0.0, 0.0],
            [float(width - 1), 0.0],
        ]
        input_labels = [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0]

        return input_points, input_labels

    def _build_prompts(
        self,
        face_landmarks: np.ndarray,
        width: int,
        height: int,
        mode: str,
    ) -> tuple[list[list[float]], list[int]]:
        x_min, y_min = face_landmarks.min(axis=0)
        x_max, y_max = face_landmarks.max(axis=0)
        face_w = float(x_max - x_min)
        face_h = float(y_max - y_min)

        def pt(value: object) -> list[float]:
            as_array = np.asarray(value, dtype=np.float32).reshape(-1)
            if as_array.size < 2:
                return [0.0, 0.0]
            return [float(as_array[0]), float(as_array[1])]

        input_points: list[list[float]] = []
        input_labels: list[int] = []

        if mode == "hair":
            pt_forehead_top = pt(face_landmarks[10])
            pt_forehead_l = pt(face_landmarks[109])
            pt_forehead_r = pt(face_landmarks[338])

            pt_hair_top = [pt_forehead_top[0], float(max(0, pt_forehead_top[1] - int(face_h * 0.15)))]
            pt_hair_l = [pt_forehead_l[0], float(max(0, pt_forehead_l[1] - int(face_h * 0.10)))]
            pt_hair_r = [pt_forehead_r[0], float(max(0, pt_forehead_r[1] - int(face_h * 0.10)))]

            pt_side_l = [float(max(0, x_min - int(face_w * 0.05))), float(int(y_min + face_h * 0.30))]
            pt_side_r = [float(min(width - 1, x_max + int(face_w * 0.05))), float(int(y_min + face_h * 0.30))]

            pt_low_l = [float(max(0, x_min - int(face_w * 0.10))), float(int(y_min + face_h * 0.80))]
            pt_low_r = [float(min(width - 1, x_max + int(face_w * 0.10))), float(int(y_min + face_h * 0.80))]

            input_points = [
                pt_hair_top,
                pt_hair_l,
                pt_hair_r,
                pt_side_l,
                pt_side_r,
                pt_low_l,
                pt_low_r,
                pt(face_landmarks[1]),
                pt(face_landmarks[33]),
                pt(face_landmarks[362]),
                pt(face_landmarks[17]),
            ]
            input_labels = [1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0]

            input_points.extend([[0.0, 0.0], [float(width - 1), 0.0]])
            input_labels.extend([0, 0])
        else:
            pt_forehead = [float(int(x_min + face_w * 0.50)), float(int(y_min + face_h * 0.10))]
            pt_top_head = [float(int(x_min + face_w * 0.50)), float(int(y_min - face_h * 0.10))]
            input_points = [
                pt_forehead,
                pt(face_landmarks[1]),
                pt(face_landmarks[152]),
                pt(face_landmarks[234]),
                pt(face_landmarks[454]),
                pt_top_head,
            ]
            input_labels = [1, 1, 1, 1, 1, 1]

            pt_bg1 = [
                float(max(0, int(x_min - face_w * 0.50))),
                float(max(0, int(y_min - face_h * 0.50))),
            ]
            pt_bg2 = [
                float(min(width - 1, int(x_max + face_w * 0.50))),
                float(max(0, int(y_min - face_h * 0.50))),
            ]
            input_points.extend([pt_bg1, pt_bg2])
            input_labels.extend([0, 0])

        return input_points, input_labels

    def _predict_mask_with_points(
        self,
        image_rgb: np.ndarray,
        input_points: list[list[float]],
        input_labels: list[int],
        mode: str,
    ) -> np.ndarray:
        height, width = image_rgb.shape[:2]

        if self._remoteConfigured():
            try:
                return self._predict_remote_mask(image_rgb, input_points, input_labels)
            except Exception as exc:
                logger.warning("Remote SAM masking failed, falling back to MobileSAM: %s", exc)

        if not self._loaded:
            self.load_model()

        if self._predictor is None:
            return np.zeros((height, width), dtype=np.uint8)

        self._predictor.set_image(image_rgb)

        try:
            masks, scores, _logits = self._predictor.predict(
                point_coords=np.array(input_points, dtype=np.float32),
                point_labels=np.array(input_labels, dtype=np.int32),
                multimask_output=True,
            )
            best_idx = int(np.argmax(scores)) if scores is not None else 0
            mask = (masks[best_idx] * 255).astype(np.uint8)
            return mask
        except Exception as exc:
            logger.error("MobileSAM prediction failed (%s): %s", mode, exc)
            return np.zeros((height, width), dtype=np.uint8)

    def _predict_remote_mask(
        self,
        image_rgb: np.ndarray,
        input_points: list[list[float]],
        input_labels: list[int],
    ) -> np.ndarray:
        remote_base = (self.settings.REMOTE_INFERENCE_URL or "").strip().rstrip("/")
        endpoint = f"{remote_base}/v1/sam/predict"

        with PILImage.fromarray(image_rgb, mode="RGB") as pil_image:
            buf = io.BytesIO()
            pil_image.save(buf, format="PNG")
            image_bytes = buf.getvalue()

        headers: dict[str, str] = {}
        api_key = (self.settings.REMOTE_INFERENCE_API_KEY or "").strip()
        if api_key:
            headers["X-API-Key"] = api_key

        data = {
            "point_coords": json.dumps(input_points),
            "point_labels": json.dumps(input_labels),
            "multimask_output": "true",
        }

        try:
            import httpx

            read_timeout = float(getattr(self.settings, "REMOTE_INFERENCE_SAM_TIMEOUT_SECONDS", 60.0) or 60.0)
            timeout = httpx.Timeout(read_timeout, connect=10.0)
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    endpoint,
                    data=data,
                    files={"image": ("image.png", image_bytes, "image/png")},
                    headers=headers,
                )
                response.raise_for_status()
        except Exception as exc:
            raise RuntimeError(f"remote SAM request failed: {exc}") from exc

        try:
            with PILImage.open(io.BytesIO(response.content)) as mask_image:
                mask = mask_image.convert("L")
                if mask.size != (image_rgb.shape[1], image_rgb.shape[0]):
                    mask = mask.resize((image_rgb.shape[1], image_rgb.shape[0]), PILImage.Resampling.NEAREST)
                return np.array(mask, dtype=np.uint8)
        except Exception as exc:
            raise RuntimeError(f"remote SAM response decode failed: {exc}") from exc

    def predict_hair_mask(
        self, 
        image_rgb: np.ndarray, 
        face_landmarks: np.ndarray
    ) -> np.ndarray:
        """
        Uses MobileSAM to segment hair based on face landmark prompts.
        """
        return self._predict_mask_with_prompts(image_rgb, face_landmarks, mode="hair")

    def predict_hair_mask_from_face_box(
        self,
        image_rgb: np.ndarray,
        face_box: tuple[int, int, int, int],
    ) -> np.ndarray:
        """
        Hair segmentation fallback when face landmarks are unavailable.
        """
        height, width = image_rgb.shape[:2]
        input_points, input_labels = self._build_hair_prompts_from_face_box(face_box, width, height)
        return self._predict_mask_with_points(image_rgb, input_points, input_labels, mode="hair(face_box)")

    def predict_portrait_mask(
        self,
        image_rgb: np.ndarray,
        face_landmarks: np.ndarray
    ) -> np.ndarray:
        """
        Uses MobileSAM to segment the entire face/forehead area for aging.
        """
        return self._predict_mask_with_prompts(image_rgb, face_landmarks, mode="portrait")

    def _predict_mask_with_prompts(
        self,
        image_rgb: np.ndarray,
        face_landmarks: np.ndarray,
        mode: str = "hair"
    ) -> np.ndarray:
        height, width = image_rgb.shape[:2]
        if mode not in {"hair", "portrait"}:
            mode = "hair"

        input_points, input_labels = self._build_prompts(
            face_landmarks=face_landmarks,
            width=width,
            height=height,
            mode=mode,
        )
        return self._predict_mask_with_points(image_rgb, input_points, input_labels, mode=mode)
