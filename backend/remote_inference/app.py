from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import anyio
import numpy as np
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from PIL import Image as PILImage

logger = logging.getLogger("remote_inference")

_DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=_DEFAULT_LOG_LEVEL)

app = FastAPI(title="Remote Inference API", version="0.1.0")
_GPU_LOCK = asyncio.Lock()


def _get_expected_api_key() -> str:
    return (os.getenv("INFERENCE_API_KEY") or os.getenv("REMOTE_INFERENCE_API_KEY") or "").strip()


def _require_api_key(x_api_key: str | None) -> None:
    expected = _get_expected_api_key()
    if not expected:
        return
    if not x_api_key or x_api_key.strip() != expected:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def _resolve_device() -> str:
    configured = os.getenv("DEVICE")
    if configured:
        configured = configured.strip().lower()
        if configured == "cuda":
            try:
                import torch

                if torch.cuda.is_available():
                    return "cuda"
                logger.warning("DEVICE=cuda requested but CUDA is not available; falling back to cpu")
                return "cpu"
            except Exception:
                logger.warning("DEVICE=cuda requested but torch is unavailable; falling back to cpu")
                return "cpu"
        return configured
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


@contextmanager
def _pushd(path: Path):
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _ensure_hairfastgan_on_syspath() -> Path | None:
    candidates: list[Path] = []
    env_dir = os.getenv("HAIRFASTGAN_REPO_DIR")
    if env_dir:
        candidates.append(Path(env_dir))
    candidates.extend(
        [
            Path.cwd() / "HairFastGAN",
            Path("/content/HairFastGAN"),
        ]
    )

    for candidate in candidates:
        if not candidate.is_dir():
            continue
        if not (candidate / "hair_swap.py").exists():
            continue
        sys.path.insert(0, str(candidate))
        return candidate
    return None


_SAM_PREDICTOR: Any | None = None


def _load_sam_predictor() -> Any:
    global _SAM_PREDICTOR
    if _SAM_PREDICTOR is not None:
        return _SAM_PREDICTOR

    try:
        from segment_anything import SamPredictor, sam_model_registry
    except Exception as exc:
        raise RuntimeError(
            "segment-anything is not installed. Install it with "
            "`pip install git+https://github.com/facebookresearch/segment-anything.git`."
        ) from exc

    model_type = (os.getenv("SAM_MODEL_TYPE") or "vit_b").strip()
    checkpoint = (os.getenv("SAM_CHECKPOINT_PATH") or os.getenv("SAM_CHECKPOINT") or "sam_vit_b_01ec64.pth").strip()
    checkpoint_path = Path(checkpoint)
    if not checkpoint_path.exists():
        raise RuntimeError(
            f"SAM checkpoint not found at {checkpoint_path}. "
            "Download it and set SAM_CHECKPOINT_PATH."
        )

    device = _resolve_device()
    sam = sam_model_registry[model_type](checkpoint=str(checkpoint_path))
    sam.to(device=device)
    sam.eval()

    predictor = SamPredictor(sam)
    _SAM_PREDICTOR = predictor
    logger.info("SAM predictor loaded model_type=%s device=%s checkpoint=%s", model_type, device, checkpoint_path)
    return predictor


def _sam_predict_mask(
    image_rgb: np.ndarray,
    point_coords: np.ndarray,
    point_labels: np.ndarray,
    multimask_output: bool,
) -> np.ndarray:
    predictor = _load_sam_predictor()
    predictor.set_image(image_rgb)
    masks, scores, _logits = predictor.predict(
        point_coords=point_coords,
        point_labels=point_labels,
        multimask_output=multimask_output,
    )
    if masks is None or len(masks) == 0:
        return np.zeros(image_rgb.shape[:2], dtype=np.uint8)
    best_idx = int(np.argmax(scores)) if scores is not None else 0
    mask = masks[best_idx]
    return (mask.astype(np.uint8) * 255).astype(np.uint8)


def _encode_mask_png(mask_np: np.ndarray) -> bytes:
    with PILImage.fromarray(mask_np, mode="L") as mask_img:
        buf = io.BytesIO()
        mask_img.save(buf, format="PNG")
        return buf.getvalue()


