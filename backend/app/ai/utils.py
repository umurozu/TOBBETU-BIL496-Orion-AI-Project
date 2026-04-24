import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def get_python_bin(base_path: Path) -> Path:
    """
    Locates the python executable for a virtual environment.
    Strategy:
      1. Prefer the currently running backend interpreter so subprocess models
         inherit the same CUDA-capable environment.
      2. Look for .venv in the base_path (model-specific venv).
      3. If not found, look for a shared venv in a known location (models/u2net-demo/.venv).
      4. Fall back to system python.
    """
    is_windows = sys.platform == "win32"

    current_exe = Path(sys.executable)
    if current_exe.exists() and not current_exe.is_dir():
        return current_exe
    
    # List of candidate venv roots
    candidates = [
        base_path / ".venv",
        base_path, # Check if base_path itself is the venv
    ]
    
    # Add shared venv candidate if on Windows
    # (mainproject/models/model_name -> go up to 'models' then down to 'u2net-demo/.venv')
    if is_windows:
        try:
            shared_venv = base_path.parent / "u2net-demo" / ".venv"
            if shared_venv.exists():
                candidates.append(shared_venv)
        except Exception:
            pass

    for venv_root in candidates:
        if not venv_root.exists():
            continue
            
        # Try Windows path
        if is_windows:
            windows_exe = venv_root / "Scripts" / "python.exe"
            if windows_exe.exists() and not windows_exe.is_dir():
                return windows_exe
        
        # Try Unix path
        unix_exe = venv_root / "bin" / "python"
        if unix_exe.exists() and not unix_exe.is_dir():
            if not is_windows:
                return unix_exe
            else:
                logger.warning(f"Detected Unix-style venv on Windows at {unix_exe}. Ignoring.")
        
    # Standard python lookup via shutil.which
    which_python = shutil.which("python")
    if which_python:
        logger.debug(f"Found system python via shutil.which: {which_python}")
        return Path(which_python)

    # Fallback to sys.executable as absolute last resort
    logger.debug(f"Venv python not found or incompatible, using sys.executable: {current_exe}")
    return current_exe

def reinhard_color_transfer(source_rgb, target_rgb, source_mask=None):
    """
    Deterministically matches the color statistics of the source image to the target image
    using the Reinhard Color Transfer algorithm in the L*a*b* color space.
    
    If source_mask is provided, only pixels within the mask are processed/adjusted.
    This fulfills the academic requirement for a deterministic algorithm.
    """
    import cv2
    import numpy as np
    
    # Convert RGB to LAB
    source_lab = cv2.cvtColor(source_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    target_lab = cv2.cvtColor(target_rgb, cv2.COLOR_RGB2LAB).astype(np.float32)

    # Compute mean and std for target
    (lMeanT, lStDT) = cv2.meanStdDev(target_lab[:, :, 0])
    (aMeanT, aStDT) = cv2.meanStdDev(target_lab[:, :, 1])
    (bMeanT, bStDT) = cv2.meanStdDev(target_lab[:, :, 2])

    if source_mask is not None:
        # Use mask to find mean and std of the foreground only
        (lMeanS, lStDS) = cv2.meanStdDev(source_lab[:, :, 0], mask=source_mask)
        (aMeanS, aStDS) = cv2.meanStdDev(source_lab[:, :, 1], mask=source_mask)
        (bMeanS, bStDS) = cv2.meanStdDev(source_lab[:, :, 2], mask=source_mask)
    else:
        (lMeanS, lStDS) = cv2.meanStdDev(source_lab[:, :, 0])
        (aMeanS, aStDS) = cv2.meanStdDev(source_lab[:, :, 1])
        (bMeanS, bStDS) = cv2.meanStdDev(source_lab[:, :, 2])

    # Avoid division by zero
    lStDS = lStDS if lStDS > 0 else 1.0
    aStDS = aStDS if aStDS > 0 else 1.0
    bStDS = bStDS if bStDS > 0 else 1.0

    l = source_lab[:, :, 0]
    a = source_lab[:, :, 1]
    b = source_lab[:, :, 2]

    # Transfer calculation
    l = ((l - lMeanS) * (lStDT / lStDS)) + lMeanT
    a = ((a - aMeanS) * (aStDT / aStDS)) + aMeanT
    b = ((b - bMeanS) * (bStDT / bStDS)) + bMeanT

    # Clip and assemble
    l = np.clip(l, 0, 255)
    a = np.clip(a, 0, 255)
    b = np.clip(b, 0, 255)

    result_lab = cv2.merge([l, a, b]).astype(np.uint8)
    result_rgb = cv2.cvtColor(result_lab, cv2.COLOR_LAB2RGB)

    # If mask provided, only apply the change to the masked area
    if source_mask is not None:
        mask_3d = cv2.cvtColor(source_mask, cv2.COLOR_GRAY2RGB) / 255.0
        result_rgb = (result_rgb * mask_3d + source_rgb * (1.0 - mask_3d)).astype(np.uint8)

    return result_rgb
