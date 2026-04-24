"""
AIModel Abstract Base — LLD §3.1.1, Class: AIModel (Abstract)
HLD Module: AI Processing Layer

Defines the common contract for all AI-based image processing strategies.
Implements the Strategy design pattern and enforces a unified processing
interface for extensibility and maintainability.

CRITICAL: When plugging in real AI models, subclasses must implement:
    - process(image, request) -> ResultImage
    - Override preprocess() and postprocess() as needed for the specific model

The load_model() / unload_model() lifecycle is managed by the application:
    - Models are loaded at startup via AIModelFactory
    - Models are unloaded at shutdown
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import io
import logging

from app.model.image import Image
from app.model.editing_request import EditingRequest
from app.model.result_image import ResultImage
from app.config.settings import get_settings

logger = logging.getLogger(__name__)

try:
    import torch
except ImportError:
    torch = None


class AIModel(ABC):
    """
    LLD §3.1.1 — Class AIModel (Abstract)
    
    Strategy Pattern base class for all AI processing models.
    
    Attributes:
        modelName (str): Logical name of the model
        version (str): Model version identifier
        loaded (bool): Whether model weights are loaded
        inputWidth (int): Expected input width
        inputHeight (int): Expected input height
        device (str): Execution device (CPU / GPU)
    """

    def __init__(
        self,
        modelName: str,
        version: str = "1.0.0",
        inputWidth: Optional[int] = None,
        inputHeight: Optional[int] = None,
        device: Optional[str] = None,
    ):
        settings = get_settings()
        self.modelName = modelName
        self.version = version
        self.loaded = False
        self.inputWidth = inputWidth or settings.MODEL_INPUT_WIDTH
        self.inputHeight = inputHeight or settings.MODEL_INPUT_HEIGHT
        configured_device = (device or settings.DEVICE).lower().strip()
        if configured_device == "cuda" and torch is not None and torch.cuda.is_available():
            self.device = "cuda"
        else:
            self.device = "cpu"
        self._model = None  # Placeholder for actual model instance

    @abstractmethod
    def process(self, image: Image, request: EditingRequest) -> ResultImage:
        """
        Executes model inference pipeline: preprocess → infer → postprocess.
        
        This is the main entry point for AI processing. Concrete implementations
        must orchestrate the full pipeline.
        
        Args:
            image: Input Image instance with validated raw data.
            request: EditingRequest with operation parameters.
            
        Returns:
            ResultImage containing the processed output.
            
        Raises:
            ProcessingError: If inference fails.
        """
        pass

    def loadModel(self) -> None:
        """
        Loads model weights into memory.
        
        Called at application startup. Subclasses should override this to:
        1. Load model weights from disk or registry
        2. Move model to the configured device (CPU/GPU)
        3. Set self._model to the loaded model instance
        4. Set self.loaded = True
        
        Example for PyTorch:
            def loadModel(self):
                self._model = torch.load("model.pt", map_location=self.device)
                self._model.eval()
                self.loaded = True
        """
        logger.info(
            f"Loading model '{self.modelName}' v{self.version} on device={self.device}"
        )
        # Subclasses override this with actual model loading
        self.loaded = True
        logger.info(f"Model '{self.modelName}' loaded successfully")

    def unloadModel(self) -> None:
        """
        Releases model resources and frees memory.
        
        Called at application shutdown or when model is no longer needed.
        """
        logger.info(f"Unloading model '{self.modelName}'")
        self._model = None
        self.loaded = False

    def isLoaded(self) -> bool:
        """
        Checks whether model weights are loaded.
        
        Returns:
            True if model is ready for inference.
        """
        return self.loaded

    def preprocess(self, image: Image) -> Image:
        """
        Applies resizing, normalization, and format conversion
        to prepare input for model inference.
        
        Default implementation:
        - Normalizes the image (RGB conversion)
        - Resizes to model's expected input dimensions
        
        Subclasses should override for model-specific preprocessing
        (e.g., specific normalization, tensor conversion).
        
        Args:
            image: Raw input Image.
            
        Returns:
            Preprocessed Image ready for inference.
        """
        from PIL import Image as PILImage

        logger.debug(f"Preprocessing image {image.imageId} for model '{self.modelName}'")

        # Ensure image is normalized to RGB
        image.normalize()

        # Resize to model input dimensions if needed
        img = PILImage.open(io.BytesIO(image.rawData))
        if img.width != self.inputWidth or img.height != self.inputHeight:
            img = img.resize(
                (self.inputWidth, self.inputHeight),
                PILImage.Resampling.LANCZOS,
            )
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image.rawData = buffer.getvalue()
            image.width = self.inputWidth
            image.height = self.inputHeight
            image.size = len(image.rawData)

        return image

    def postprocess(self, rawOutput: bytes) -> ResultImage:
        """
        Converts raw model output to a ResultImage instance.
        
        Default implementation wraps raw bytes as PNG ResultImage.
        Subclasses should override for model-specific postprocessing
        (e.g., tensor-to-image conversion, mask overlay, color mapping).
        
        Args:
            rawOutput: Raw bytes from model inference output.
            
        Returns:
            ResultImage instance containing processed data.
        """
        import uuid

        logger.debug(f"Postprocessing output from model '{self.modelName}'")

        return ResultImage(
            resultId=str(uuid.uuid4()),
            processedData=rawOutput,
            format="png",
        )

    def _ensure_loaded(self) -> None:
        """Helper to verify model is loaded before inference."""
        if not self.loaded:
            logger.info(
                f"Lazy-loading model '{self.modelName}' on first use (device={self.device})"
            )
            self.loadModel()

        if not self.loaded:
            from app.utils.exceptions import ModelNotLoadedError
            raise ModelNotLoadedError(
                f"Model '{self.modelName}' is not loaded. Call loadModel() first."
            )