_HAIRFAST_MODEL: Any | None = None
_HAIRFAST_REPO_DIR: Path | None = None


def _resolve_checkpoint_path(repo_dir: Path, maybe_rel: str) -> str:
    path = Path(maybe_rel)
    if path.is_absolute():
        return str(path)
    return str(repo_dir / path)


def _load_hairfast_model() -> Any:
    global _HAIRFAST_MODEL, _HAIRFAST_REPO_DIR
    if _HAIRFAST_MODEL is not None:
        return _HAIRFAST_MODEL

    repo_dir = _ensure_hairfastgan_on_syspath()
    if repo_dir is None:
        raise RuntimeError("HairFastGAN repo not found. Set HAIRFASTGAN_REPO_DIR or clone into ./HairFastGAN.")

    # HairFastGAN loads some checkpoints via relative paths (expects CWD at repo root).
    # Ensure we initialize the model with the repo as working directory.
    required_rel = Path("pretrained_models") / "BiSeNet" / "face_parsing_79999_iter.pth"
    if not (repo_dir / required_rel).exists():
        raise RuntimeError(
            "HairFastGAN weights are incomplete. Missing "
            f"`{required_rel}` under `{repo_dir}`. "
            "Make sure you copied `pretrained_models/` into the HairFastGAN repo (and ran `git lfs pull`)."
        )

    try:
        from hair_swap import HairFast, get_parser
    except Exception as exc:
        raise RuntimeError(
            "Failed to import HairFastGAN. Ensure the HairFastGAN repo is present and dependencies are installed."
        ) from exc

    with _pushd(repo_dir):
        parser = get_parser()
        args = parser.parse_args([])
        args.device = _resolve_device()
        args.ckpt = _resolve_checkpoint_path(repo_dir, str(args.ckpt))
        args.rotate_checkpoint = _resolve_checkpoint_path(repo_dir, str(args.rotate_checkpoint))
        args.blending_checkpoint = _resolve_checkpoint_path(repo_dir, str(args.blending_checkpoint))
        args.pp_checkpoint = _resolve_checkpoint_path(repo_dir, str(args.pp_checkpoint))

        model = HairFast(args)
    _HAIRFAST_MODEL = model
    _HAIRFAST_REPO_DIR = repo_dir
    logger.info("HairFastGAN model loaded device=%s repo_dir=%s", args.device, repo_dir)
    return model


def _tensor_to_png_bytes(tensor: Any) -> bytes:
    try:
        import torch
        import torchvision.transforms.functional as VF
    except Exception as exc:
        raise RuntimeError("torch/torchvision are required to encode HairFastGAN outputs.") from exc

    # HairFastGAN returns `(final, face, shape, color)` when `align=True`.
    if isinstance(tensor, (tuple, list)):
        if not tensor:
            raise TypeError("HairFastGAN returned an empty list/tuple.")
        tensor = tensor[0]

    # Be tolerant to wrapper dicts (some forks return structured outputs).
    if isinstance(tensor, dict):
        for key in ("result", "output", "image", "final", "final_image"):
            if key in tensor:
                tensor = tensor[key]
                break
        else:
            if tensor:
                tensor = next(iter(tensor.values()))

    if isinstance(tensor, PILImage.Image):
        tensor = VF.to_tensor(tensor)

    if not isinstance(tensor, torch.Tensor):
        raise TypeError("HairFastGAN returned an unexpected output type.")

    image_tensor = tensor.detach().float().cpu().clamp(0.0, 1.0)
    pil_img = VF.to_pil_image(image_tensor)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def _hairfast_swap(face: PILImage.Image, shape: PILImage.Image, color: PILImage.Image, align: bool) -> bytes:
    model = _load_hairfast_model()
    repo_dir = _HAIRFAST_REPO_DIR
    if repo_dir is None:
        raise RuntimeError("HairFastGAN repo dir missing after model load.")

    with _pushd(repo_dir):
        output = model.swap(face, shape, color, align=align)
    return _tensor_to_png_bytes(output)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "device": _resolve_device(),
            "cuda_available": _cuda_available(),
            "sam_loaded": _SAM_PREDICTOR is not None,
            "hairfastgan_loaded": _HAIRFAST_MODEL is not None,
        }
    )


