"""
Structured Logging Utility — LLD §1.2.7
HLD Module: Logging and Monitoring

Provides structured logging that:
- Includes timestamps and operation ID tagging
- Classifies errors
- NEVER logs raw image data or personal identifiers
"""

import logging
import uuid
from app.config.settings import get_settings


def get_logger(name: str) -> logging.Logger:
    """
    Creates a logger instance with structured formatting.
    
    Args:
        name: Logger name (typically __name__ of the calling module).
    
    Returns:
        Configured logging.Logger instance.
    """
    settings = get_settings()
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(settings.LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    return logger


def generate_operation_id() -> str:
    """Generates a unique operation ID for request tracing."""
    return str(uuid.uuid4())[:12]
