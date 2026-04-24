"""
AI Layer Package — LLD §3.1.1 (AIModel hierarchy)
HLD Module: AI Processing Layer

Contains abstract AIModel interface and all concrete model implementations.
"""

from app.ai.base import AIModel
from app.ai.segmentation import SegmentationModel
from app.ai.inpainting import InpaintingModel
from app.ai.enhancement import EnhancementModel
from app.ai.style_transfer import StyleTransferModel
from app.ai.beautification import BeautificationModel
from app.ai.colorization import ColorizationModel
from app.ai.nsfw_detection import NSFWDetectionModel
from app.ai.hair_refiner import HairRefinerModel
from app.ai.factory import AIModelFactory, create_default_factory

__all__ = [
    "AIModel",
    "SegmentationModel",
    "InpaintingModel",
    "EnhancementModel",
    "StyleTransferModel",
    "BeautificationModel",
    "ColorizationModel",
    "NSFWDetectionModel",
    "HairRefinerModel",
    "AIModelFactory",
    "create_default_factory",
]
