"""
AIModelFactory — LLD §3.1.1, Class: AIModelFactory
HLD Module: AI Processing Layer — Factory

Responsible for creating and managing AIModel instances.
Encapsulates object creation logic and supports Open/Closed Principle compliance.

Uses Strategy Pattern:
    - Models are registered during application startup
    - Controllers request models by EditingType
    - Factory returns the appropriate AIModel instance
    - New models can be added without modifying existing code
"""

from __future__ import annotations
import logging
from typing import Dict, Optional

from app.ai.base import AIModel
from app.model.editing_request import EditingType
from app.utils.exceptions import ModelNotFoundError

logger = logging.getLogger(__name__)


class AIModelFactory:
    """
    LLD §3.1.1 — Class AIModelFactory

    Attributes:
        modelRegistry (Dict[EditingType, AIModel]): Registered model mappings
    """

    def __init__(self):
        self._modelRegistry: Dict[EditingType, AIModel] = {}

    def createModel(self, editing_type: EditingType) -> AIModel:
        """
        Returns the appropriate AI model for the requested editing type.
        
        Args:
            editing_type: The type of editing operation.
            
        Returns:
            Registered AIModel instance for the given type.
            
        Raises:
            ModelNotFoundError: If no model is registered for the given type.
        """
        model = self._modelRegistry.get(editing_type)
        if model is None:
            raise ModelNotFoundError(
                f"No model registered for editing type: {editing_type.value}"
            )
        return model

    def registerModel(self, editing_type: EditingType, model: AIModel) -> None:
        """
        Registers a new AI model for a given editing type.
        
        This is called during application startup to populate the registry.
        
        Args:
            editing_type: The editing type this model handles.
            model: AIModel instance to register.
        """
        logger.info(
            f"Registering model '{model.modelName}' v{model.version} "
            f"for type '{editing_type.value}'"
        )
        self._modelRegistry[editing_type] = model

    def supports(self, editing_type: EditingType) -> bool:
        """
        Checks whether a model is available for the given editing type.
        
        Args:
            editing_type: The editing type to check.
            
        Returns:
            True if a model is registered for this type.
        """
        return editing_type in self._modelRegistry

    def loadAllModels(self) -> None:
        """
        Loads all registered models into memory.
        Called once at application startup.
        """
        logger.info(f"Loading {len(self._modelRegistry)} registered models...")
        for editing_type, model in self._modelRegistry.items():
            if not model.isLoaded():
                try:
                    logger.info(f"Loading model for '{editing_type.value}'...")
                    model.loadModel()
                except Exception as e:
                    logger.error(f"Failed to load model for '{editing_type.value}': {e}")
                    model.loaded = True  # Mark as loaded (but unavailable) to prevent retry loop
        logger.info("All models loaded successfully.")

    def unloadAllModels(self) -> None:
        """
        Unloads all registered models from memory.
        Called at application shutdown.
        """
        logger.info("Unloading all models...")
        for model in self._modelRegistry.values():
            if model.isLoaded():
                model.unloadModel()
        logger.info("All models unloaded.")

    def getRegisteredTypes(self) -> list:
        """Returns list of all registered editing types."""
        return list(self._modelRegistry.keys())


def create_default_factory(hairstyle_service=None) -> AIModelFactory:
    """
    Creates and configures an AIModelFactory with all models registered.

    Segmentation / Background removal → U2NetSegmentationModel (Fatih's real implementation)
    Inpainting / Object removal → LamaInpaintingModel (Fatih's real implementation)
    All others → Placeholder implementations (ready for future real models)

    Returns:
        Configured AIModelFactory instance.
    """
    from app.ai.enhancement import EnhancementModel
    from app.ai.style_transfer import StyleTransferModel
    from app.ai.beautification import BeautificationModel
    from app.ai.colorization import ColorizationModel
    from app.ai.nsfw_detection import NSFWDetectionModel
    from app.ai.hair_refiner import HairRefinerModel
    from app.ai.aging import AgeTransformationModel
    from app.ai.hairstyle import HairstyleModel

    # Real AI implementations (from Fatih)
    from app.ai.u2net_segmentation import U2NetSegmentationModel
    from app.ai.lama_inpainting import LamaInpaintingModel
    from app.ai.face_editing import FaceEditingModel
    from app.services.hairstyle_service import HairstyleTryOnService

    # Placeholder (stub) implementations — kept for compatibility
    from app.ai.segmentation import SegmentationModel
    from app.ai.inpainting import InpaintingModel

    factory = AIModelFactory()

    # ---- Real models (Fatih's implementations) ----
    # U2Net handles segmentation AND background removal (same model, different output)
    factory.registerModel(EditingType.SEGMENTATION, U2NetSegmentationModel())
    factory.registerModel(EditingType.BACKGROUND_REPLACE, U2NetSegmentationModel())

    # LaMa handles all inpainting-based operations
    factory.registerModel(EditingType.INPAINTING, LamaInpaintingModel())
    factory.registerModel(EditingType.OBJECT_REMOVAL, LamaInpaintingModel())

    # ---- Placeholder models (to be replaced when real models are integrated) ----
    factory.registerModel(EditingType.ENHANCEMENT, EnhancementModel())
    factory.registerModel(EditingType.STYLE_TRANSFER, StyleTransferModel())
    factory.registerModel(EditingType.BEAUTIFICATION, BeautificationModel())
    factory.registerModel(EditingType.COLORIZATION, ColorizationModel())
    factory.registerModel(EditingType.NSFW_DETECTION, NSFWDetectionModel())
    factory.registerModel(EditingType.HAIR_REFINER, HairRefinerModel())
    factory.registerModel(EditingType.FACE_EDIT, FaceEditingModel())
    factory.registerModel(EditingType.AGING, AgeTransformationModel())
    factory.registerModel(EditingType.REJUVENATION, AgeTransformationModel())
    factory.registerModel(
        EditingType.HAIRSTYLE,
        HairstyleModel(hairstyle_service=hairstyle_service or HairstyleTryOnService()),
    )

    return factory

