from __future__ import annotations

import logging
import sys
from pathlib import Path
from threading import Lock

from app.ai.portrait_processing import decode_image_bytes, encode_image_bytes, pil_to_rgb_alpha
from app.config.settings import get_settings

try:
    import numpy as np
    import torch
except ImportError:
    np = None
    torch = None

logger = logging.getLogger(__name__)


class InvisioEccvColorizationService:
    """Wraps the invisio ECCV16 colorization pipeline inside mainproject."""

    def __init__(self):
        self._settings = get_settings()
        self._backend_root = Path(__file__).resolve().parents[2]
        self._vendor_dir = self._resolve_path(self._settings.COLORIZATION_VENDOR_DIR)
        self._cluster_path = self._resolve_path(self._settings.COLORIZATION_CLUSTER_POINTS_PATH)
        self._weights_path = self._resolve_path(self._settings.COLORIZATION_WEIGHTS_PATH)
        self._device = self._resolve_device(self._settings.COLORIZATION_DEVICE)
        self._input_size = max(64, int(self._settings.COLORIZATION_INPUT_SIZE))
        self._load_lock = Lock()
        self._model = None
        self._preprocess_img = None
        self._postprocess_tens = None

    def isConfigured(self) -> bool:
        return (
            torch is not None
            and np is not None
            and self._vendor_dir.exists()
            and self._cluster_path.exists()
            and self._weights_path.exists()
        )

    def warmup(self) -> None:
        if not self.isConfigured():
            raise FileNotFoundError(
                "Invisio ECCV16 assets are missing. "
                f"vendor={self._vendor_dir}, cluster={self._cluster_path}, weights={self._weights_path}"
            )
        self._ensure_loaded()

    def release(self) -> None:
        self._model = None
        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()

    def colorize(self, image_bytes: bytes) -> bytes:
        self._ensure_loaded()

        pil_image = decode_image_bytes(image_bytes)
        rgb_image, alpha_channel = pil_to_rgb_alpha(pil_image)
        tens_orig_l, tens_rs_l = self._preprocess_img(
            rgb_image,
            HW=(self._input_size, self._input_size),
        )

        tens_rs_l = tens_rs_l.to(self._device)
        with torch.no_grad():
            out_ab = self._model(tens_rs_l).detach().cpu()

        output_rgb = self._postprocess_tens(tens_orig_l, out_ab)
        output_rgb = np.clip(output_rgb * 255.0, 0, 255).astype(np.uint8)
        return encode_image_bytes(output_rgb, alpha_channel, image_format="PNG")

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return

        with self._load_lock:
            if self._model is not None:
                return

            self._ensure_vendor_imports()
            from invisio_colorizers.eccv16 import eccv16
            from invisio_colorizers.util import postprocess_tens, preprocess_img

            logger.info(
                "Loading Invisio ECCV16 colorization model from %s on device=%s",
                self._weights_path,
                self._device,
            )
            model = eccv16(
                pretrained=True,
                weights_path=str(self._weights_path),
                cluster_points_path=str(self._cluster_path),
            )
            self._model = model.to(self._device).eval()
            self._preprocess_img = preprocess_img
            self._postprocess_tens = postprocess_tens
            logger.info("Invisio ECCV16 colorization model ready")

    def _ensure_vendor_imports(self) -> None:
        vendor_parent = str(self._vendor_dir.parent)
        if vendor_parent not in sys.path:
            sys.path.insert(0, vendor_parent)

    def _resolve_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return self._backend_root / path

    def _resolve_device(self, configured_device: str) -> str:
        requested = (configured_device or self._settings.DEVICE).strip().lower()
        if requested == "cuda" and torch is not None and torch.cuda.is_available():
            return "cuda"
        return "cpu"
