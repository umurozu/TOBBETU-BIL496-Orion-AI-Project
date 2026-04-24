"""
U2NetSegmentationModel — Real AI Implementation
HLD Module: AI Processing Layer — Segmentation

Wraps Fatih's U2Net subprocess-based background removal implementation
behind the AIModel Strategy interface.

U2Net produces high-quality salient object detection masks and is used for:
  - Segmentation (EditingType.SEGMENTATION)
  - Background removal (EditingType.BACKGROUND_REMOVE)

Integration:
    The actual U2Net repo lives at: fatih/models/u2net-demo/
    MODELS_BASE_DIR setting should point to fatih/models/ directory,
    or defaults to resolution relative to this file.
"""

from __future__ import annotations
import io
import logging
import uuid
import sys
import subprocess
import shutil
from pathlib import Path
from typing import Optional

from app.ai.base import AIModel
from app.ai.utils import get_python_bin
from app.model.image import Image
from app.model.editing_request import EditingRequest
from app.model.result_image import ResultImage
from app.model.mask import Mask
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

# ---- Lazy import of PIL to avoid hard dependency at import time ----
try:
    from PIL import Image as PILImage
    import numpy as np
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def _resolve_models_base_dir() -> Path:
    """
    Resolves the base directory containing Fatih's model submodules.
    Priority:
      1. MODELS_BASE_DIR setting (if non-empty)
      2. Auto-detect relative to project structure
    """
    settings = get_settings()
    if settings.MODELS_BASE_DIR:
        return Path(settings.MODELS_BASE_DIR)
    # Fallback: traverse up from this file to locate fatih/models
    this_file = Path(__file__).resolve()
    # mainproject/backend/app/ai/u2net_segmentation.py → go up 4 levels to reach mainproject root
    candidate = this_file.parents[3] / "models"
    return candidate


