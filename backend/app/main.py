"""
Invisio Backend Application — Main Entrypoint
LLD §2.1.1 — Application Package

Initializes and configures the FastAPI application:
- CORS middleware for frontend communication
- Security and rate-limiting middleware
- AI model factory and lifecycle
- Controller dependency injection
- Background session cleanup
"""

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException
from pydantic import ValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
import tempfile
import os
import io
import traceback
from app.model.image import Image
from app.model.editing_request import EditingType, EditingRequest

from app.config.settings import get_settings
from app.config.database import init_db, close_db
from app.middleware.rate_limiter import RateLimiterMiddleware
from app.middleware.security import SecurityMiddleware
from app.ai.factory import create_default_factory
from app.services.session_service import SessionService
from app.services.storage_service import StorageService
from app.services.signature_service import SignatureService
from app.services.export_service import ExportService
from app.services.hairstyle_service import HairstyleTryOnService
from app.controller.security_controller import SecurityController
from app.controller.session_controller import SessionController
from app.controller.image_controller import ImageController
from app.controller.editing_controller import EditingController
from app.controller.refinement_controller import RefinementController
from app.controller.download_controller import DownloadController
from app.controller.signature_controller import SignatureController
from app.controller.hairstyle_controller import HairstyleController
from app.controller.auth_controller import AuthController
from app.controller.community_controller import CommunityController
from app.core.routes import router, init_routes
from app.schemas.responses import APIResponse
from app.utils.exceptions import InvisioBaseError

_HAS_ADAIN = None
stylize = None

logger = logging.getLogger(__name__)


def _get_adain_stylizer():
    global _HAS_ADAIN, stylize
    if stylize is not None:
        return stylize

    try:
        from app.ai.inference_adain import stylize as _stylize
        stylize = _stylize
        _HAS_ADAIN = True
        return stylize
    except ImportError:
        _HAS_ADAIN = False
        return None


# ------- Shared instances -------
session_service = SessionService()
storage_service = StorageService()
signature_service = SignatureService()
export_service = ExportService(signature_service=signature_service)
hairstyle_service = HairstyleTryOnService()
model_factory = create_default_factory(hairstyle_service=hairstyle_service)
security_controller = SecurityController()
session_controller = SessionController(session_service, security_controller)
image_controller = ImageController(
    session_service, session_controller, security_controller, model_factory
)
editing_controller = EditingController(
    model_factory, session_service, session_controller, security_controller
)
refinement_controller = RefinementController(
    session_service, session_controller, security_controller, model_factory
)
download_controller = DownloadController(
    session_service, session_controller, security_controller, export_service
)
signature_controller = SignatureController(signature_service)
hairstyle_controller = HairstyleController(
    hairstyle_service,
    session_service,
    session_controller,
)
auth_controller = AuthController()
community_controller = CommunityController(
    session_service, storage_service
)

# Inject controllers into routes
init_routes(
    image_ctrl=image_controller,
    editing_ctrl=editing_controller,
    refinement_ctrl=refinement_controller,
    download_ctrl=download_controller,
    session_ctrl=session_controller,
    auth_ctrl=auth_controller,
    community_ctrl=community_controller,
    signature_ctrl=signature_controller,
    hairstyle_ctrl=hairstyle_controller,
)


# ------- Background Task: Session Cleanup -------
async def _session_cleanup_task():
    """Periodically removes expired sessions."""
    settings = get_settings()
    while True:
        await asyncio.sleep(settings.SESSION_CLEANUP_INTERVAL_SECONDS)
        try:
            cleaned = session_service.cleanupExpiredSessions()
            if cleaned > 0:
                logger.info(f"Session cleanup: removed {cleaned} expired sessions")
        except Exception as e:
            logger.error(f"Session cleanup error: {e}")


# ------- Lifespan Manager -------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()

    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Device: {settings.DEVICE}")

    # Initialize database (create tables if needed)
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")

    # Keep startup light and defer model loading until the first relevant request.
    logger.info("AI models will be loaded lazily on demand.")

    # Start background session cleanup
    cleanup_task = asyncio.create_task(_session_cleanup_task())

    logger.info(f"{settings.APP_NAME} is ready.")
    yield

    # Shutdown
    logger.info(f"Shutting down {settings.APP_NAME}...")
    cleanup_task.cancel()
    model_factory.unloadAllModels()
    try:
        await close_db()
    except Exception:
        pass
    logger.info("Shutdown complete.")


# ------- FastAPI App -------
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered photo editor — Team Orion-AI",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SecurityMiddleware)
app.add_middleware(RateLimiterMiddleware)

# Routes
app.include_router(router)


