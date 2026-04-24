"""
Watermarking for final exported images.

This service only touches images during the download/export step so the
editing preview stays clean and lossless while exported results carry the
project watermark.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage
from PIL import ImageDraw, ImageFont

from app.config.settings import get_settings

logger = logging.getLogger(__name__)


class WatermarkService:
    def __init__(self):
        self.settings = get_settings()
        self._backendRoot = Path(__file__).resolve().parents[2]
        self._projectRoot = self._backendRoot.parent
        self._workspaceRoot = self._projectRoot.parent

    def applyWatermark(self, image_bytes: bytes) -> PILImage.Image:
        base_image = PILImage.open(io.BytesIO(image_bytes)).convert("RGBA")
        if not self.settings.EXPORT_WATERMARK_ENABLED:
            return base_image

        overlay = PILImage.new("RGBA", base_image.size, (0, 0, 0, 0))
        watermark_asset = self.resolveWatermarkAssetPath()

        if watermark_asset is not None:
            self._drawAssetWatermark(overlay, watermark_asset)
        else:
            self._drawTextWatermark(overlay)

        return PILImage.alpha_composite(base_image, overlay)

    def resolveWatermarkAssetPath(self) -> Optional[Path]:
        configured_path = self.settings.EXPORT_WATERMARK_IMAGE_PATH.strip()
        candidates: list[Path] = []

        if configured_path:
            candidate = Path(configured_path)
            if candidate.is_absolute():
                candidates.append(candidate)
            else:
                candidates.extend(
                    [
                        self._workspaceRoot / candidate,
                        self._projectRoot / candidate,
                        self._backendRoot / candidate,
                    ]
                )
        else:
            candidates.extend(
                [
                    self._workspaceRoot / "watermark.png",
                    self._projectRoot / "watermark.png",
                    self._backendRoot / "watermark.png",
                    self._backendRoot / "assets" / "watermark.png",
                ]
            )

        for candidate in candidates:
            if candidate.exists():
                return candidate

        if configured_path:
            logger.warning("Configured watermark asset not found at %s", candidates[0])
        return None

    def _drawAssetWatermark(self, overlay: PILImage.Image, asset_path: Path) -> None:
        asset = PILImage.open(asset_path).convert("RGBA")
        scale = max(0.05, float(self.settings.EXPORT_WATERMARK_SCALE))
        target_width = max(48, int(overlay.width * scale))
        target_height = max(1, int(asset.height * (target_width / float(asset.width))))
        asset = asset.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

        alpha = asset.getchannel("A").point(
            lambda pixel: int(pixel * max(0.0, min(1.0, self.settings.EXPORT_WATERMARK_OPACITY)))
        )
        asset.putalpha(alpha)

        x_pos, y_pos = self._resolvePosition(overlay.size, asset.size)
        overlay.alpha_composite(asset, dest=(x_pos, y_pos))

    def _drawTextWatermark(self, overlay: PILImage.Image) -> None:
        text = (self.settings.EXPORT_WATERMARK_TEXT or self.settings.APP_NAME).strip()
        draw = ImageDraw.Draw(overlay)
        font_size = max(16, int(min(overlay.width, overlay.height) * max(0.05, self.settings.EXPORT_WATERMARK_SCALE) * 0.55))
        font = self._loadFont(font_size)
        opacity = max(0.0, min(1.0, self.settings.EXPORT_WATERMARK_OPACITY))
        fill = (255, 255, 255, int(255 * opacity))
        stroke = (15, 23, 42, int(190 * opacity))

        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=1)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x_pos, y_pos = self._resolvePosition(overlay.size, (text_width, text_height))

        draw.text(
            (x_pos, y_pos),
            text,
            font=font,
            fill=fill,
            stroke_width=1,
            stroke_fill=stroke,
        )

    def _resolvePosition(
        self,
        canvas_size: tuple[int, int],
        watermark_size: tuple[int, int],
    ) -> tuple[int, int]:
        canvas_width, canvas_height = canvas_size
        watermark_width, watermark_height = watermark_size
        margin = max(0, int(self.settings.EXPORT_WATERMARK_MARGIN))
        position = (self.settings.EXPORT_WATERMARK_POSITION or "bottom_right").lower()

        if position == "top_left":
            return margin, margin
        if position == "top_right":
            return max(margin, canvas_width - watermark_width - margin), margin
        if position == "bottom_left":
            return margin, max(margin, canvas_height - watermark_height - margin)
        if position == "center":
            return max(0, (canvas_width - watermark_width) // 2), max(0, (canvas_height - watermark_height) // 2)

        return (
            max(margin, canvas_width - watermark_width - margin),
            max(margin, canvas_height - watermark_height - margin),
        )

    def _loadFont(self, font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        font_candidates = [
            "DejaVuSans.ttf",
            "arial.ttf",
            str(self._backendRoot / "assets" / "fonts" / "DejaVuSans.ttf"),
        ]

        for candidate in font_candidates:
            try:
                return ImageFont.truetype(candidate, font_size)
            except Exception:
                continue

        return ImageFont.load_default()
