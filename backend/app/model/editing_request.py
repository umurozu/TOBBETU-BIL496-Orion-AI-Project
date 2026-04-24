"""
EditingRequest Model — LLD §3.1.1, Class: EditingRequest
HLD Module: Model Layer — Core Domain

Encapsulates a user-initiated editing operation, including editing type
and model parameters.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional

from app.utils.exceptions import ValidationError


class EditingType(str, Enum):
    """
    Supported editing operation types.
    Maps directly to AIModel concrete implementations (LLD §3.1.1).
    """
    SEGMENTATION = "segmentation"
    INPAINTING = "inpainting"
    OBJECT_REMOVAL = "object_removal"
    BACKGROUND_REPLACE = "background_replace"
    ENHANCEMENT = "enhancement"
    STYLE_TRANSFER = "style_transfer"
    BEAUTIFICATION = "beautification"
    COLORIZATION = "colorization"
    NSFW_DETECTION = "nsfw_detection"
    HAIR_REFINER = "hair_refiner"
    FACE_EDIT = "face_edit"
    AGING = "aging"
    REJUVENATION = "rejuvenation"
    HAIRSTYLE = "hairstyle"


@dataclass
class EditingRequest:
    """
    LLD §3.1.1 — Class EditingRequest

    Attributes:
        requestId (str): Unique request identifier
        editingType (EditingType): Requested editing operation
        parameters (Dict[str, Any]): Operation-specific parameters
        requestedAt (datetime): Request timestamp
    """

    requestId: str
    editingType: EditingType
    parameters: Dict[str, Any] = field(default_factory=dict)
    requestedAt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def getParameter(self, key: str) -> Optional[Any]:
        """
        Retrieves a parameter value by key.

        Args:
            key: Parameter key name.

        Returns:
            Parameter value or None if not found.
        """
        return self.parameters.get(key)

    def validate(self) -> None:
        """
        Validates request consistency.
        
        Raises:
            ValidationError: If editing type is invalid or required parameters are missing.
        """
        if not self.requestId:
            raise ValidationError(
                message="Request ID cannot be empty",
                error_code="INVALID_REQUEST_ID",
            )

        if not isinstance(self.editingType, EditingType):
            raise ValidationError(
                message=f"Invalid editing type: {self.editingType}",
                error_code="INVALID_EDITING_TYPE",
            )

        # Validate type-specific required parameters
        required_params = self._get_required_params()
        for param in required_params:
            if param not in self.parameters:
                raise ValidationError(
                    message=f"Missing required parameter '{param}' for {self.editingType.value}",
                    error_code="MISSING_PARAMETER",
                )

    def _get_required_params(self) -> list:
        """Returns required parameters for each editing type."""
        param_map = {
            EditingType.INPAINTING: [],
            EditingType.OBJECT_REMOVAL: [],
            EditingType.BACKGROUND_REPLACE: [],
            EditingType.ENHANCEMENT: [],
            EditingType.STYLE_TRANSFER: [],
            EditingType.BEAUTIFICATION: [],
            EditingType.COLORIZATION: [],
            EditingType.SEGMENTATION: [],
            EditingType.NSFW_DETECTION: [],
            EditingType.HAIR_REFINER: [],
            EditingType.FACE_EDIT: [],
            EditingType.AGING: [],
            EditingType.REJUVENATION: [],
            EditingType.HAIRSTYLE: [],
        }
        return param_map.get(self.editingType, [])
