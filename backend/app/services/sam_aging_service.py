"""
DEPRECATED: Heavy SAM Aging Service.
Removed to save VRAM on 4GB systems.
"""

class InvisioSamAgingService:
    def __init__(self):
        pass

    def isConfigured(self) -> bool:
        return False

    def warmup(self) -> None:
        pass

    def release(self) -> None:
        pass

    def age(self, image_bytes: bytes, target_age: int) -> bytes:
        raise RuntimeError("Heavy SAM Aging Service has been removed to save VRAM.")
