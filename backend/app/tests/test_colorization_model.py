import io
import sys

import pytest
from PIL import Image as PILImage

from app.ai.colorization import ColorizationModel
from app.controller.editing_controller import EditingController
from app.controller.security_controller import SecurityController
from app.controller.session_controller import SessionController
from app.model.editing_request import EditingRequest, EditingType
from app.model.image import Image
from app.services.eccv_colorization_service import OptivimoEccvColorizationService
from app.services.session_service import SessionService
from app.utils.exceptions import ProcessingError


def _png_bytes(color=(128, 128, 128)) -> bytes:
    img = PILImage.new("RGB", (32, 32), color=color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class _UnavailableColorizationService:
    def isConfigured(self) -> bool:
        return False

    def warmup(self) -> None:
        raise AssertionError("warmup should not run when assets are unavailable")

    def release(self) -> None:
        return None


class _FailingColorizationService:
    def isConfigured(self) -> bool:
        return True

    def warmup(self) -> None:
        return None

    def colorize(self, image_bytes: bytes) -> bytes:
        raise RuntimeError("synthetic failure")

    def release(self) -> None:
        return None


class _FailingModel:
    def process(self, image: Image, request: EditingRequest):
        raise ProcessingError(
            "Colorization failed while processing the image.",
            error_code="COLORIZATION_FAILED",
        )


class _Factory:
    def createModel(self, editing_type: EditingType):
        return _FailingModel()


def test_colorization_model_raises_when_assets_are_missing():
    model = ColorizationModel()
    model._service = _UnavailableColorizationService()

    image = Image(
        imageId="img-1",
        rawData=_png_bytes(),
        format="png",
        size=0,
        width=32,
        height=32,
    )
    request = EditingRequest(
        requestId="req-1",
        editingType=EditingType.COLORIZATION,
    )

    with pytest.raises(ProcessingError) as exc_info:
        model.process(image, request)

    assert exc_info.value.error_code == "COLORIZATION_UNAVAILABLE"


def test_colorization_model_raises_when_inference_fails():
    model = ColorizationModel()
    model._service = _FailingColorizationService()

    image = Image(
        imageId="img-2",
        rawData=_png_bytes(),
        format="png",
        size=0,
        width=32,
        height=32,
    )
    request = EditingRequest(
        requestId="req-2",
        editingType=EditingType.COLORIZATION,
    )

    with pytest.raises(ProcessingError) as exc_info:
        model.process(image, request)

    assert exc_info.value.error_code == "COLORIZATION_FAILED"


def test_editing_controller_preserves_model_processing_error():
    session_service = SessionService()
    security_controller = SecurityController()
    session_controller = SessionController(session_service, security_controller)
    editing_controller = EditingController(
        model_factory=_Factory(),
        session_service=session_service,
        session_controller=session_controller,
        security_controller=security_controller,
    )

    session_id = session_service.createSession()
    image_bytes = _png_bytes()
    session_service.storeImage(
        session_id,
        Image(
            imageId="img-3",
            rawData=image_bytes,
            format="png",
            size=len(image_bytes),
            width=32,
            height=32,
        ),
    )

    with pytest.raises(ProcessingError) as exc_info:
        editing_controller.applyEditing(session_id, "colorization", {})

    assert exc_info.value.error_code == "COLORIZATION_FAILED"
    assert session_service.getSessionData(session_id).processing_status == "error"


def test_colorization_service_imports_from_configured_vendor_parent(tmp_path):
    service = OptivimoEccvColorizationService()
    service._vendor_dir = tmp_path / "external_vendor" / "optivimo_colorizers"
    service._vendor_dir.mkdir(parents=True)
    vendor_parent = str(service._vendor_dir.parent)

    while vendor_parent in sys.path:
        sys.path.remove(vendor_parent)

    try:
        service._ensure_vendor_imports()
        assert vendor_parent in sys.path
    finally:
        while vendor_parent in sys.path:
            sys.path.remove(vendor_parent)
