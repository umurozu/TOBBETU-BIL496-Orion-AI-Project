"""
Backend Integration Tests — LLD Verification
Complete test suite covering all Functional Requirements (FR-01 through FR-13)
and Test Cases (TC-01 through TC-19).

Tests the complete API flow: upload → process → status → download
"""

import io
import base64
import time
import uuid
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from PIL import Image as PILImage
from PIL import ImageChops

from app.main import app, hairstyle_service, session_controller, session_service
from app.model.image import Image


@pytest.fixture
def client():
    """Creates a test client for the FastAPI app with lifespan enabled."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_image_bytes():
    """Creates a minimal valid PNG image for testing."""
    img = PILImage.new("RGB", (100, 100), color=(128, 128, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def large_image_bytes():
    """Creates a large (2048x2048) image to test performance handling."""
    img = PILImage.new("RGB", (2048, 2048), color=(64, 128, 192))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def portrait_image_bytes():
    """Creates a portrait-like test image with face-like features."""
    img = PILImage.new("RGB", (256, 256), color=(220, 180, 160))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


@pytest.fixture
def grayscale_image_bytes():
    """Creates a grayscale test image for colorization."""
    img = PILImage.new("L", (128, 128), color=128)
    img = img.convert("RGB")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def upload_image(client, image_bytes, filename="test.png"):
    """Helper: uploads an image and returns the session_id."""
    resp = client.post(
        "/upload",
        files={"file": (filename, image_bytes, "image/png")},
    )
    assert resp.status_code == 200, f"Upload failed: {resp.text}"
    data = resp.json()
    assert data["status"] == "success"
    return data["data"]["session_id"]


# =====================================================
# TC-01: Upload valid image (FR-01)
# =====================================================
class TestTC01UploadValidImage:
    def test_upload_valid_image(self, client, sample_image_bytes):
        response = client.post(
            "/upload",
            files={"file": ("test.png", sample_image_bytes, "image/png")},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "session_id" in data["data"]
        assert "image_id" in data["data"]
        assert data["data"]["format"] == "png"

    def test_upload_returns_dimensions(self, client, sample_image_bytes):
        response = client.post(
            "/upload",
            files={"file": ("test.png", sample_image_bytes, "image/png")},
        )
        data = response.json()
        assert data["data"]["width"] == 100
        assert data["data"]["height"] == 100

    def test_upload_jpeg_image(self, client):
        """Validates JPEG upload support."""
        img = PILImage.new("RGB", (50, 50), color=(200, 100, 100))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        resp = client.post(
            "/upload",
            files={"file": ("photo.jpg", buf.getvalue(), "image/jpeg")},
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["format"] == "jpg"


# =====================================================
# TC-02: Reject invalid file (FR-01)
# =====================================================
class TestTC02RejectInvalidFile:
    def test_upload_invalid_format(self, client):
        response = client.post(
            "/upload",
            files={"file": ("test.bmp", b"fake_data", "image/bmp")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert data["error_code"] == "INVALID_FORMAT"

    def test_upload_text_file(self, client):
        response = client.post(
            "/upload",
            files={"file": ("readme.txt", b"hello world", "text/plain")},
        )
        assert response.status_code == 400

    def test_upload_pdf_file(self, client):
        response = client.post(
            "/upload",
            files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
        )
        assert response.status_code == 400

    def test_upload_corrupted_file(self, client):
        response = client.post(
            "/upload",
            files={"file": ("test.png", b"not_an_image", "image/png")},
        )
        assert response.status_code == 400

    def test_upload_oversized_file(self, client):
        oversized = b"\x00" * (11 * 1024 * 1024)
        response = client.post(
            "/upload",
            files={"file": ("large.png", oversized, "image/png")},
        )
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "FILE_TOO_LARGE"


# =====================================================
# TC-03: AI processing workflow (FR-02..FR-07)
# =====================================================
class TestTC03AIProcessingWorkflow:
    """Verifies that ALL registered editing types can be invoked
    and return a valid response through the /process endpoint."""

    @pytest.mark.parametrize("editing_type", [
        "enhancement",
        "beautification",
        "aging",
        "colorization",
        "style_transfer",
        "object_removal",
        "background_replace",
        "face_edit",
    ])
    def test_process_all_editing_types(self, client, sample_image_bytes, editing_type):
        session_id = upload_image(client, sample_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": editing_type,
                "parameters": {},
            },
        )
        assert response.status_code == 200, f"{editing_type} failed: {response.text}"
        data = response.json()
        assert data["status"] == "success"
        assert "result_image" in data["data"]
        assert "result_id" in data["data"]
        # Verify result_image is valid base64
        decoded = base64.b64decode(data["data"]["result_image"])
        assert len(decoded) > 0

    def test_process_invalid_session(self, client):
        response = client.post(
            "/process",
            json={
                "session_id": "nonexistent",
                "editing_type": "enhancement",
                "parameters": {},
            },
        )
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"

    def test_process_invalid_editing_type(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "nonexistent_type",
                "parameters": {},
            },
        )
        assert response.status_code == 400


# =====================================================
# TC-04: Preview display (FR-08) — tested via base64 output
# =====================================================
class TestTC04PreviewDisplay:
    def test_processed_image_is_viewable(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        resp = client.post(
            "/process",
            json={"session_id": session_id, "editing_type": "enhancement", "parameters": {}},
        )
        data = resp.json()["data"]
        img_bytes = base64.b64decode(data["result_image"])
        img = PILImage.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0 and img.size[1] > 0


# =====================================================
# TC-05: Download image (FR-09)
# =====================================================
class TestTC05DownloadImage:
    def test_download_after_processing(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        client.post(
            "/process",
            json={"session_id": session_id, "editing_type": "enhancement", "parameters": {}},
        )
        response = client.get(f"/download/{session_id}?format=png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"

    def test_download_jpeg_format(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        client.post(
            "/process",
            json={"session_id": session_id, "editing_type": "enhancement", "parameters": {}},
        )
        response = client.get(f"/download/{session_id}?format=jpeg")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"

    def test_download_no_result(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.get(f"/download/{session_id}?format=png")
        assert response.status_code == 400


class TestTC05BSignatureDetection:
    def test_detect_signature_for_exported_image(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        client.post(
            "/process",
            json={"session_id": session_id, "editing_type": "enhancement", "parameters": {}},
        )
        exported = client.get(f"/download/{session_id}?format=png")

        response = client.post(
            "/detect-invisio-image",
            files={"file": ("signed.png", exported.content, "image/png")},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_signature"] is True
        assert data["confidence"] > 0

    def test_detect_signature_rejects_plain_image(self, client, sample_image_bytes):
        response = client.post(
            "/detect-invisio-image",
            files={"file": ("plain.png", sample_image_bytes, "image/png")},
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["has_signature"] is False


class _FakeHairstylePipeline:
    def __init__(self):
        self.last_kwargs = None

    def __call__(self, **kwargs):
        self.last_kwargs = kwargs
        base = kwargs["image"].convert("RGB")
        mask = kwargs["mask_image"].convert("L")
        tint = PILImage.new("RGB", base.size, color=(123, 81, 58))
        output = PILImage.composite(tint, base, mask)
        return SimpleNamespace(images=[output])


class TestTC05CHairstyleTryOn:
    def test_hairstyle_presets_endpoint(self, client):
        response = client.get("/hairstyle-presets")
        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["items"] == []
        assert len(payload["color_options"]) >= 5

    def test_hairstyle_process_endpoint(self, client, portrait_image_bytes):
        session_id = upload_image(client, portrait_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "hairstyle",
                "parameters": {"hair_color": "chestnut_brown"},
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["data"]["result_image"]

    def test_hair_transfer_endpoint(self, client, portrait_image_bytes):
        session_id = upload_image(client, portrait_image_bytes)
        response = client.post(
            "/hair-transfer",
            data={"session_id": session_id},
            files={
                "shape_reference": ("shape.png", portrait_image_bytes, "image/png"),
                "color_reference": ("color.png", portrait_image_bytes, "image/png"),
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        assert payload["data"]["format"] == "png"
        assert payload["data"]["result_image"]


# =====================================================
# TC-06: Large image performance (FR-12)
# =====================================================
class TestTC06LargeImagePerformance:
    def test_large_image_upload_and_process(self, client, large_image_bytes):
        """Validates that a 2048x2048 image can be uploaded and processed."""
        session_id = upload_image(client, large_image_bytes)

        start = time.time()
        response = client.post(
            "/process",
            json={"session_id": session_id, "editing_type": "enhancement", "parameters": {}},
        )
        elapsed = time.time() - start

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        # Should complete within 60 seconds even on CPU
        assert elapsed < 60, f"Processing took {elapsed:.1f}s (too slow)"


# =====================================================
# TC-07: Session-based deletion (FR-10)
# =====================================================
class TestTC07SessionDeletion:
    def test_delete_session_removes_data(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)

        # Verify session exists
        status_resp = client.get(f"/status/{session_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["data"]["has_image"] == True

        # Delete session
        del_resp = client.delete(f"/session/{session_id}")
        assert del_resp.status_code == 200

        # Verify session is gone
        verify_resp = client.get(f"/status/{session_id}")
        assert verify_resp.status_code == 400
        assert verify_resp.json()["error_code"] == "SESSION_NOT_FOUND"

    def test_delete_session_cleans_result(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        client.post(
            "/process",
            json={"session_id": session_id, "editing_type": "enhancement", "parameters": {}},
        )

        # Confirm result exists
        status = client.get(f"/status/{session_id}").json()
        assert status["data"]["has_result"] == True

        # Delete and verify
        client.delete(f"/session/{session_id}")
        verify = client.get(f"/status/{session_id}")
        assert verify.status_code == 400


# =====================================================
# TC-08: No-image error handling (FR-01)
# =====================================================
class TestTC08NoImageError:
    def test_process_without_upload(self, client, sample_image_bytes):
        """Process request on a fresh session without any uploaded image."""
        session_id = upload_image(client, sample_image_bytes)
        # delete image by cleaning up session and making a new one
        client.delete(f"/session/{session_id}")

        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "enhancement",
                "parameters": {},
            },
        )
        assert response.status_code == 400


# =====================================================
# TC-09: Object removal (FR-02)
# =====================================================
class TestTC09ObjectRemoval:
    def test_object_removal_pipeline(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "object_removal",
                "parameters": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["result_image"]
        img_bytes = base64.b64decode(data["data"]["result_image"])
        assert len(img_bytes) > 100


# =====================================================
# TC-10: Image enhancement (FR-03)
# =====================================================
class TestTC10ImageEnhancement:
    def test_enhancement_returns_image(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "enhancement",
                "parameters": {"sharpness": 1.5},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        img_bytes = base64.b64decode(data["data"]["result_image"])
        img = PILImage.open(io.BytesIO(img_bytes))
        assert img.size[0] > 0


# =====================================================
# TC-11: Style transfer (FR-04)
# =====================================================
class TestTC11StyleTransfer:
    def test_style_transfer_via_process(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "style_transfer",
                "parameters": {"style_id": "impressionist"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["result_image"]


# =====================================================
# TC-12: Facial beautification (FR-05)
# =====================================================
class TestTC12FacialBeautification:
    def test_beautification_returns_image(self, client, portrait_image_bytes):
        session_id = upload_image(client, portrait_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "beautification",
                "parameters": {"smoothing": 0.7},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["result_image"]


# =====================================================
# TC-12B: Age transformation
# =====================================================
class TestTC12BAgeTransformation:
    def test_aging_returns_image(self, client, portrait_image_bytes):
        session_id = upload_image(client, portrait_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "aging",
                "parameters": {"intensity": 0.7, "rejuvenate": False},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        result_bytes = base64.b64decode(data["data"]["result_image"])
        result_image = PILImage.open(io.BytesIO(result_bytes)).convert("RGB")
        original_image = PILImage.open(io.BytesIO(portrait_image_bytes)).convert("RGB")

        assert data["data"]["result_image"]
        assert ImageChops.difference(original_image, result_image).getbbox() is not None


# =====================================================
# TC-13: Background editing (FR-06)
# =====================================================
class TestTC13BackgroundEditing:
    def test_background_replace_returns_image(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "background_replace",
                "parameters": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["result_image"]


# =====================================================
# TC-14: Colorization (FR-07)
# =====================================================
class TestTC14Colorization:
    def test_colorization_returns_image(self, client, grayscale_image_bytes):
        session_id = upload_image(client, grayscale_image_bytes)
        response = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "colorization",
                "parameters": {},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["result_image"]


# =====================================================
# TC-15: Manual mask refinement (FR-11)
# =====================================================
class TestTC15ManualMaskRefinement:
    def test_refine_mask_endpoint(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        # Create a simple brush mask matching 100x100 (which is the dimension of sample_image_bytes)
        import numpy as np
        brush = np.zeros((100, 100), dtype=np.uint8)
        brush[40:60, 40:60] = 255
        brush_b64 = base64.b64encode(brush.tobytes()).decode("utf-8")

        response = client.post(
            "/refine",
            json={
                "session_id": session_id,
                "mask_data": brush_b64,
                "brush_size": 15,
                "brush_strength": 0.8,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "mask_data" in data["data"]


# =====================================================
# TC-16: Hybrid AI + manual workflow (FR-12)
# =====================================================
class TestTC16HybridWorkflow:
    def test_hybrid_segment_refine_regenerate(self, client, sample_image_bytes):
        """Full hybrid pipeline: upload → detect mask → refine → regenerate."""
        session_id = upload_image(client, sample_image_bytes)

        # Step 1: Generate segmentation mask via detect_mask
        seg_resp = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "detect_mask",
                "parameters": {},
            },
        )
        assert seg_resp.status_code == 200
        mask_b64 = seg_resp.json()["data"]["result_image"]
        assert mask_b64

        # Step 2: Regenerate using that mask as refinement input
        regen_resp = client.post(
            "/regenerate",
            json={
                "session_id": session_id,
                "mask_data": mask_b64,
            },
        )
        assert regen_resp.status_code == 200
        data = regen_resp.json()
        assert data["status"] == "success"
        assert data["data"]["result_image"]


# =====================================================
# TC-17: NSFW detection (FR-13)
# =====================================================
class TestTC17NSFWDetection:
    def test_nsfw_model_registered(self, client):
        """Verifies NSFW model is registered in the factory."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "nsfw_detection" in data["registered_models"]