@app.post("/v1/sam/warmup")
async def sam_warmup(x_api_key: str | None = Header(None, alias="X-API-Key")) -> JSONResponse:
    _require_api_key(x_api_key)
    try:
        async with _GPU_LOCK:
            await anyio.to_thread.run_sync(_load_sam_predictor)
    except Exception as exc:
        logger.exception("SAM warmup failed")
        raise HTTPException(status_code=500, detail=f"SAM warmup failed: {exc}") from exc

    return JSONResponse({"status": "ok"})


@app.post("/v1/hairfastgan/warmup")
async def hairfastgan_warmup(x_api_key: str | None = Header(None, alias="X-API-Key")) -> JSONResponse:
    _require_api_key(x_api_key)
    try:
        async with _GPU_LOCK:
            await anyio.to_thread.run_sync(_load_hairfast_model)
    except Exception as exc:
        logger.exception("HairFastGAN warmup failed")
        raise HTTPException(status_code=500, detail=f"HairFastGAN warmup failed: {exc}") from exc

    return JSONResponse({"status": "ok"})


@app.post("/v1/sam/predict")
async def sam_predict(
    image: UploadFile = File(...),
    point_coords: str = Form(...),
    point_labels: str = Form(...),
    multimask_output: bool = Form(True),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> Response:
    _require_api_key(x_api_key)

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="image is required.")

    try:
        coords_obj = json.loads(point_coords)
        labels_obj = json.loads(point_labels)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="point_coords and point_labels must be JSON.") from exc

    coords_arr = np.asarray(coords_obj, dtype=np.float32)
    labels_arr = np.asarray(labels_obj, dtype=np.int32)
    if coords_arr.ndim != 2 or coords_arr.shape[1] != 2:
        raise HTTPException(status_code=400, detail="point_coords must be a JSON list of [x, y] pairs.")
    if labels_arr.ndim != 1 or labels_arr.shape[0] != coords_arr.shape[0]:
        raise HTTPException(status_code=400, detail="point_labels must match point_coords length.")

    try:
        with PILImage.open(io.BytesIO(image_bytes)) as pil_img:
            image_rgb = np.array(pil_img.convert("RGB"), dtype=np.uint8)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="image could not be decoded.") from exc

    try:
        async with _GPU_LOCK:
            mask_np = await anyio.to_thread.run_sync(
                _sam_predict_mask,
                image_rgb,
                coords_arr,
                labels_arr,
                multimask_output,
            )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("SAM prediction failed")
        raise HTTPException(status_code=500, detail=f"SAM prediction failed: {exc}") from exc

    return Response(content=_encode_mask_png(mask_np), media_type="image/png")


@app.post("/v1/hairfastgan/swap")
async def hairfastgan_swap(
    face_image: UploadFile = File(...),
    shape_image: UploadFile = File(...),
    color_image: UploadFile = File(...),
    align: bool = Form(True),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
) -> Response:
    _require_api_key(x_api_key)

    face_bytes, shape_bytes, color_bytes = await face_image.read(), await shape_image.read(), await color_image.read()
    if not face_bytes:
        raise HTTPException(status_code=400, detail="face_image is required.")
    if not shape_bytes:
        raise HTTPException(status_code=400, detail="shape_image is required.")
    if not color_bytes:
        raise HTTPException(status_code=400, detail="color_image is required.")

    try:
        face = PILImage.open(io.BytesIO(face_bytes)).convert("RGB")
        shape = PILImage.open(io.BytesIO(shape_bytes)).convert("RGB")
        color = PILImage.open(io.BytesIO(color_bytes)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="one or more images could not be decoded.") from exc

    try:
        async with _GPU_LOCK:
            png_bytes = await anyio.to_thread.run_sync(_hairfast_swap, face, shape, color, align)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("HairFastGAN swap failed")
        raise HTTPException(status_code=500, detail=f"HairFastGAN swap failed: {exc}") from exc

    return Response(content=png_bytes, media_type="image/png")
