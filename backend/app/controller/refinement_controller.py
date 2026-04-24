"""
RefinementController — LLD §3.1.2, Class: RefinementController
HLD Module: Controller Layer — Mask Refinement

Manages mask refinement operations after AI-based segmentation.
Enables user-driven correction and regenerates final output.
"""

import uuid
import base64
import logging

import numpy as np

from app.model.mask import Mask
from app.model.refinement_tool import RefinementTool
from app.model.editing_request import EditingRequest, EditingType
from app.services.session_service import SessionService
from app.controller.session_controller import SessionController
from app.controller.security_controller import SecurityController
from app.ai.factory import AIModelFactory
from app.utils.exceptions import ValidationError, ProcessingError

logger = logging.getLogger(__name__)


class RefinementController:
    """
    LLD §3.1.2 — Class RefinementController

    Attributes:
        refinementTool (RefinementTool): Mask correction functionality
        sessionController (SessionController): Session management
        securityController (SecurityController): Security validation
    """

    def __init__(
        self,
        session_service: SessionService,
        session_controller: SessionController,
        security_controller: SecurityController,
        model_factory: AIModelFactory,
    ):
        self.refinementTool = RefinementTool()
        self.sessionService = session_service
        self.sessionController = session_controller
        self.securityController = security_controller
        self.modelFactory = model_factory

    def refineMask(
        self,
        session_id: str,
        brush_data_b64: str,
        brush_size: int = 10,
        brush_strength: float = 1.0,
    ) -> dict:
        """
        Applies user-driven mask adjustments.
        
        Args:
            session_id: Session ID.
            brush_data_b64: Base64-encoded brush input data.
            brush_size: Brush radius.
            brush_strength: Brush intensity.
            
        Returns:
            Dictionary with refined mask data.
        """
        self.sessionController.validateSession(session_id)

        image = self.sessionService.getImage(session_id)
        if image is None:
            raise ValidationError(
                message="No image found in session",
                error_code="NO_IMAGE",
            )

        # Generate segmentation mask if not exists
        seg_model = self.modelFactory.createModel(EditingType.SEGMENTATION)
        seg_request = EditingRequest(
            requestId=str(uuid.uuid4()),
            editingType=EditingType.SEGMENTATION,
        )
        original_mask = seg_model.generateMask(image)

        # Decode brush input
        try:
            brush_bytes = base64.b64decode(brush_data_b64)
            brush_input = np.frombuffer(brush_bytes, dtype=np.uint8).reshape(
                (image.height, image.width)
            )
        except Exception as e:
            raise ValidationError(
                message=f"Invalid brush data: {str(e)}",
                error_code="INVALID_BRUSH_DATA",
            )

        # Apply refinement
        self.refinementTool.brushSize = brush_size
        self.refinementTool.brushStrength = brush_strength
        refined_mask = self.refinementTool.applyRefinement(original_mask, brush_input)

        mask_b64 = base64.b64encode(refined_mask.to_bytes()).decode("utf-8")

        return {
            "session_id": session_id,
            "mask_width": refined_mask.width,
            "mask_height": refined_mask.height,
            "mask_data": mask_b64,
        }

    def regenerateImage(self, session_id: str, refined_mask_b64: str) -> dict:
        """
        Reprocesses image using updated mask.
        
        Args:
            session_id: Session ID.
            refined_mask_b64: Base64-encoded refined mask.
            
        Returns:
            Dictionary with regenerated result data.
        """
        self.sessionController.validateSession(session_id)

        image = self.sessionService.getImage(session_id)
        if image is None:
            raise ValidationError(message="No image found", error_code="NO_IMAGE")

        # Decode mask
        mask_bytes = base64.b64decode(refined_mask_b64)
        mask = Mask.from_bytes(mask_bytes, image.width, image.height)

        # Run inpainting with refined mask
        inpainting_model = self.modelFactory.createModel(EditingType.INPAINTING)
        request = EditingRequest(
            requestId=str(uuid.uuid4()),
            editingType=EditingType.INPAINTING,
            parameters={"mask_data": mask_bytes},
        )
        result = inpainting_model.process(image, request)

        self.sessionService.storeResult(session_id, result)

        result_b64 = base64.b64encode(result.getData()).decode("utf-8")
        return {
            "session_id": session_id,
            "result_id": result.resultId,
            "result_image": result_b64,
            "format": result.format,
        }
