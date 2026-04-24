import io

from PIL import Image as PILImage
from PIL import ImageChops

from app.model.result_image import ExportFormat, ResultImage
from app.services.export_service import ExportService
from app.services.signature_service import SignatureService


def test_export_service_applies_watermark():
    image = PILImage.new("RGBA", (320, 200), color=(210, 180, 160, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = ResultImage(resultId="test-result", processedData=buffer.getvalue(), format="png")
    exported = ExportService().exportResult(result, ExportFormat.PNG)

    original = PILImage.open(io.BytesIO(buffer.getvalue())).convert("RGB")
    watermarked = PILImage.open(io.BytesIO(exported)).convert("RGB")
    diff = ImageChops.difference(original, watermarked)

    assert diff.getbbox() is not None


def test_export_service_preserves_png_dimensions():
    image = PILImage.new("RGBA", (256, 128), color=(60, 90, 120, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = ResultImage(resultId="png-result", processedData=buffer.getvalue(), format="png")
    exported = ExportService().exportResult(result, ExportFormat.PNG)
    exported_image = PILImage.open(io.BytesIO(exported))

    assert exported_image.size == (256, 128)


def test_export_service_embeds_detectable_signature():
    image = PILImage.new("RGBA", (420, 280), color=(90, 140, 190, 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    result = ResultImage(resultId="signed-result", processedData=buffer.getvalue(), format="png")
    exported = ExportService().exportResult(result, ExportFormat.PNG)
    detection = SignatureService().detectSignature(exported)

    assert detection["has_signature"] is True
    assert detection["matched_bits"] > 0
