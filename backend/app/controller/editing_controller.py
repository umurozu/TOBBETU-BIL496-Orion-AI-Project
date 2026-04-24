"""
EditingController — LLD §3.1.2, Class: EditingController <<Facade>>
HLD Module: Controller Layer — AI Editing Orchestration

Acts as a facade for AI-based editing operations.
Coordinates model selection, request validation, and processing
through the AIModelFactory.

API Route: POST /process
"""

from __future__ import annotations
import uuid
import base64
import logging

from app.model.editing_request import EditingRequest, EditingType
from app.model.result_image import ResultImage
from app.ai.factory import AIModelFactory
from app.ai.base import AIModel
from app.services.session_service import SessionService
from app.controller.session_controller import SessionController
from app.controller.security_controller import SecurityController
from app.utils.exceptions import InvisioBaseError, ValidationError, ProcessingError

logger = logging.getLogger(__name__)


class EditingController:
    """
    LLD §3.1.2 — Class EditingController <<Facade>>

    Attributes:
        modelFactory (AIModelFactory): Factory for AI model instantiation
        sessionController (SessionController): Session management
        securityController (SecurityController): Security validation
    """

    def __init__(
        self,
        model_factory: AIModelFactory,
        session_service: SessionService,
        session_controller: SessionController,
        security_controller: SecurityController,
    ):
        self.modelFactory = model_factory
        self.sessionService = session_service
        self.sessionController = session_controller
        self.securityController = security_controller

    def applyEditing(self, session_id: str, editing_type_str: str, parameters: dict) -> dict:
        """
        Applies selected editing operation.
        """
        logger.info(f"Processing edit: type={editing_type_str}, session={session_id}")

        # Step 1: Validate session
        self.sessionController.validateSession(session_id)

        # Step 2: Parse editing type
        editing_type = self._parseEditingType(editing_type_str)

        # Step 3: Create editing request
        request = EditingRequest(
            requestId=str(uuid.uuid4()),
            editingType=editing_type,
            parameters=parameters,
        )

        # Step 4: Validate request
        self._validateEditingRequest(request)

        # Step 5: Get image from session
        image = self.sessionService.getImage(session_id)
        if image is None:
            raise ValidationError(
                message="No image found in session. Please upload first.",
                error_code="NO_IMAGE",
            )

        # Step 6: Update processing status
        self.sessionService.setProcessingStatus(session_id, "processing")

        try:
            # Step 7: Handle special mask detection operations
            if editing_type == EditingType.SEGMENTATION:
                import io
                from PIL import Image as PILImage
                
                mask = None
                if editing_type_str == "detect_mask":
                    seg_model = self.modelFactory.createModel(EditingType.SEGMENTATION)
                    mask = seg_model.generateMask(image)
                elif editing_type_str == "detect_hair_mask":
                    hair_model = self.modelFactory.createModel(EditingType.HAIRSTYLE)
                    if hasattr(hair_model, "generateMask"):
                        mask = hair_model.generateMask(image)
                    else:
                        raise ProcessingError("Hair mask detection not supported by model")
                
                if mask:
                    # Convert mask (numpy array) to PNG bytes
                    pil_mask = PILImage.fromarray(mask.maskData, mode="L")
                    buf = io.BytesIO()
                    pil_mask.save(buf, format="PNG")
                    mask_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                    
                    return {
                        "session_id": session_id,
                        "result_id": str(uuid.uuid4()),
                        "result_image": mask_b64,
                        "format": "png",
                    }

            # Step 8: Select AI model via factory
            model = self._selectModel(editing_type)

            # Step 9: Execute inference
            result = model.process(image, request)

            # Step 10: Store result in session
            self.sessionService.storeResult(session_id, result)

            # Step 11: Encode result for response
            result_b64 = base64.b64encode(result.getData()).decode("utf-8")

            logger.info(f"Edit complete: session={session_id}, result={result.resultId}")

            return {
                "session_id": session_id,
                "result_id": result.resultId,
                "result_image": result_b64,
                "format": result.format,
            }

        except InvisioBaseError as e:
            self.sessionService.setProcessingStatus(session_id, "error")
            logger.error(f"Processing failed for session {session_id} with {e.error_code}: {e.message}")
            raise
        except Exception as e:
            self.sessionService.setProcessingStatus(session_id, "error")
            logger.error(f"Processing failed for session {session_id}: {str(e)}", exc_info=True)
            raise ProcessingError(f"AI processing failed: {str(e)}")

    def getLandmarks(self, session_id: str) -> dict:
        """
        Retrieves facial landmarks for the session image.
        """
        self.sessionController.validateSession(session_id)
        image = self.sessionService.getImage(session_id)
        if image is None:
            raise ValidationError("No image in session", "NO_IMAGE")

        model = self.modelFactory.createModel(EditingType.FACE_EDIT)
        if hasattr(model, "get_landmarks"):
            points = model.get_landmarks(image)
            return {"status": "success", "data": {"points": points}}
        
        return {"status": "error", "message": "Landmark detection not supported by model"}

    def _selectModel(self, editing_type: EditingType) -> AIModel:
        """Determines appropriate AI model via factory."""
        return self.modelFactory.createModel(editing_type)

    def _validateEditingRequest(self, request: EditingRequest) -> None:
        """Ensures request parameters are valid."""
        request.validate()

    def _parseEditingType(self, type_str: str) -> EditingType:
        """Converts string to EditingType enum."""
        if type_str in ["detect_mask", "detect_hair_mask"]:
            return EditingType.SEGMENTATION
        try:
            return EditingType(type_str.lower())
        except ValueError:
            raise ValidationError(
                message=f"Unknown editing type: '{type_str}'. "
                        f"Available: {[t.value for t in EditingType]}",
                error_code="INVALID_EDITING_TYPE",
            )
