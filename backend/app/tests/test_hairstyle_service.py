import base64
import io

import numpy as np
from PIL import Image as PILImage, ImageChops, ImageDraw

from app.services.hairstyle_service import HairstyleTryOnService, PreparedHairImage


def _portrait_bytes(hair=(48, 28, 18), skin=(220, 187, 160), shirt=(40, 55, 80)):
    image = PILImage.new("RGB", (512, 512), color=(206, 220, 232))
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 350, 512, 512), fill=(168, 186, 203))
    draw.ellipse((150, 70, 362, 290), fill=hair)
    draw.ellipse((176, 126, 336, 318), fill=skin)
    draw.rectangle((205, 280, 306, 356), fill=skin)
    draw.rounded_rectangle((138, 318, 374, 500), radius=48, fill=shirt)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _mask_b64(box, size=(512, 512)):
    mask = PILImage.new("L", size, color=0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(box, radius=12, fill=255)
    buffer = io.BytesIO()
    mask.save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("utf-8")


def test_preset_catalog_is_available():
    service = HairstyleTryOnService()
    presets = service.listPresets()
    colors = service.listColorOptions()

    assert presets == []
    assert len(colors) >= 5


def test_generate_hair_recolor_image():
    service = HairstyleTryOnService()
    source = _portrait_bytes()

    result = service.generateHairstyle(source, "", "chestnut_brown")

    generated = PILImage.open(io.BytesIO(result)).convert("RGB")
    original = PILImage.open(io.BytesIO(source)).convert("RGB")
    difference = ImageChops.difference(original, generated)
    bbox = difference.getbbox()

    assert generated.size == (512, 512)
    assert bbox is not None
    assert bbox[3] < 390
    assert generated.getpixel((20, 20)) == original.getpixel((20, 20))


def test_hair_transfer_generates_image():
    service = HairstyleTryOnService()

    source = _portrait_bytes(hair=(36, 23, 16), skin=(223, 190, 165), shirt=(42, 64, 108))
    shape_ref = _portrait_bytes(hair=(88, 52, 24), skin=(230, 195, 171), shirt=(74, 64, 72))
    color_ref = _portrait_bytes(hair=(178, 126, 58), skin=(218, 184, 159), shirt=(34, 48, 60))

    result = service.generateHairTransfer(
        source_image_bytes=source,
        shape_reference_bytes=shape_ref,
        color_reference_bytes=color_ref,
    )

    generated = PILImage.open(io.BytesIO(result)).convert("RGB")

    assert generated.size == (512, 512)
    assert generated.tobytes() != PILImage.open(io.BytesIO(source)).convert("RGB").tobytes()


def test_manual_brush_mask_expands_across_hair_region():
    service = HairstyleTryOnService()
    source_bytes = _portrait_bytes()
    source_rgb = np.array(PILImage.open(io.BytesIO(source_bytes)).convert("RGB"), dtype=np.uint8)
    empty_hair_mask = np.zeros((512, 512), dtype=np.uint8)
    prepared = PreparedHairImage(
        rgb=source_rgb,
        analysis=None,
        face_box=(176, 126, 336, 318),
        hair_mask=empty_hair_mask,
    )

    service._get_subject_mask = lambda **kwargs: np.full((512, 512), 255, dtype=np.uint8)
    user_mask_b64 = _mask_b64((178, 98, 220, 168))

    expanded_mask = service._build_source_recolor_mask(
        prepared,
        source_bytes,
        user_mask_b64=user_mask_b64,
        brush_size=30,
    )

    assert expanded_mask[130, 192] > 0
    assert expanded_mask[130, 320] > 0
    assert expanded_mask[220, 256] == 0
