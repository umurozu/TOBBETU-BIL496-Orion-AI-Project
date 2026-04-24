"""
API Routes — LLD §1.2.1, §2.1.1
HLD Module: Controller Layer — REST API

Defines all REST API endpoints as specified in the LLD:
    POST /upload         →  Image upload
    POST /process        →  AI editing operation
    GET /status/{id}     →  Session status
    POST /refine         →  Mask refinement
    POST /regenerate     →  Re-process with refined mask
    GET /download/{id}   →  Export processed image
"""

import logging
import os

from fastapi import APIRouter, UploadFile, File, Query, Path, Depends, Header, Body, Form
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io

from app.schemas.requests import ProcessRequest, RefinementRequest, DownloadRequest
from app.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest
from app.schemas.responses import APIResponse, CommunityFeedResponse
from app.config.database import get_db
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

# These will be initialized in main.py and injected
_image_controller = None
_editing_controller = None
_refinement_controller = None
_download_controller = None
_session_controller = None
_auth_controller = None
_community_controller = None
_signature_controller = None
_hairstyle_controller = None


def init_routes(image_ctrl, editing_ctrl, refinement_ctrl, download_ctrl, session_ctrl, auth_ctrl=None, community_ctrl=None, signature_ctrl=None, hairstyle_ctrl=None):
    """Injects controller instances into routes module."""
    global _image_controller, _editing_controller, _refinement_controller
    global _download_controller, _session_controller, _auth_controller, _community_controller, _signature_controller, _hairstyle_controller
    _image_controller = image_ctrl
    _editing_controller = editing_ctrl
    _refinement_controller = refinement_ctrl
    _download_controller = download_ctrl
    _session_controller = session_ctrl
    _auth_controller = auth_ctrl
    _community_controller = community_ctrl
    _signature_controller = signature_ctrl
    _hairstyle_controller = hairstyle_ctrl


@router.get("/health", tags=["System"])
async def health_check():
    """GET /health — Application health check."""
    from app.config.settings import get_settings
    settings = get_settings()
    registered = []
    active_sessions = 0
    if _session_controller:
        try:
            active_sessions = _session_controller.sessionService.getActiveSessionCount()
        except Exception:
            pass
    if _editing_controller:
        try:
            registered = [t.value for t in _editing_controller.modelFactory.getRegisteredTypes()]
        except Exception:
            pass
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "registered_models": registered,
        "active_sessions": active_sessions,
    }


@router.post("/upload", response_model=APIResponse, tags=["Image"])
async def upload_image(file: UploadFile = File(...)):
    """
    POST /upload — Upload an image for editing.
    
    Accepts a multipart/form-data image file.
    Creates a new session and returns session_id with image metadata.
    """
    result = await _image_controller.uploadImage(file)
    return APIResponse.success(
        message="Image uploaded successfully",
        data=result,
    )


@router.post("/process", response_model=APIResponse, tags=["Editing"])
async def process_image(request: ProcessRequest):
    """
    POST /process — Apply an AI editing operation.
    
    Requires active session_id, editing_type, and optional parameters.
    Returns processed image as base64-encoded data.
    """
    result = _editing_controller.applyEditing(
        session_id=request.session_id,
        editing_type_str=request.editing_type,
        parameters=request.parameters,
    )
    return APIResponse.success(
        message="Editing applied successfully",
        data=result,
    )


@router.get("/status/{session_id}", response_model=APIResponse, tags=["Session"])
async def get_status(session_id: str = Path(..., description="Session ID")):
    """
    GET /status/{session_id} — Check session status.
    
    Returns session processing status, image availability, and expiration info.
    """
    status = _session_controller.getStatus(session_id)
    return APIResponse.success(
        message="Session status retrieved",
        data=status,
    )


@router.post("/refine", response_model=APIResponse, tags=["Refinement"])
async def refine_mask(request: RefinementRequest):
    """
    POST /refine — Apply mask refinement.
    
    Accepts brush data and modifies the segmentation mask.
    """
    result = _refinement_controller.refineMask(
        session_id=request.session_id,
        brush_data_b64=request.mask_data or "",
        brush_size=request.brush_size,
        brush_strength=request.brush_strength,
    )
    return APIResponse.success(
        message="Mask refined successfully",
        data=result,
    )


