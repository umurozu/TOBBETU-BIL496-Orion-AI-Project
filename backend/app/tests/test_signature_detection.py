import io

from fastapi.testclient import TestClient
from PIL import Image as PILImage

from app.main import app


def test_detect_invisio_image_on_exported_download():
    with TestClient(app) as client:
        image = PILImage.new("RGB", (220, 180), color=(180, 150, 130))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        upload = client.post("/upload", files={"file": ("portrait.png", buffer.getvalue(), "image/png")})
        session_id = upload.json()["data"]["session_id"]

        process = client.post(
            "/process",
            json={
                "session_id": session_id,
                "editing_type": "enhancement",
                "parameters": {"upscale": 1},
            },
        )
        assert process.status_code == 200

        downloaded = client.get(f"/download/{session_id}?format=png")
        assert downloaded.status_code == 200

        detect = client.post(
            "/detect-invisio-image",
            files={"file": ("downloaded.png", downloaded.content, "image/png")},
        )
        assert detect.status_code == 200
        assert detect.json()["data"]["has_signature"] is True


def test_detect_invisio_image_on_plain_upload():
    with TestClient(app) as client:
        image = PILImage.new("RGB", (220, 180), color=(80, 120, 160))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")

        detect = client.post(
            "/detect-invisio-image",
            files={"file": ("plain.png", buffer.getvalue(), "image/png")},
        )
        assert detect.status_code == 200
        assert detect.json()["data"]["has_signature"] is False
