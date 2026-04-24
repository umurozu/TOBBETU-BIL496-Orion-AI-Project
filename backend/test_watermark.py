import sys
import os
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(os.getcwd()) / "app"))
sys.path.append(os.getcwd())

from app.services.watermark_service import WatermarkService

service = WatermarkService()
path = service.resolveWatermarkAssetPath()
print(f"Resolved path: {path}")

if path and path.exists():
    print("SUCCESS: Watermark found!")
else:
    print("FAILURE: Watermark not found!")
