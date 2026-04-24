import sys
import os
import numpy as np
import cv2
from PIL import Image as PILImage
import io

# Mocking app structures
class MockImage:
    def __init__(self, raw_data):
        self.rawData = raw_data

class MockRequest:
    def __init__(self, parameters):
        self.parameters = parameters

# Import the model
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from app.ai.face_editing import FaceEditingModel

def test_contrast_matching():
    model = FaceEditingModel()
    
    # Create two different images
    img1 = np.full((100, 100, 3), [200, 100, 50], dtype=np.uint8) # Brighter/Redder
    img2 = np.full((100, 100, 3), [50, 50, 50], dtype=np.uint8)   # Darker/Grayer
    
    matched = model._match_contrast(img1, img2)
    
    print(f"Original Mean: {img1.mean(axis=(0,1))}")
    print(f"Target Mean: {img2.mean(axis=(0,1))}")
    print(f"Matched Mean: {matched.mean(axis=(0,1))}")
    
    # Matched mean should be very close to target mean
    diff = np.abs(matched.mean(axis=(0,1)) - img2.mean(axis=(0,1)))
    assert np.all(diff < 5), f"Contrast matching failed. Diff: {diff}"
    print("Contrast matching test passed!")

if __name__ == "__main__":
    test_contrast_matching()
