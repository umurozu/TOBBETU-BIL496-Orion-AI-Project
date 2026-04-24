"""
LamaInpaintingModel — Real AI Implementation
HLD Module: AI Processing Layer — Inpainting / Object Removal

Wraps Fatih's LaMa (Large Mask inpainting) subprocess-based implementation
behind the AIModel Strategy interface.

LaMa is a state-of-the-art inpainting model used for:
  - Object removal (EditingType.OBJECT_REMOVAL)
  - Region inpainting (EditingType.INPAINTING)
  - Background replacement (EditingType.BACKGROUND_REPLACE)

Integration:
    The actual LaMa repo lives at: fatih/models/lama/
    Requires 'big-lama/' checkpoint directory inside the lama folder.
    MODELS_BASE_DIR setting should point to fatih/models/ directory.
"""

from __future__ import annotations
import io
import logging
import uuid
import sys
import subprocess
import shutil
import os
import re
from pathlib import Path

from app.ai.base import AIModel
from app.ai.utils import get_python_bin
from app.model.image import Image
from app.model.editing_request import EditingRequest
from app.model.result_image import ResultImage
from app.model.mask import Mask
from app.config.settings import get_settings
from app.utils.exceptions import ProcessingError, ValidationError

logger = logging.getLogger(__name__)

try:
    from PIL import Image as PILImage, ImageFilter
    import numpy as np
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False


def _resolve_models_base_dir() -> Path:
    """Resolves the base directory containing Fatih's model submodules."""
    settings = get_settings()
    if settings.MODELS_BASE_DIR:
        return Path(settings.MODELS_BASE_DIR)
    # mainproject/backend/app/ai/lama_inpainting.py → go up 4 levels to reach mainproject root
    this_file = Path(__file__).resolve()
    return this_file.parents[3] / "models"


