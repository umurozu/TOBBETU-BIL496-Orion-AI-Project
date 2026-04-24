"""
Application Configuration — LLD §1.2, §1.3
HLD Module: Core Configuration

Config-driven parameters for Invisio backend.
No hard-coded constants; all values are configurable via environment variables.
"""

from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """
    Centralized application settings.
    
    Corresponds to:
        - LLD §1.2.3 (Data Format Specifications)
        - LLD §1.2.5 (Security Interface Constraints)
        - LLD §1.3.4 (Coding Standards — externalized config)
    """

    # --- Application ---
    APP_NAME: str = "Invisio"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # --- Server ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    # --- Image Constraints (LLD §1.2.3) ---
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10 MB
    ALLOWED_FORMATS: List[str] = ["jpeg", "jpg", "png"]
    MAX_IMAGE_WIDTH: int = 4096
    MAX_IMAGE_HEIGHT: int = 4096

    # --- Session (LLD §1.1.5, §1.2.3) ---
    SESSION_TIMEOUT_SECONDS: int = 1800  # 30 minutes
    SESSION_CLEANUP_INTERVAL_SECONDS: int = 300  # 5 minutes

    # --- Security (LLD §1.2.5) ---
    RATE_LIMIT_REQUESTS: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # --- AI Processing (LLD §1.1.2, §1.1.6) ---
    DEVICE: str = "cuda"  # "cpu" or "cuda"
    REMOTE_INFERENCE_URL: str = ""
    REMOTE_INFERENCE_API_KEY: str = ""
    REMOTE_INFERENCE_SAM_TIMEOUT_SECONDS: float = 60.0
    REMOTE_INFERENCE_HAIRFASTGAN_TIMEOUT_SECONDS: float = 300.0
    MODEL_INPUT_WIDTH: int = 512
    MODEL_INPUT_HEIGHT: int = 512
    NSFW_DETECTION_THRESHOLD: float = 0.5
    NSFW_AUTO_BLOCK: bool = True
    # Path to the root directory containing AI model submodules (u2net-demo, lama)
    MODELS_BASE_DIR: str = ""  # Resolved relative to project root at runtime if empty
    # Optional: explicit python executable for LaMa subprocess (object removal / inpainting)
    LAMA_PYTHON_BIN: str = ""
    SUPER_RES_MODEL_NAME: str = "edsr"
    SUPER_RES_MODEL_PATH: str = "checkpoints/superres/EDSR_x4.pb"
    SUPER_RES_MAX_SCALE: int = 4
    SUPER_RES_MAX_OUTPUT_EDGE: int = 6144
    HAIRSTYLE_MODEL_ID: str = "runwayml/stable-diffusion-inpainting"
    HAIRSTYLE_MODEL_PATH: str = ""
    HAIRSTYLE_CACHE_DIR: str = "checkpoints/hairstyle/cache"
    HAIRSTYLE_DEVICE: str = "cuda"
    HAIRSTYLE_STEPS: int = 20
    HAIRSTYLE_GUIDANCE_SCALE: float = 7.5
    HAIRSTYLE_STRENGTH: float = 0.92
    HAIRSTYLE_MAX_EDGE: int = 512
    HAIRSTYLE_NEGATIVE_PROMPT: str = (
        "low quality, blurry, extra face, distorted face, duplicate hair, bad anatomy, "
        "cartoon, painting, deformed eyes, broken background, warped ears"
    )
    HAIR_TRANSFER_MAX_EDGE: int = 1024
    HAIR_TRANSFER_BLEND_STRENGTH: float = 0.84
    HAIR_TRANSFER_COLOR_STRENGTH: float = 0.78
    HAIR_TRANSFER_SHARPEN_AMOUNT: float = 0.9
    AGING_SAM_VENDOR_DIR: str = "vendor/SAM"
    AGING_SAM_CHECKPOINT_PATH: str = "checkpoints/aging/sam_ffhq_aging.pt"
    AGING_SAM_DEVICE: str = "cuda"
    COLORIZATION_VENDOR_DIR: str = "vendor/invisio_colorizers"
    COLORIZATION_CLUSTER_POINTS_PATH: str = "checkpoints/colorization/cluster_points.npy"
    COLORIZATION_WEIGHTS_PATH: str = "checkpoints/colorization/colorization_release_v2-9b330a0b.pth"
    COLORIZATION_DEVICE: str = "cuda"
    COLORIZATION_INPUT_SIZE: int = 256

    # --- Community Feature ---
    COMMUNITY_STORAGE_DIR: str = "data/community_images"  # Relative to backend working directory

    # --- Export / Watermark ---
    EXPORT_WATERMARK_ENABLED: bool = True
    EXPORT_WATERMARK_TEXT: str = "Invisio"
    EXPORT_WATERMARK_IMAGE_PATH: str = ""
    EXPORT_WATERMARK_POSITION: str = "bottom_right"
    EXPORT_WATERMARK_OPACITY: float = 0.1
    EXPORT_WATERMARK_MARGIN: int = 24
    EXPORT_WATERMARK_SCALE: float = 0.18
    EXPORT_SIGNATURE_ENABLED: bool = True
    EXPORT_SIGNATURE_STRENGTH: float = 0.028
    EXPORT_SIGNATURE_THRESHOLD: float = 0.72

    # --- Database (PostgreSQL via Docker) ---
    DATABASE_URL: str = "postgresql+asyncpg://admin:admin123@localhost:5432/appdb"
    DB_ECHO: bool = False  # SQLAlchemy SQL echo (debug only)
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40

    # --- Authentication (JWT) ---
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Logging (LLD §1.2.7) ---
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parseDebugFlag(cls, value):
        if isinstance(value, bool):
            return value

        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug", "development"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "production", "prod"}:
            return False
        return value

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Returns cached Settings instance. Thread-safe singleton."""
    return Settings()