class U2NetSegmentationModel(AIModel):
    """
    Real U2Net–based segmentation / background removal model.

    Uses Fatih's subprocess-based U2Net implementation. Wraps the
    external script call behind the standard AIModel.process() interface.

    Attributes:
        u2net_base (Path): Root directory of the u2net-demo submodule.
        script_path (Path): Path to run_single.py.
        model_path (Path): Path to u2net.pth weights file.
        _available (bool): Whether the model and script are present.
    """

    def __init__(self, **kwargs):
        super().__init__(modelName="U2NetSegmentation", version="1.0.0", **kwargs)
        base = _resolve_models_base_dir()
        self.u2net_base = base / "u2net-demo"
        self.script_path = self.u2net_base / "run_single.py"
        self.model_path = self.u2net_base / "saved_models" / "u2net" / "u2net.pth"
        self._temp_dir = Path(self.u2net_base).parent.parent / "temp" / "output"
        self._available = False

    def loadModel(self) -> None:
        """Check availability of U2Net resources on startup."""
        if not _PIL_AVAILABLE:
            logger.warning("U2NetSegmentationModel: Pillow/numpy not installed — model unavailable")
            return
        if not self.script_path.exists():
            logger.warning(
                f"U2NetSegmentationModel: run_single.py not found at {self.script_path}. "
                "Model will be unavailable. Ensure fatih/models/u2net-demo/ is present."
            )
            self.loaded = True  # Mark as 'loaded' but unavailable
            return
        if not self.model_path.exists():
            logger.warning(
                f"U2NetSegmentationModel: model weights not found at {self.model_path}. "
                "Download u2net.pth and place it in u2net-demo/saved_models/u2net/"
            )
            self.loaded = True
            return
        self._available = True
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"U2NetSegmentationModel loaded — script={self.script_path}")
        self.loaded = True

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        """
        Runs U2Net background removal / segmentation.

        Pipeline: validate → write temp files → subprocess → composite → postprocess
        """
        self._ensure_loaded()

        if not self._available:
            logger.warning("U2NetSegmentationModel unavailable — returning original image")
            return self.postprocess(image.rawData)

        if not _PIL_AVAILABLE:
            return self.postprocess(image.rawData)

        logger.info(f"U2NetSegmentationModel: processing image {image.imageId}")

        unique_id = uuid.uuid4().hex
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        input_path = self.u2net_base / f"{unique_id}_input.png"
        mask_path = self._temp_dir / f"{unique_id}_mask.png"
        final_png = self._temp_dir / f"{unique_id}_transparent.png"

        try:
            # Write input image
            pil_img = PILImage.open(io.BytesIO(image.rawData)).convert("RGB")
            pil_img.save(str(input_path), format="PNG")

            # Correctly resolve python binary across platforms
            python_bin = get_python_bin(self.u2net_base)

            cmd = [
                str(python_bin),
                str(self.script_path),
                str(input_path),
                str(mask_path),
                str(self.model_path),
            ]

            logger.info(f"U2Net Subprocess Command: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=str(self.u2net_base),
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise RuntimeError(f"U2Net failed: {result.stderr or result.stdout}")

            if not mask_path.exists():
                raise FileNotFoundError("U2Net did not produce a mask output.")

            # Composite: apply mask as alpha channel
            original = PILImage.open(io.BytesIO(image.rawData)).convert("RGBA")
            mask = PILImage.open(str(mask_path)).convert("L")
            if mask.size != original.size:
                mask = mask.resize(original.size, PILImage.Resampling.LANCZOS)

            mask_np = np.array(mask).astype(np.uint8)

            # Apply user brush edits if provided
            user_mask_b64 = request.getParameter("mask_data")
            is_erase_mode = request.getParameter("brush_action") is True
            if user_mask_b64:
                if isinstance(user_mask_b64, str):
                    import base64
                    if user_mask_b64.startswith("data:image"):
                        try:
                            user_mask_b64 = user_mask_b64.split(",", 1)[1]
                        except IndexError: pass
                    try:
                        user_mask_bytes = base64.b64decode(user_mask_b64)
                        user_mask_pil = PILImage.open(io.BytesIO(user_mask_bytes)).convert("L")
                        if user_mask_pil.size != mask.size:
                            user_mask_pil = user_mask_pil.resize(mask.size, PILImage.Resampling.LANCZOS)
                        
                        user_mask_np = np.array(user_mask_pil).astype(np.uint8)
                        
                        # Where user brushed (white areas in user_mask), apply edits
                        brush_mask = user_mask_np > 50
                        if is_erase_mode:
                            mask_np[brush_mask] = 0 # Erase from kept background (meaning it gets removed)
                        else:
                            mask_np[brush_mask] = 255 # Add to kept background
                            
                    except Exception as e:
                        logger.error(f"U2NetSegmentationModel: Failed to apply user mask: {e}")

            orig_np = np.array(original)
            orig_np[:, :, 3] = mask_np

            transparent_img = PILImage.fromarray(orig_np)
            # Save as PNG with transparency
            buf = io.BytesIO()
            transparent_img.save(buf, format="PNG")
            result_bytes = buf.getvalue()

            logger.info(f"U2NetSegmentationModel: segmentation complete for {image.imageId}")
            return self.postprocess(result_bytes)

        except Exception as e:
            logger.error(f"U2NetSegmentationModel error: {e}")
            # Graceful degradation: return original image
            return self.postprocess(image.rawData)

        finally:
            if input_path.exists():
                input_path.unlink(missing_ok=True)

    def generateMask(self, image: Image) -> Mask:
        """
        Generates a binary segmentation mask using U2Net.
        Returns a placeholder mask if model is unavailable.
        """
        import numpy as np
        if not self._available or not _PIL_AVAILABLE:
            mask_data = np.zeros((image.height, image.width), dtype=np.uint8)
            center_h, center_w = image.height // 4, image.width // 4
            mask_data[center_h:image.height - center_h, center_w:image.width - center_w] = 255
            return Mask(maskData=mask_data, confidenceScore=0.5, width=image.width, height=image.height)

        # Run process() and extract mask from transparent PNG
        dummy_request = EditingRequest(
            requestId=str(uuid.uuid4()),
            editingType=None,
            parameters={},
        )
        result = self.process(image, dummy_request)
        result_pil = PILImage.open(io.BytesIO(result.processedData)).convert("RGBA")
        mask_np = np.array(result_pil)[:, :, 3]
        return Mask(maskData=mask_np, confidenceScore=0.9, width=image.width, height=image.height)