class LamaInpaintingModel(AIModel):
    """
    Real LaMa–based inpainting / object removal model.

    Dispatches to Fatih's subprocess-based LaMa implementation.
    Falls back gracefully when model weights are not present.

    Attributes:
        lama_base (Path): Root of the lama submodule directory.
        script_path (Path): Path to bin/predict.py inside lama.
        model_dir (Path): Path to big-lama/ checkpoint directory.
        _available (bool): Whether LaMa is ready for inference.
    """

    def __init__(self, edgeAware: bool = True, **kwargs):
        super().__init__(modelName="LamaInpainting", version="1.0.0", **kwargs)
        self.edgeAware = edgeAware
        base = _resolve_models_base_dir()
        self.lama_base = base / "lama"
        self.script_path = self.lama_base / "bin" / "predict.py"
        self.model_dir = self.lama_base / "big-lama"
        self._temp_root = base.parent / "temp" / "lama"
        self._output_dir = base.parent / "temp" / "output"
        self._available = False

    def loadModel(self) -> None:
        """Check availability of LaMa resources at application startup."""
        if not _PIL_AVAILABLE:
            logger.warning("LamaInpaintingModel: Pillow/numpy not installed — model unavailable")
            self.loaded = True
            return
        if not self.script_path.exists():
            logger.warning(
                f"LamaInpaintingModel: predict.py not found at {self.script_path}. "
                "Ensure fatih/models/lama/ is present and contains bin/predict.py."
            )
            self.loaded = True
            return
        if not self.model_dir.exists():
            logger.warning(
                f"LamaInpaintingModel: big-lama/ checkpoint not found at {self.model_dir}. "
                "Download the LaMa weights and place them at lama/big-lama/."
            )
            self.loaded = True
            return
        self._available = True
        self._temp_root.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LamaInpaintingModel loaded — model_dir={self.model_dir}")
        self.loaded = True

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        """
        Performs content-aware inpainting using LaMa.

        Extracts mask from request parameters (key: 'mask_data' as bytes),
        or uses a default center-region mask if none is provided.

        Pipeline: decode mask → preprocess → LaMa subprocess → postprocess
        """
        self._ensure_loaded()

        if not self._available:
            logger.warning("LamaInpaintingModel unavailable — returning original image")
            if request.getParameter("mask_data") is not None:
                raise ProcessingError(
                    "LaMa inpainting is not available on this server. Ensure the LaMa repo and weights are installed.",
                    error_code="LAMA_UNAVAILABLE",
                )
            return self.postprocess(image.rawData)

        if not _PIL_AVAILABLE:
            if request.getParameter("mask_data") is not None:
                raise ProcessingError(
                    "LaMa inpainting dependencies are missing (Pillow/numpy).",
                    error_code="LAMA_DEPENDENCY_MISSING",
                )
            return self.postprocess(image.rawData)

        logger.info(f"LamaInpaintingModel: processing image {image.imageId}")

        # Extract mask bytes from request parameters
        mask_bytes = request.getParameter("mask_data")
        if mask_bytes is None:
            logger.warning("LamaInpaintingModel: no mask_data in request — cannot run without mask")
            raise ValidationError(
                message="Mask is required for object removal. Paint the area to remove, then try again.",
                error_code="MASK_REQUIRED",
            )
            
        if isinstance(mask_bytes, str):
            import base64
            # Strip data URL prefix if present (e.g., data:image/png;base64,...)
            if mask_bytes.startswith("data:image"):
                try:
                    mask_bytes = mask_bytes.split(",", 1)[1]
                except IndexError:
                    pass
            try:
                mask_bytes = base64.b64decode(mask_bytes)
            except Exception as e:
                logger.error(f"LamaInpaintingModel: failed to decode base64 mask: {e}")
                return self.postprocess(image.rawData)

        try:
            return self.fillRegion(image, mask_bytes)
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"LamaInpaintingModel error: {e}", exc_info=True)
            raise ProcessingError(
                "LaMa inpainting failed. Check backend logs for details.",
                error_code="LAMA_INFERENCE_FAILED",
            )

    def fillRegion(self, image: Image, mask_bytes: bytes) -> ResultImage:
        """
        Fills the region indicated by mask_bytes using LaMa.

        Args:
            image: Input image.
            mask_bytes: Raw PNG/bytes of the mask (white = area to fill).

        Returns:
            ResultImage with the inpainted result.
        """
        job_id = uuid.uuid4().hex
        work_dir = self._temp_root / job_id
        input_dir = work_dir / "input"
        run_output_dir = work_dir / "output"
        final_path = self._output_dir / f"{job_id}_inpainted.png"

        input_dir.mkdir(parents=True, exist_ok=True)
        run_output_dir.mkdir(parents=True, exist_ok=True)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        image_path = input_dir / "input.png"
        mask_path = input_dir / "input_mask001.png"

        try:
            # Load and validate images
            pil_image = PILImage.open(io.BytesIO(image.rawData)).convert("RGB")
            pil_mask = PILImage.open(io.BytesIO(mask_bytes)).convert("L")

            if pil_mask.size != pil_image.size:
                pil_mask = pil_mask.resize(pil_image.size, PILImage.Resampling.NEAREST)

            # Clean mask: strict binary + slight dilation to cover object edges
            mask_np = np.array(pil_mask, dtype=np.uint8)
            mask_np = np.where(mask_np > 20, 255, 0).astype(np.uint8)
            pil_mask = PILImage.fromarray(mask_np, mode="L").filter(ImageFilter.MaxFilter(5))

            pil_image.save(str(image_path), format="PNG")
            pil_mask.save(str(mask_path), format="PNG")

            # Correctly resolve python binary across platforms
            python_bin: Path | None = None
            settings = get_settings()
            python_override = (settings.LAMA_PYTHON_BIN or "").strip()
            if python_override:
                candidate = Path(python_override)
                if candidate.exists() and not candidate.is_dir():
                    python_bin = candidate
                else:
                    logger.warning(
                        f"LamaInpaintingModel: LAMA_PYTHON_BIN points to missing python: {candidate}"
                    )

            if python_bin is None:
                shared_venv_root = self.lama_base.parent / "u2net-demo" / ".venv"
                if sys.platform == "win32":
                    candidate = shared_venv_root / "Scripts" / "python.exe"
                else:
                    candidate = shared_venv_root / "bin" / "python"
                if candidate.exists() and not candidate.is_dir():
                    python_bin = candidate

            if python_bin is None:
                python_bin = get_python_bin(self.lama_base)

            cmd = [
                str(python_bin),
                str(self.script_path),
                f"model.path={self.model_dir}",
                f"indir={input_dir}",
                f"outdir={run_output_dir}",
                "dataset.img_suffix=.png",
                f"device={self.device}",
            ]

            logger.info(f"LaMa Subprocess Command: {' '.join(cmd)}")

            env = os.environ.copy()
            env["PYTHONPATH"] = str(self.lama_base)
            env["TORCH_HOME"] = str(self.lama_base)

            result = subprocess.run(
                cmd,
                cwd=str(self.lama_base),
                env=env,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode != 0:
                stderr = (result.stderr or "").strip()
                stdout = (result.stdout or "").strip()
                combined = "\n".join([part for part in [stderr, stdout] if part]).strip()

                missing_match = re.search(r"No module named ['\"]([^'\"]+)['\"]", combined)
                if missing_match:
                    missing_module = missing_match.group(1)
                    raise ProcessingError(
                        f"LaMa dependency missing: '{missing_module}'. Install backend LaMa dependencies and restart.",
                        error_code="LAMA_DEPENDENCY_MISSING",
                    )

                if "CUDA out of memory" in combined:
                    raise ProcessingError(
                        "LaMa ran out of GPU memory. Try a smaller image or set DEVICE=cpu in backend .env.",
                        error_code="LAMA_OOM",
                    )

                raise ProcessingError(
                    "LaMa inference failed. Check backend logs for details.",
                    error_code="LAMA_INFERENCE_FAILED",
                )

            # LaMa output file: input_mask001.png
            inpainted_path = run_output_dir / "input_mask001.png"
            if not inpainted_path.exists():
                raise ProcessingError(
                    "LaMa output file was not produced. Check backend logs for details.",
                    error_code="LAMA_OUTPUT_MISSING",
                )

            shutil.copy2(str(inpainted_path), str(final_path))

            # Read result and return as ResultImage
            with open(str(final_path), "rb") as f:
                result_bytes = f.read()

            logger.info(f"LamaInpaintingModel: inpainting complete, output={final_path}")
            return self.postprocess(result_bytes)

        finally:
            shutil.rmtree(str(work_dir), ignore_errors=True)