@router.get("/landmarks/{session_id}", response_model=APIResponse, tags=["AI Processing"])
async def get_face_landmarks(session_id: str = Path(...)):
    """
    GET /landmarks/{session_id} — Get face mesh coordinates for an active session.
    Used for interactive Face Reshape.
    """
    try:
        result = _editing_controller.getLandmarks(session_id)
        if result.get("status") == "success":
            return APIResponse.success(message="Landmarks detected", data=result["data"])
        return APIResponse.error(message=result.get("message", "Detection failed"))
    except Exception as e:
        logger.error(f"Landmark detection error: {e}")
        return APIResponse.error(message=str(e), error_code="LANDMARK_ERROR")

        
    try:
        import io
        import numpy as np
        from PIL import Image as PILImage
        import mediapipe as mp
        
        orig_img = PILImage.open(io.BytesIO(image_model.rawData)).convert("RGB")
        np_img = np.array(orig_img)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np_img)
        detection_result = face_model._landmarker.detect(mp_image)
        
        if not detection_result.face_landmarks:
            return APIResponse.error(message="No human face found in image.")
            
        landmarks = detection_result.face_landmarks[0]
        h, w = np_img.shape[:2]
        
        points = []
        for lm in landmarks:
            points.append([int(lm.x * w), int(lm.y * h)])
            
        return APIResponse.success(
            message="Landmarks retrieved",
            data={"points": points, "width": w, "height": h}
        )
    except Exception as e:
        return APIResponse.error(message=f"Failed to extract landmarks: {e}")


@router.post("/regenerate", response_model=APIResponse, tags=["Refinement"])
async def regenerate_image(request: RefinementRequest):
    """
    POST /regenerate — Re-process image with refined mask.
    """
    result = _refinement_controller.regenerateImage(
        session_id=request.session_id,
        refined_mask_b64=request.mask_data or "",
    )
    return APIResponse.success(
        message="Image regenerated successfully",
        data=result,
    )


