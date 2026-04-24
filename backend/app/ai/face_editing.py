"""
FaceEditingModel — LLD §3.1.1, Class: FaceEditingModel (extends AIModel)
HLD Module: AI Processing Layer

Implements localized facial feature editing (eyes, nose, mouth, etc.)
using MediaPipe Face Landmarker and OpenCV warping techniques.
"""

from __future__ import annotations
import io
import logging
from typing import Dict, Any, List, Tuple
from PIL import Image as PILImage

try:
    import numpy as np
    import cv2
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    np = None
    cv2 = None

from app.ai.base import AIModel
from app.model.image import Image
from app.model.editing_request import EditingRequest
from app.model.result_image import ResultImage

logger = logging.getLogger(__name__)

class FaceEditingModel(AIModel):
    """
    LLD §3.1.1 — Class FaceEditingModel (extends AIModel)
    
    Uses MediaPipe Face Mesh to detect facial landmarks and OpenCV
    for piecewise affine warping or mesh deformation.
    """

    # Landmark indices for facial regions (Canonical MediaPipe Face Mesh)
    REGIONS = {
        "left_eye": [33, 160, 158, 133, 153, 144],
        "right_eye": [362, 385, 387, 263, 373, 380],
        "left_eyebrow": [70, 63, 105, 66, 107],
        "right_eyebrow": [300, 293, 334, 296, 336],
        "nose": [1, 2, 98, 327, 278, 48, 4, 195],
        "mouth": [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291],
        "jaw": [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10]
    }

    def __init__(self, **kwargs):
        super().__init__(modelName="FaceEditingModel", **kwargs)
        self._landmarker = None

    def loadModel(self) -> None:
        """Initializes MediaPipe Face Landmarker using the Tasks API."""
        if not _CV2_AVAILABLE:
            logger.warning("FaceEditingModel: cv2/numpy not available — model unavailable")
            self.loaded = True
            return

        try:
            import os
            from mediapipe.tasks import python
            from mediapipe.tasks.python import vision
            
            logger.info(f"Loading MediaPipe Face Landmarker for {self.modelName}")
            
            model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "face_landmarker.task"))
            
            if not os.path.exists(model_path):
                logger.error(f"MediaPipe model not found at {model_path}")
                model_path = "face_landmarker.task"

            base_options = python.BaseOptions(model_asset_path=model_path)
            options = vision.FaceLandmarkerOptions(
                base_options=base_options,
                output_face_blendshapes=True,
                output_facial_transformation_matrixes=True,
                num_faces=1
            )
            self._landmarker = vision.FaceLandmarker.create_from_options(options)
        except Exception as e:
            logger.error(f"Failed to load FaceEditingModel: {e}")
        self.loaded = True

    def unloadModel(self) -> None:
        """Closes MediaPipe Face Landmarker."""
        if self._landmarker:
            self._landmarker.close()
        self.loaded = False

    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        """
        Main entry point for facial feature editing.
        """
        self._ensure_loaded()

        if not _CV2_AVAILABLE or self._landmarker is None:
            logger.warning("FaceEditingModel unavailable — returning original image")
            return self.postprocess(image.rawData)

        import mediapipe as mp
        
        # Extract parameters
        params = request.parameters
        left_eye_scale = params.get("left_eye_scale", 1.0)
        right_eye_scale = params.get("right_eye_scale", 1.0)
        nose_scale = params.get("nose_scale", 1.0)
        mouth_scale = params.get("mouth_scale", 1.0)
        left_eyebrow_scale = params.get("left_eyebrow_scale", 1.0)
        right_eyebrow_scale = params.get("right_eyebrow_scale", 1.0)
        jaw_scale = params.get("jaw_scale", 1.0)

        # Convert image to numpy array (RGBA if possible, otherwise RGB)
        raw_io = io.BytesIO(image.rawData)
        pil_img = PILImage.open(raw_io)
        has_alpha = pil_img.mode == 'RGBA'
        if has_alpha:
            np_img = np.array(pil_img) # Keep RGBA
        else:
            np_img = np.array(pil_img.convert("RGB"))
        
        h, w = np_img.shape[:2]

        # Detect landmarks using Tasks API
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np_img)
        detection_result = self._landmarker.detect(mp_image)
        
        if not detection_result.face_landmarks:
            logger.warning("No face detected for editing.")
            return self.postprocess(image.rawData)

        # Convert normalized landmarks to pixel coordinates
        landmarks = detection_result.face_landmarks[0]
        points = []
        for lm in landmarks:
            points.append((int(lm.x * w), int(lm.y * h)))
        points = np.array(points)

        if "source_points" in request.parameters and "target_points" in request.parameters:
            src_pts = np.array(request.parameters["source_points"])
            dst_pts = np.array(request.parameters["target_points"])
            edited_img = self._warp_and_blend(np_img, src_pts, dst_pts)
        else:
            # Reconstruct legacy target points if using sliders (fallback)
            edited_img = self._apply_face_edits(
                np_img, points,
                {
                    "left_eye": left_eye_scale,
                    "right_eye": right_eye_scale,
                    "nose": nose_scale,
                    "mouth": mouth_scale,
                    "left_eyebrow": left_eyebrow_scale,
                    "right_eyebrow": right_eyebrow_scale,
                    "jaw": jaw_scale
                }
            )

        # Convert back to bytes
        res_pil = PILImage.fromarray(edited_img)
        buffer = io.BytesIO()
        res_pil.save(buffer, format="PNG")
        
        return self.postprocess(buffer.getvalue())

    def get_landmarks(self, image: Image) -> List[Tuple[int, int]]:
        """
        Detects and returns facial landmarks as pixel coordinates.
        """
        self._ensure_loaded()
        if not _CV2_AVAILABLE or self._landmarker is None:
            return []

        import mediapipe as mp
        pil_img = PILImage.open(io.BytesIO(image.rawData)).convert("RGB")
        np_img = np.array(pil_img)
        h, w = np_img.shape[:2]

        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=np_img)
        detection_result = self._landmarker.detect(mp_image)
        
        if not detection_result.face_landmarks:
            return []

        landmarks = detection_result.face_landmarks[0]
        points = []
        for lm in landmarks:
            points.append((int(lm.x * w), int(lm.y * h)))
        return points

    def _warp_and_blend(self, img: np.ndarray, src_pts: np.ndarray, dst_pts: np.ndarray) -> np.ndarray:
        """
        Warping with points, then deterministic Contrast Matching and Poisson Blending.
        """
        warped_img = self._warp_image(img, src_pts, dst_pts)
        
        # 1. Deterministic Contrast/Color Matching (Global)
        # We ensure the warped face matches the global statistics of the original image
        blended_img = self._match_contrast(warped_img, img)
        
        # 2. Poisson Blend mask for seamless boundary
        hull = cv2.convexHull(dst_pts.astype(np.int32))
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        cv2.fillConvexPoly(mask, hull, 255)
        
        # Erosion to avoid boundary seam artifacts
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=2)
        
        M = cv2.moments(hull)
        if M["m00"] != 0:
            cX = int(M["m10"] / M["m00"])
            cY = int(M["m01"] / M["m00"])
        else:
            cX, cY = img.shape[1]//2, img.shape[0]//2
            
        try:
            # We use normalization to combine the warped result with the original context seamlessly
            final = cv2.seamlessClone(blended_img, img, mask, (cX, cY), cv2.NORMAL_CLONE)
            return final
        except Exception as e:
            logger.error(f"Poisson blending failed: {e}")
            return blended_img

    def _match_contrast(self, source: np.ndarray, target: np.ndarray) -> np.ndarray:
        """
        Deterministic algorithm to match contrast/lighting based on global stats (Reinhard-lite).
        Ensures the warped region doesn't look like a 'sticker'.
        """
        source_lab = cv2.cvtColor(source, cv2.COLOR_RGB2LAB).astype("float32")
        target_lab = cv2.cvtColor(target, cv2.COLOR_RGB2LAB).astype("float32")

        # Compute stats for L, A, B channels
        (l_s, a_s, b_s) = cv2.split(source_lab)
        (l_t, a_t, b_t) = cv2.split(target_lab)

        l_s_mean, l_s_std = l_s.mean(), l_s.std()
        a_s_mean, a_s_std = a_s.mean(), a_s.std()
        b_s_mean, b_s_std = b_s.mean(), b_s.std()

        l_t_mean, l_t_std = l_t.mean(), l_t.std()
        a_t_mean, a_t_std = a_t.mean(), a_t.std()
        b_t_mean, b_t_std = b_t.mean(), b_t.std()

        # Scale and shift channels
        l = (l_s - l_s_mean) * (l_t_std / (l_s_std + 1e-5)) + l_t_mean
        a = (a_s - a_s_mean) * (a_t_std / (a_s_std + 1e-5)) + a_t_mean
        b = (b_s - b_s_mean) * (b_t_std / (b_s_std + 1e-5)) + b_t_mean

        # Clip and convert back
        l = np.clip(l, 0, 255)
        a = np.clip(a, 0, 255)
        b = np.clip(b, 0, 255)

        matched = cv2.merge([l, a, b])
        matched = cv2.cvtColor(matched.astype("uint8"), cv2.COLOR_LAB2RGB)

        # Preserve Alpha if present
        if source.shape[2] == 4:
            alpha = source[:, :, 3]
            matched = cv2.merge([matched[:,:,0], matched[:,:,1], matched[:,:,2], alpha])
            
        return matched

    def _apply_face_edits(self, img: np.ndarray, points: np.ndarray, scales: Dict[str, float]) -> np.ndarray:
        """
        Legacy slider-based calculations.
        """
        h, w = img.shape[:2]
        target_points = points.copy().astype(float)

        for region, scale in scales.items():
            if scale == 1.0:
                continue
            
            region_indices = self.REGIONS.get(region, [])
            if not region_indices:
                continue

            region_pts = points[region_indices]
            center = np.mean(region_pts, axis=0)

            # Scale landmarks relative to center
            for idx in region_indices:
                target_points[idx] = center + (points[idx] - center) * scale

        # Warping & Blending
        return self._warp_and_blend(img, points, target_points)

    def _warp_image(self, img: np.ndarray, src_pts: np.ndarray, dst_pts: np.ndarray) -> np.ndarray:
        """
        Performs piecewise affine warp using Delaunay triangulation.
        """
        h, w = img.shape[:2]
        
        # Add corners to keep boundary stable
        corners = np.array([[0, 0], [w-1, 0], [0, h-1], [w-1, h-1], 
                           [w//2, 0], [w//2, h-1], [0, h//2], [w-1, h//2]])
        
        full_src = np.vstack([src_pts, corners])
        full_dst = np.vstack([dst_pts, corners])
        
        # Delaunay triangulation on source points
        rect = (0, 0, w, h)
        subdiv = cv2.Subdiv2D(rect)
        for p in full_src:
            subdiv.insert((float(p[0]), float(p[1])))
        
        triangles = subdiv.getTriangleList()
        
        dst_img = np.zeros_like(img)
        # Use single channel mask for geometry, but expansion handled in _warp_triangle
        channels = img.shape[2]

        for t in triangles:
            # Triangle corners
            pts_src = np.array([(t[0], t[1]), (t[2], t[3]), (t[4], t[5])], dtype=np.float32)
            
            # Find indices in full_src
            indices = []
            for p in pts_src:
                # Find the closest point in full_src
                dists = np.sum((full_src - p)**2, axis=1)
                indices.append(np.argmin(dists))
            
            pts_dst = full_dst[indices].astype(np.float32)
            
            # Warp triangle
            self._warp_triangle(img, dst_img, pts_src, pts_dst)
            
        return dst_img

    def _warp_triangle(self, src: np.ndarray, dst: np.ndarray, src_tri: np.ndarray, dst_tri: np.ndarray):
        """
        Warps a single triangle from src to dst.
        """
        # Get bounding box for each triangle
        r1 = cv2.boundingRect(src_tri)
        r2 = cv2.boundingRect(dst_tri)

        # Offset points by bounding box top-left corner
        src_tri_cropped = []
        dst_tri_cropped = []

        for i in range(3):
            src_tri_cropped.append(((src_tri[i][0] - r1[0]), (src_tri[i][1] - r1[1])))
            dst_tri_cropped.append(((dst_tri[i][0] - r2[0]), (dst_tri[i][1] - r2[1])))

        # Crop input image
        img1_cropped = src[r1[1]:r1[1] + r1[3], r1[0]:r1[0] + r1[2]]

        # Affine transform
        warp_mat = cv2.getAffineTransform(np.float32(src_tri_cropped), np.float32(dst_tri_cropped))
        
        # Apply affine transform to cropped input image
        img2_cropped = cv2.warpAffine(img1_cropped, warp_mat, (r2[2], r2[3]), None, 
                                     flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

        # Create mask for triangle (with correct number of channels)
        num_channels = src.shape[2]
        mask = np.zeros((r2[3], r2[2], num_channels), dtype=np.float32)
        cv2.fillConvexPoly(mask, np.int32(dst_tri_cropped), (1.0,) * num_channels, 16, 0)

        # Copy triangular region from img2_cropped to output image using the weights
        roi_dst = dst[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]]
        dst[r2[1]:r2[1] + r2[3], r2[0]:r2[0] + r2[2]] = roi_dst * (1 - mask) + img2_cropped * mask
