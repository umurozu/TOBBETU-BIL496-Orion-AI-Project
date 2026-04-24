from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HairstylePresetSpec:
    id: str
    label: str
    description: str
    filename: str
    width_ratio: float = 1.45
    bottom_anchor_ratio: float = 0.18
    x_shift_ratio: float = 0.0
    y_shift_ratio: float = 0.0


@dataclass(frozen=True)
class HairColorSpec:
    id: str
    label: str
    rgb: tuple[int, int, int]
    swatch: str
    strength: float = 0.78
    warmth: float = 0.0
    saturation: float = 0.0
    brightness: float = 0.0


HAIRSTYLE_PRESETS: tuple[HairstylePresetSpec, ...] = (
    HairstylePresetSpec(
        id="shape_01",
        label="Shape 1",
        description="Imported custom hairstyle reference with balanced crown volume.",
        filename="shape-01.png",
        width_ratio=1.52,
        bottom_anchor_ratio=0.22,
    ),
    HairstylePresetSpec(
        id="shape_02",
        label="Shape 2",
        description="Imported custom hairstyle reference with a fuller side silhouette.",
        filename="shape-02.png",
        width_ratio=1.58,
        bottom_anchor_ratio=0.24,
    ),
    HairstylePresetSpec(
        id="shape_03",
        label="Shape 3",
        description="Imported custom hairstyle reference with a tighter upper profile.",
        filename="shape-03.png",
        width_ratio=1.42,
        bottom_anchor_ratio=0.18,
    ),
    HairstylePresetSpec(
        id="shape_04",
        label="Shape 4",
        description="Imported custom hairstyle reference with a broader drape and longer falloff.",
        filename="shape-04.png",
        width_ratio=1.66,
        bottom_anchor_ratio=0.3,
    ),
)


HAIR_COLOR_OPTIONS: tuple[HairColorSpec, ...] = (
    HairColorSpec(
        id="natural_black",
        label="Natural Black",
        rgb=(28, 22, 19),
        swatch="#1c1613",
        strength=0.82,
        warmth=-0.08,
        saturation=0.02,
        brightness=-0.04,
    ),
    HairColorSpec(
        id="espresso_brown",
        label="Espresso Brown",
        rgb=(64, 42, 29),
        swatch="#402a1d",
        strength=0.8,
        warmth=0.02,
        saturation=0.05,
        brightness=-0.02,
    ),
    HairColorSpec(
        id="chestnut_brown",
        label="Chestnut Brown",
        rgb=(116, 74, 48),
        swatch="#744a30",
        strength=0.76,
        warmth=0.09,
        saturation=0.08,
        brightness=0.01,
    ),
    HairColorSpec(
        id="honey_blonde",
        label="Honey Blonde",
        rgb=(183, 146, 88),
        swatch="#b79258",
        strength=0.72,
        warmth=0.16,
        saturation=0.06,
        brightness=0.08,
    ),
    HairColorSpec(
        id="copper_red",
        label="Copper Red",
        rgb=(164, 83, 48),
        swatch="#a45330",
        strength=0.78,
        warmth=0.18,
        saturation=0.14,
        brightness=0.02,
    ),
)


DEFAULT_HAIRSTYLE_PRESET_ID = HAIRSTYLE_PRESETS[0].id
DEFAULT_HAIR_COLOR_ID = HAIR_COLOR_OPTIONS[0].id