@router.get("/download/{session_id}", tags=["Download"])
async def download_image(
    session_id: str = Path(..., description="Session ID"),
    format: str = Query(default="png", description="Export format: jpeg, png, webp"),
):
    """
    GET /download/{session_id} — Download processed image.
    
    Returns the processed image as a downloadable file in the requested format.
    """
    image_bytes, content_type, filename = _download_controller.prepareDownload(
        session_id=session_id,
        format_str=format,
    )

    return StreamingResponse(
        io.BytesIO(image_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/detect-invisio-image", response_model=APIResponse, tags=["Download"])
async def detect_invisio_image(file: UploadFile = File(...)):
    """POST /detect-invisio-image — detect whether an image contains the Invisio export signature."""
    result = await _signature_controller.detectSignature(file)
    return APIResponse.success(
        message="Image signature analyzed successfully",
        data=result,
    )


@router.get("/hairstyle-presets", response_model=APIResponse, tags=["AI"])
async def get_hairstyle_presets():
    """GET /hairstyle-presets — list available hairstyle presets."""
    result = _hairstyle_controller.listPresets()
    return APIResponse.success(
        message="Hairstyle presets retrieved successfully",
        data=result,
    )


@router.post("/hairstyle-tryon", tags=["AI"])
async def hairstyle_tryon(
    file: UploadFile = File(...),
    style_id: str = Form(""),
    hair_color: str = Form("natural_black"),
):
    """POST /hairstyle-tryon — recolor the detected hair region in an uploaded portrait."""
    image_bytes, content_type, filename = await _hairstyle_controller.generateHairstyle(
        image_file=file,
        style_id=style_id,
        hair_color=hair_color,
    )
    return StreamingResponse(
        io.BytesIO(image_bytes),
        media_type=content_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/hair-transfer", response_model=APIResponse, tags=["AI"])
async def hair_transfer(
    session_id: str = Form(...),
    shape_reference: UploadFile = File(...),
    color_reference: UploadFile = File(...),
):
    """POST /hair-transfer â€” run the three-input hair editing pipeline."""
    result = await _hairstyle_controller.generateHairTransfer(
        session_id=session_id,
        shape_reference_file=shape_reference,
        color_reference_file=color_reference,
    )
    return APIResponse.success(
        message="Hair transfer completed successfully",
        data=result,
    )


@router.delete("/session/{session_id}", response_model=APIResponse, tags=["Session"])
async def delete_session(session_id: str = Path(...)):
    """
    DELETE /session/{session_id} — Expire and cleanup session.
    """
    _session_controller.expireSession(session_id)
    _session_controller.cleanupSession(session_id)
    return APIResponse.success(message="Session terminated and data deleted")


# ===================== AUTH ROUTES =====================


def _extract_bearer_token(authorization: str = Header(...)) -> str:
    """Extracts Bearer token from Authorization header."""
    if not authorization.startswith("Bearer "):
        from app.utils.exceptions import UnauthorizedError
        raise UnauthorizedError("Authorization header must start with 'Bearer '")
    return authorization[7:]


@router.post("/auth/register", response_model=APIResponse, tags=["Auth"])
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    POST /auth/register — Create a new user account.

    Returns JWT access and refresh tokens on success.
    """
    result = await _auth_controller.register(
        db=db,
        email=request.email,
        username=request.username,
        password=request.password,
        consent_given=request.consent_given,
    )
    return APIResponse.success(message="Registration successful", data=result)


@router.post("/auth/login", response_model=APIResponse, tags=["Auth"])
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    POST /auth/login — Authenticate and receive JWT tokens.
    """
    result = await _auth_controller.login(
        db=db, email=request.email, password=request.password
    )
    return APIResponse.success(message="Login successful", data=result)


@router.post("/auth/refresh", response_model=APIResponse, tags=["Auth"])
async def refresh_token(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """
    POST /auth/refresh — Refresh access token using a valid refresh token.
    """
    result = await _auth_controller.refresh(
        db=db, refresh_token=request.refresh_token
    )
    return APIResponse.success(message="Token refreshed", data=result)


@router.get("/auth/me", response_model=APIResponse, tags=["Auth"])
async def get_me(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """
    GET /auth/me — Returns profile of the currently authenticated user.

    Requires 'Authorization: Bearer <access_token>' header.
    """
    token = _extract_bearer_token(authorization)
    result = await _auth_controller.me(db=db, token=token)
    return APIResponse.success(message="User profile retrieved", data=result)


@router.delete("/auth/unregister", response_model=APIResponse, tags=["Auth"])
async def delete_account(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """
    DELETE /auth/unregister — Permanent account deletion (GDPR Right to Erasure).
    """
    token = _extract_bearer_token(authorization)
    user_info = await _auth_controller.me(db=db, token=token)
    result = await _auth_controller.unregister(db=db, user_id=user_info["id"])
    return APIResponse.success(message="Account deleted successfully", data=result)


# ====================== COMMUNITY ROUTES ======================

def _get_community_user(authorization: str = Header(None)):
    """Extracts optional Bearer token, returns None if not present."""
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:]
    return None


@router.post("/community/share", response_model=APIResponse, tags=["Community"])
async def share_to_community(
    session_id: str = Body(...),
    caption: str = Body(None),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """
    POST /community/share — Share current session image to community.
    Requires authentication (Bearer token).
    """
    token = _extract_bearer_token(authorization)
    current_user_dict = await _auth_controller.me(db=db, token=token)
    # me() returns a plain dict; we need the UserDB ORM object for the controller
    from app.repositories.user_repository import UserRepository
    user_db = await UserRepository.get_by_id(db, current_user_dict["id"])

    post = await _community_controller.share_image(
        db=db,
        session_id=session_id,
        current_user=user_db,
        caption=caption,
    )
    return APIResponse.success(
        message="Image shared to community",
        data={"post_id": post.id, "image_url": post.image_url, "shared_at": post.shared_at},
    )

@router.post("/community/share-direct", response_model=APIResponse, tags=["Community"])
async def share_direct_to_community(
    image: UploadFile = File(...),
    caption: str = Form(""),
    ai_operation: str = Form("Standalone"),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...)
):
    """
    POST /community/share-direct — Directly upload an image and share it.
    Requires authentication (Bearer token).
    """
    token = _extract_bearer_token(authorization)
    from app.repositories.user_repository import UserRepository
    current_user_dict = await _auth_controller.me(db=db, token=token)
    user_db = await UserRepository.get_by_id(db, current_user_dict["id"])

    content = await image.read()
    post = await _community_controller.share_direct_image(
        db=db,
        current_user=user_db,
        image_bytes=content,
        caption=caption,
        ai_operation=ai_operation
    )

    return APIResponse.success(
        message="Image shared natively to community",
        data={"post_id": post.id, "image_url": post.image_url, "shared_at": post.shared_at},
    )


@router.get("/community/feed", tags=["Community"])
async def get_community_feed(
    limit: int = Query(default=20, le=50, ge=1),
    cursor: int = Query(default=None),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """
    GET /community/feed — Public paginated community image feed.
    Optional auth for 'is_liked_by_me' tracking.
    """
    current_user_id = None
    if authorization:
        try:
            token = _extract_bearer_token(authorization)
            user_info = await _auth_controller.me(db=db, token=token)
            current_user_id = user_info.get("id")
        except Exception:
            pass

    feed = await _community_controller.get_feed(db=db, current_user_id=current_user_id, limit=limit, cursor=cursor)
    return APIResponse.success(
        message="Community feed retrieved",
        data={"items": [item.model_dump() for item in feed.items], "next_cursor": feed.next_cursor},
    )


@router.get("/community/post/{post_id}", response_model=APIResponse, tags=["Community"])
async def get_community_post(
    post_id: int = Path(...),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """GET /community/post/{id} — Retrieve a single community post by ID."""
    current_user_id = None
    if authorization:
        try:
            token = _extract_bearer_token(authorization)
            user_info = await _auth_controller.me(db=db, token=token)
            current_user_id = user_info.get("id")
        except Exception:
            pass

    post = await _community_controller.get_post(db=db, post_id=post_id, current_user_id=current_user_id)
    return APIResponse.success(message="Post retrieved", data=post.model_dump())


@router.delete("/community/post/{post_id}", response_model=APIResponse, tags=["Community"])
async def delete_community_post(
    post_id: int = Path(...),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """DELETE /community/post/{id} — Delete a community post (owner only)."""
    token = _extract_bearer_token(authorization)
    from app.repositories.user_repository import UserRepository
    user_info = await _auth_controller.me(db=db, token=token)
    user_db = await UserRepository.get_by_id(db, user_info["id"])

    await _community_controller.delete_post(db=db, post_id=post_id, current_user=user_db)
    return APIResponse.success(message="Post deleted successfully")


@router.post("/community/post/{post_id}/like", response_model=APIResponse, tags=["Community"])
async def toggle_like(
    post_id: int = Path(...),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """POST /community/post/{id}/like — Toggle like on a community post."""
    token = _extract_bearer_token(authorization)
    user_info = await _auth_controller.me(db=db, token=token)
    result = await _community_controller.toggle_like(db=db, post_id=post_id, current_user_id=user_info["id"])
    return APIResponse.success(message="Like toggled", data=result)


@router.get("/community/post/{post_id}/comments", response_model=APIResponse, tags=["Community"])
async def get_comments(
    post_id: int = Path(...),
    db: AsyncSession = Depends(get_db),
):
    """GET /community/post/{id}/comments — Retrieve all comments for a post."""
    comments = await _community_controller.get_comments(db=db, post_id=post_id)
    return APIResponse.success(
        message="Comments retrieved",
        data={"items": [c.model_dump() for c in comments]},
    )


@router.post("/community/post/{post_id}/comments", response_model=APIResponse, tags=["Community"])
async def add_comment(
    post_id: int = Path(...),
    text: str = Body(...),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
):
    """POST /community/post/{id}/comments — Add a comment to a community post."""
    token = _extract_bearer_token(authorization)
    from app.repositories.user_repository import UserRepository
    user_info = await _auth_controller.me(db=db, token=token)
    user_db = await UserRepository.get_by_id(db, user_info["id"])

    comment = await _community_controller.add_comment(db=db, post_id=post_id, current_user=user_db, text=text)
    return APIResponse.success(message="Comment added", data=comment.model_dump())


@router.get("/users/{user_id}/shared-images", response_model=APIResponse, tags=["Community"])
async def get_user_shared_posts(
    user_id: int = Path(...),
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(None),
):
    """GET /users/{user_id}/shared-images — Get all posts shared by a specific user."""
    current_user_id = None
    if authorization:
        try:
            token = _extract_bearer_token(authorization)
            user_info = await _auth_controller.me(db=db, token=token)
            current_user_id = user_info.get("id")
        except Exception:
            pass

    posts = await _community_controller.get_user_posts(db=db, target_user_id=user_id, current_user_id=current_user_id)
    return APIResponse.success(
        message="User posts retrieved",
        data={"items": [p.model_dump() for p in posts]},
    )


@router.get("/community/images/file/{filename}", tags=["Community"])
async def serve_community_image(filename: str):
    """GET /community/images/file/{filename} — Serve a stored community image file."""
    settings = get_settings()
    safe_name = os.path.basename(filename)  # Prevent directory traversal
    file_path = os.path.join(settings.COMMUNITY_STORAGE_DIR, safe_name)
    if not os.path.exists(file_path):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(file_path)