# ------- Global Exception Handler -------
@app.exception_handler(InvisioBaseError)
async def invisio_exception_handler(request: Request, exc: InvisioBaseError):
    """Transforms Invisio exceptions into standardized API responses."""
    response = APIResponse.error(
        message=exc.message,
        error_code=exc.error_code,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=response.model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Catches unexpected exceptions — never exposes internals."""
    logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
    response = APIResponse.error(
        message="An internal error occurred. Please try again.",
        error_code="INTERNAL_ERROR",
    )
    return JSONResponse(
        status_code=500,
        content=response.model_dump(),
    )


# ------- Standalone AdaIN Style Transfer Endpoint -------
@app.post("/style-transfer", tags=["AI"])
async def style_transfer_adain(
    content_image: UploadFile = File(...),
    style_image: UploadFile = File(...),
    alpha: float = Form(1.0)
):
    """
    Directly applies AdaIN style transfer using the standalone app.ai.inference_adain module.
    """
    adain_stylize = _get_adain_stylizer()
    if adain_stylize is None:
        raise HTTPException(status_code=503, detail="Style transfer (AdaIN) is not available. PyTorch not installed.")
    if not content_image.filename or not style_image.filename:
        raise HTTPException(status_code=400, detail="Images must be provided.")
        
    try:
        # Create temp files for reliable processing as required by stylize(content_path, style_path, alpha)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf_content:
            content_content = await content_image.read()
            tf_content.write(content_content)
            temp_content_path = tf_content.name
            
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tf_style:
            style_content = await style_image.read()
            tf_style.write(style_content)
            temp_style_path = tf_style.name
            
    except Exception as e:
        logger.error(f"Failed to read image buffer: {e}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded image files.")

    # ------- NSFW Check (LLD §1.2.5) -------
    try:
        nsfw_model = model_factory.createModel(EditingType.NSFW_DETECTION)
        
        # Check Content Image
        content_img_model = Image(
            imageId="tmp_content_" + str(uuid.uuid4())[:8],
            rawData=content_content,
            format="jpg",
            size=len(content_content),
            width=512, height=512 # Placeholder dims for nsfw check
        )
        nsfw_model.process(content_img_model, EditingRequest(requestId="nsfw_check", editingType=EditingType.NSFW_DETECTION))
        
        # Check Style Image
        style_img_model = Image(
            imageId="tmp_style_" + str(uuid.uuid4())[:8],
            rawData=style_content,
            format="jpg",
            size=len(style_content),
            width=512, height=512
        )
        nsfw_model.process(style_img_model, EditingRequest(requestId="nsfw_check", editingType=EditingType.NSFW_DETECTION))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        pass

    try:
        result_path = adain_stylize(temp_content_path, temp_style_path, alpha=alpha)
        with open(result_path, "rb") as f:
            result_bytes = f.read()
            
        return StreamingResponse(
            io.BytesIO(result_bytes),
            media_type="image/jpeg"
        )
    except Exception as e:
        logger.error(f"Unexpected AdaIN error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal processing error during style transfer.")
    finally:
        try:
            if os.path.exists(temp_content_path): os.remove(temp_content_path)
            if os.path.exists(temp_style_path): os.remove(temp_style_path)
        except: pass


# ------- Standalone Dual-Image Background Replace Endpoint -------
@app.post("/background-replace", tags=["AI"])
async def background_replace_dual(
    foreground_image: UploadFile = File(...),
    background_image: UploadFile = File(...)
):
    """
    Applies background replacement and deterministic color transfer.
    """
    if not foreground_image.filename or not background_image.filename:
        raise HTTPException(status_code=400, detail="Both images must be provided.")
        
    try:
        fg_content = await foreground_image.read()
        bg_content = await background_image.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded image files.")

    from PIL import Image as PILImage
    import cv2
    import numpy as np
    from app.ai.utils import reinhard_color_transfer
    
    # Composite and Color Transfer directly using the uploaded foreground's Alpha channel
    try:
        fg_rgba = PILImage.open(io.BytesIO(fg_content)).convert("RGBA")
        bg_rgb = PILImage.open(io.BytesIO(bg_content)).convert("RGB")
        
        # Smart Proportional Scaling and Bottom-Center Alignment
        bg_w, bg_h = bg_rgb.size
        fg_w, fg_h = fg_rgba.size
        
        # Scale foreground: maintain aspect ratio, fit inside background 
        # (capped at 95% of background height to avoid clipping top perfectly)
        scale_factor = min(bg_w / fg_w, (bg_h * 0.95) / fg_h)
        new_fg_size = (int(fg_w * scale_factor), int(fg_h * scale_factor))
        
        fg_rgba_resized = fg_rgba.resize(new_fg_size, PILImage.Resampling.LANCZOS)
        
        # Create empty transparent canvas matching BG dimensions
        canvas = PILImage.new("RGBA", bg_rgb.size, (0, 0, 0, 0))
        
        # Center horizontally, align to bottom naturally
        x_offset = (bg_w - new_fg_size[0]) // 2
        y_offset = bg_h - new_fg_size[1]
        
        canvas.paste(fg_rgba_resized, (x_offset, y_offset), fg_rgba_resized)
        
        fg_np = np.array(canvas)
        bg_np = np.array(bg_rgb)
        
        fg_rgb = fg_np[:, :, :3]
        fg_alpha = fg_np[:, :, 3]
        
        # Apply Reinhard Color Transfer (deterministic)
        fg_rgb_matched = reinhard_color_transfer(fg_rgb, bg_np, source_mask=fg_alpha)
        
        # Alpha composite
        alpha_mask = fg_alpha.astype(float) / 255.0
        alpha_mask_3d = np.stack([alpha_mask]*3, axis=2)
        
        final_rgb = (fg_rgb_matched * alpha_mask_3d + bg_np * (1.0 - alpha_mask_3d)).astype(np.uint8)
        
        final_pil = PILImage.fromarray(final_rgb)
        buf = io.BytesIO()
        final_pil.save(buf, format="JPEG", quality=95)
        
        return StreamingResponse(
            io.BytesIO(buf.getvalue()),
            media_type="image/jpeg"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Contrast matching failed: {str(e)}")
