import io

import numpy as np
import pytest
from PIL import Image as PILImage

from app.config.settings import get_settings
from app.services.hairstyle_service import HairstyleTryOnService
from app.services.mobile_sam_service import MobileSamService


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _mask_png_bytes(size=(10, 10), value=255) -> bytes:
    mask = PILImage.new("L", size, color=value)
    buf = io.BytesIO()
    mask.save(buf, format="PNG")
    return buf.getvalue()


def _rgb_png_bytes(size=(32, 32), color=(12, 34, 56)) -> bytes:
    image = PILImage.new("RGB", size, color=color)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_mobile_sam_service_uses_remote_when_configured(monkeypatch):
    monkeypatch.setenv("REMOTE_INFERENCE_URL", "http://remote.example")
    monkeypatch.setenv("REMOTE_INFERENCE_API_KEY", "secret")

    expected_mask_bytes = _mask_png_bytes((10, 10), 255)
    captured: dict[str, object] = {}

    import httpx

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data=None, files=None, headers=None):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            captured["headers"] = headers
            return _FakeResponse(expected_mask_bytes)

    monkeypatch.setattr(httpx, "Client", _Client)

    service = MobileSamService()
    image_rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    face_landmarks = np.zeros((468, 2), dtype=np.float32)

    result = service.predict_hair_mask(image_rgb, face_landmarks)

    assert captured["url"] == "http://remote.example/v1/sam/predict"
    assert captured["headers"] == {"X-API-Key": "secret"}
    assert "point_coords" in captured["data"]
    assert "point_labels" in captured["data"]
    assert captured["data"]["multimask_output"] == "true"
    assert "image" in captured["files"]
    assert result.shape == (10, 10)
    assert int(result.max()) == 255


def test_mobile_sam_service_uses_remote_from_face_box(monkeypatch):
    monkeypatch.setenv("REMOTE_INFERENCE_URL", "http://remote.example")
    monkeypatch.setenv("REMOTE_INFERENCE_API_KEY", "secret")

    expected_mask_bytes = _mask_png_bytes((10, 10), 255)
    captured: dict[str, object] = {}

    import httpx

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data=None, files=None, headers=None):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            captured["headers"] = headers
            return _FakeResponse(expected_mask_bytes)

    monkeypatch.setattr(httpx, "Client", _Client)

    service = MobileSamService()
    image_rgb = np.zeros((10, 10, 3), dtype=np.uint8)

    result = service.predict_hair_mask_from_face_box(image_rgb, face_box=(2, 2, 8, 8))

    assert captured["url"] == "http://remote.example/v1/sam/predict"
    assert captured["headers"] == {"X-API-Key": "secret"}
    assert "point_coords" in captured["data"]
    assert "point_labels" in captured["data"]
    assert "image" in captured["files"]
    assert result.shape == (10, 10)
    assert int(result.max()) == 255


def test_mobile_sam_service_falls_back_to_local_on_remote_error(monkeypatch):
    monkeypatch.setenv("REMOTE_INFERENCE_URL", "http://remote.example")

    import httpx

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise RuntimeError("network down")

    monkeypatch.setattr(httpx, "Client", _Client)

    class _Predictor:
        def __init__(self):
            self.image = None

        def set_image(self, image):
            self.image = image

        def predict(self, point_coords, point_labels, multimask_output=True):
            height, width = self.image.shape[:2]
            masks = np.ones((1, height, width), dtype=np.uint8)
            scores = np.array([0.9], dtype=np.float32)
            return masks, scores, None

    service = MobileSamService()
    service._loaded = True
    service._predictor = _Predictor()

    image_rgb = np.zeros((10, 10, 3), dtype=np.uint8)
    face_landmarks = np.zeros((468, 2), dtype=np.float32)

    result = service.predict_hair_mask(image_rgb, face_landmarks)
    assert result.shape == (10, 10)
    assert int(result.max()) == 255


def test_hairstyle_service_hair_transfer_uses_remote_when_configured(monkeypatch):
    monkeypatch.setenv("REMOTE_INFERENCE_URL", "http://remote.example")
    monkeypatch.setenv("REMOTE_INFERENCE_API_KEY", "secret")

    expected_result = b"fake-png-bytes"
    captured: dict[str, object] = {}

    import httpx

    class _Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, data=None, files=None, headers=None):
            captured["url"] = url
            captured["data"] = data
            captured["files"] = files
            captured["headers"] = headers
            return _FakeResponse(expected_result)

    monkeypatch.setattr(httpx, "Client", _Client)

    service = HairstyleTryOnService()
    source = _rgb_png_bytes((64, 64), (10, 10, 10))
    shape_ref = _rgb_png_bytes((64, 64), (20, 20, 20))
    color_ref = _rgb_png_bytes((64, 64), (30, 30, 30))

    result = service.generateHairTransfer(
        source_image_bytes=source,
        shape_reference_bytes=shape_ref,
        color_reference_bytes=color_ref,
    )

    assert result == expected_result
    assert captured["url"] == "http://remote.example/v1/hairfastgan/swap"
    assert captured["headers"] == {"X-API-Key": "secret"}
    assert captured["data"] == {"align": "true"}
    assert set(captured["files"].keys()) == {"face_image", "shape_image", "color_image"}