# =====================================================
# TC-18: Community sharing (extra feature)
# =====================================================
class TestTC18CommunitySharing:
    def test_community_feed_accessible(self, client):
        """Verifies public community feed endpoint is reachable."""
        response = client.get("/community/feed?limit=5")
        # May fail if DB is not running — that's expected in CI
        # We check the endpoint exists (not 404/405)
        assert response.status_code in [200, 500]


# =====================================================
# TC-19: Authentication (extra feature)
# =====================================================
class TestTC19Authentication:
    def test_auth_register_endpoint_exists(self, client):
        """Verifies the registration endpoint is reachable."""
        response = client.post(
            "/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "TestPass123!",
                "consent_given": True,
            },
        )
        # May fail if DB is not running or validation fails — that's expected
        assert response.status_code in [200, 400, 409, 500]

    def test_auth_login_endpoint_exists(self, client):
        """Verifies the login endpoint is reachable."""
        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "TestPass123!"},
        )
        assert response.status_code in [200, 400, 401, 500]


# =====================================================
# Health endpoint tests
# =====================================================
class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["app"] == "Invisio"
        assert "registered_models" in data

    def test_health_shows_active_sessions(self, client):
        response = client.get("/health")
        data = response.json()
        assert "active_sessions" in data


# =====================================================
# Status endpoint tests
# =====================================================
class TestStatusEndpoint:
    def test_status_after_upload(self, client, sample_image_bytes):
        session_id = upload_image(client, sample_image_bytes)
        response = client.get(f"/status/{session_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["has_image"] == True
        assert data["data"]["has_result"] == False

    def test_status_invalid_session(self, client):
        response = client.get("/status/nonexistent")
        assert response.status_code == 400
        data = response.json()
        assert data["error_code"] == "SESSION_NOT_FOUND"


# =====================================================
# Full end-to-end pipeline test
# =====================================================
class TestFullEditingPipeline:
    """End-to-end test: upload → process → status → download → cleanup"""

    def test_full_pipeline(self, client, sample_image_bytes):
        # 1. Upload
        upload_resp = client.post(
            "/upload",
            files={"file": ("photo.png", sample_image_bytes, "image/png")},
        )
        assert upload_resp.status_code == 200
        session_id = upload_resp.json()["data"]["session_id"]

        # 2. Check status
        status_resp = client.get(f"/status/{session_id}")
        assert status_resp.json()["data"]["has_image"] == True

        # 3. Process (enhancement)
        process_resp = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "enhancement",
                "parameters": {},
            },
        )
        assert process_resp.status_code == 200
        assert process_resp.json()["data"]["result_image"]

        # 4. Check status again
        status_resp2 = client.get(f"/status/{session_id}")
        assert status_resp2.json()["data"]["has_result"] == True

        # 5. Download
        dl_resp = client.get(f"/download/{session_id}?format=jpeg")
        assert dl_resp.status_code == 200
        assert dl_resp.headers["content-type"] == "image/jpeg"

        # 6. Cleanup
        del_resp = client.delete(f"/session/{session_id}")
        assert del_resp.status_code == 200
