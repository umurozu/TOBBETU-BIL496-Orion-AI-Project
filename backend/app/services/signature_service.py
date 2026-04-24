"""
Invisible export signature embedding and detection.

The signature is written into paired luminance cells near the configured
watermark position. It is subtle enough to stay unobtrusive but still
detectable after normal export.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

from PIL import Image as PILImage

from app.config.settings import get_settings
from app.services.watermark_service import WatermarkService

try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    np = None
    _CV2_AVAILABLE = False


class SignatureService:
    _ROWS = 4
    _PAIR_COLUMNS = 3
    _TOTAL_BITS = _ROWS * _PAIR_COLUMNS

    def __init__(self, watermark_service: WatermarkService | None = None):
        self.settings = get_settings()
        self.watermarkService = watermark_service or WatermarkService()
        self._bits = self._deriveBits()

    def embedSignature(self, image: PILImage.Image) -> PILImage.Image:
        if not (self.settings.EXPORT_SIGNATURE_ENABLED and _CV2_AVAILABLE):
            return image

        rgba = image.convert("RGBA")
        rgba_np = np.array(rgba).astype(np.uint8)
        rgb_np = rgba_np[:, :, :3]
        alpha_np = rgba_np[:, :, 3]

        box = self._resolveBox(rgb_np.shape[1], rgb_np.shape[0])
        if box is None:
            return rgba

        x_pos, y_pos, width, height = box
        luma = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2LAB).astype(np.float32)
        l_channel = luma[:, :, 0]
        delta = max(2.5, 255.0 * float(self.settings.EXPORT_SIGNATURE_STRENGTH))

        for bit_index, bit in enumerate(self._bits):
            left_box, right_box = self._cellPairBounds(bit_index, x_pos, y_pos, width, height)
            left_mask = self._softCellMask(l_channel.shape, left_box)
            right_mask = self._softCellMask(l_channel.shape, right_box)
            direction = 1.0 if bit == 1 else -1.0
            l_channel = np.clip(l_channel + (left_mask * delta * direction), 0, 255)
            l_channel = np.clip(l_channel - (right_mask * delta * direction), 0, 255)

        luma[:, :, 0] = l_channel
        signed_rgb = cv2.cvtColor(luma.astype(np.uint8), cv2.COLOR_LAB2RGB)
        signed_rgba = np.dstack([signed_rgb, alpha_np]).astype(np.uint8)
        return PILImage.fromarray(signed_rgba, mode="RGBA")

    def detectSignature(self, image_bytes: bytes) -> dict:
        if not _CV2_AVAILABLE:
            return {
                "has_signature": False,
                "confidence": 0.0,
                "matched_bits": 0,
                "total_bits": self._TOTAL_BITS,
                "reason": "OpenCV is not available for signature detection.",
            }

        rgba = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
        rgba_np = np.array(rgba).astype(np.uint8)
        rgb_np = rgba_np[:, :, :3]

        box = self._resolveBox(rgb_np.shape[1], rgb_np.shape[0])
        if box is None:
            return {
                "has_signature": False,
                "confidence": 0.0,
                "matched_bits": 0,
                "total_bits": self._TOTAL_BITS,
                "reason": "Image is too small for Invisio signature detection.",
            }

        luma = cv2.cvtColor(rgb_np, cv2.COLOR_RGB2LAB)[:, :, 0].astype(np.float32)
        luma = cv2.GaussianBlur(luma, (5, 5), 0)
        x_pos, y_pos, width, height = box

        matched_bits = 0
        pair_strengths: list[float] = []
        weighted_scores: list[float] = []

        for bit_index, bit in enumerate(self._bits):
            left_box, right_box = self._cellPairBounds(bit_index, x_pos, y_pos, width, height)
            left_mean = self._meanRegion(luma, left_box)
            right_mean = self._meanRegion(luma, right_box)
            diff = float(left_mean - right_mean)
            expected = 1.0 if bit == 1 else -1.0
            score = diff * expected
            if score > 0:
                matched_bits += 1
            pair_strengths.append(abs(diff))
            weighted_scores.append(score)

        match_ratio = matched_bits / float(self._TOTAL_BITS)
        average_strength = sum(pair_strengths) / max(1, len(pair_strengths))
        confidence = max(0.0, min(1.0, match_ratio * min(1.0, average_strength / 4.5)))
        threshold = float(self.settings.EXPORT_SIGNATURE_THRESHOLD)
        has_signature = match_ratio >= threshold and average_strength >= 2.2

        return {
            "has_signature": has_signature,
            "confidence": round(confidence, 4),
            "matched_bits": matched_bits,
            "total_bits": self._TOTAL_BITS,
            "average_strength": round(average_strength, 3),
            "reason": "Invisio export signature detected."
            if has_signature
            else "No reliable Invisio export signature found.",
        }

    def _deriveBits(self) -> list[int]:
        source = self._signatureSourceBytes()
        digest = hashlib.sha256(source).digest()
        bits: list[int] = []
        for byte in digest:
            for shift in range(8):
                bits.append((byte >> shift) & 1)
                if len(bits) >= self._TOTAL_BITS:
                    return bits
        return bits

    def _signatureSourceBytes(self) -> bytes:
        asset_path = self.watermarkService.resolveWatermarkAssetPath()
        if asset_path is not None and asset_path.exists():
            return asset_path.read_bytes()
        return (self.settings.APP_NAME + "::invisio-export-signature").encode("utf-8")

    def _resolveBox(self, image_width: int, image_height: int) -> tuple[int, int, int, int] | None:
        margin = max(12, int(self.settings.EXPORT_WATERMARK_MARGIN))
        width = max(72, int(image_width * 0.18))
        height = max(44, int(image_height * 0.14))
        width = min(width, image_width - (margin * 2))
        height = min(height, image_height - (margin * 2))

        if width < 48 or height < 28:
            return None

        position = (self.settings.EXPORT_WATERMARK_POSITION or "bottom_right").lower()
        if position == "top_left":
            x_pos, y_pos = margin, margin
        elif position == "top_right":
            x_pos, y_pos = image_width - width - margin, margin
        elif position == "bottom_left":
            x_pos, y_pos = margin, image_height - height - margin
        elif position == "center":
            x_pos, y_pos = (image_width - width) // 2, (image_height - height) // 2
        else:
            x_pos, y_pos = image_width - width - margin, image_height - height - margin

        return int(x_pos), int(y_pos), int(width), int(height)

    def _cellPairBounds(
        self,
        bit_index: int,
        x_pos: int,
        y_pos: int,
        width: int,
        height: int,
    ) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
        row = bit_index // self._PAIR_COLUMNS
        pair_column = bit_index % self._PAIR_COLUMNS
        cell_width = width / float(self._PAIR_COLUMNS * 2)
        cell_height = height / float(self._ROWS)

        left_x = int(round(x_pos + (pair_column * 2 * cell_width)))
        right_x = int(round(x_pos + ((pair_column * 2 + 1) * cell_width)))
        top_y = int(round(y_pos + (row * cell_height)))
        box_width = max(6, int(round(cell_width)))
        box_height = max(6, int(round(cell_height)))

        return (
            (left_x, top_y, box_width, box_height),
            (right_x, top_y, box_width, box_height),
        )

    def _softCellMask(self, shape: tuple[int, int], box: tuple[int, int, int, int]) -> "np.ndarray":
        x_pos, y_pos, width, height = box
        mask = np.zeros(shape, dtype=np.float32)
        inset = max(1, min(width, height) // 6)
        x_start = x_pos + inset
        y_start = y_pos + inset
        x_end = min(shape[1], x_pos + width - inset)
        y_end = min(shape[0], y_pos + height - inset)
        if x_end <= x_start or y_end <= y_start:
            x_start, y_start = x_pos, y_pos
            x_end = min(shape[1], x_pos + width)
            y_end = min(shape[0], y_pos + height)
        mask[y_start:y_end, x_start:x_end] = 1.0
        return cv2.GaussianBlur(mask, (5, 5), 0)

    def _meanRegion(self, luma: "np.ndarray", box: tuple[int, int, int, int]) -> float:
        x_pos, y_pos, width, height = box
        region = luma[y_pos:y_pos + height, x_pos:x_pos + width]
        if region.size == 0:
            return 0.0
        return float(region.mean())
