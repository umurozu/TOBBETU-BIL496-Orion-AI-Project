"""
RefinementTool Model — LLD §3.1.1, Class: RefinementTool
HLD Module: Model Layer — Core Domain

Provides manual mask adjustment functionality after AI-based processing.
Allows users to modify masks using brush operations.
"""

from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from app.model.mask import Mask


@dataclass
class RefinementTool:
    """
    LLD §3.1.1 — Class RefinementTool

    Attributes:
        brushSize (int): Brush radius in pixels
        brushStrength (float): Brush intensity (0.0 to 1.0)
    """

    brushSize: int = 10
    brushStrength: float = 1.0

    def applyRefinement(self, mask: Mask, brushInput: np.ndarray) -> Mask:
        """
        Applies refinement to mask using brush input.
        
        Creates a modified copy of the mask with brush adjustments applied.
        The brush strength scales the intensity of the refinement.
        
        Args:
            mask: Original Mask instance to refine.
            brushInput: 2D numpy array representing brush strokes.
            
        Returns:
            New Mask instance with refinements applied.
        """
        # Scale brush input by brush strength
        scaled_input = (brushInput * self.brushStrength).astype(np.uint8)

        # Create a refined copy of the mask
        refined_data = mask.maskData.copy()
        non_zero = scaled_input > 0
        refined_data[non_zero] = scaled_input[non_zero]

        return Mask(
            maskData=refined_data,
            confidenceScore=mask.confidenceScore,
            width=mask.width,
            height=mask.height,
        )
