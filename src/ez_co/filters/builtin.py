"""本体の基本補正。台帳上は builtin:basic の1件。内部順は明るさ→コントラスト→ガンマ→グレースケール。"""
from __future__ import annotations

from typing import Mapping, Optional

from PIL import ImageEnhance, ImageOps
from PIL.Image import Image

from ez_co.filters.registry import FilterRecord, FilterRegistry, get_filter_registry
from ez_co.utils.language_manager import get_text

BUILTIN_FILTER_ID = "builtin:basic"
_IDENTITY_GAMMA = 1e-9
_BRIGHTNESS_RANGE = (-100, 100)
_CONTRAST_RANGE = (-100, 100)
_GAMMA_RANGE = (0.2, 3.0)


def default_basic_settings() -> dict:
    return {
        "brightness": 0,
        "contrast": 0,
        "gamma": 1.0,
        "grayscale": False,
    }


def _as_int(value, fallback: int) -> int:
    try:
        if isinstance(value, bool):
            return fallback
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _as_float(value, fallback: float) -> float:
    try:
        if isinstance(value, bool):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def normalize_basic_settings(raw: Optional[Mapping] = None) -> dict:
    settings = default_basic_settings()
    if not isinstance(raw, Mapping):
        return settings
    lo, hi = _BRIGHTNESS_RANGE
    settings["brightness"] = max(lo, min(hi, _as_int(raw.get("brightness"), 0)))
    lo, hi = _CONTRAST_RANGE
    settings["contrast"] = max(lo, min(hi, _as_int(raw.get("contrast"), 0)))
    lo, hi = _GAMMA_RANGE
    gamma = _as_float(raw.get("gamma"), 1.0)
    settings["gamma"] = max(lo, min(hi, gamma))
    settings["grayscale"] = bool(raw.get("grayscale", False))
    return settings


def is_basic_identity(settings: Optional[Mapping] = None) -> bool:
    values = normalize_basic_settings(settings)
    return (
        values["brightness"] == 0
        and values["contrast"] == 0
        and abs(values["gamma"] - 1.0) <= _IDENTITY_GAMMA
        and not values["grayscale"]
    )


def _enhanceable(image: Image) -> Image:
    if image.mode in ("RGB", "RGBA", "L"):
        return image
    return image.convert("RGB")


def _apply_gamma(image: Image, gamma: float) -> Image:
    inv = 1.0 / gamma
    lut = [min(255, max(0, int(round(((index / 255.0) ** inv) * 255.0)))) for index in range(256)]
    if image.mode == "RGB":
        return image.point(lut * 3)
    if image.mode == "RGBA":
        return image.point(lut * 3 + list(range(256)))
    return image.point(lut)


def process_basic(image: Image, context) -> Image:
    settings = normalize_basic_settings(getattr(context, "settings", None))
    if is_basic_identity(settings):
        return image
    current = _enhanceable(image)
    brightness = settings["brightness"]
    if brightness:
        current = ImageEnhance.Brightness(current).enhance(1.0 + brightness / 100.0)
    contrast = settings["contrast"]
    if contrast:
        current = ImageEnhance.Contrast(current).enhance(1.0 + contrast / 100.0)
    gamma = settings["gamma"]
    if abs(gamma - 1.0) > _IDENTITY_GAMMA:
        current = _apply_gamma(current, gamma)
    if settings["grayscale"]:
        mode = current.mode
        current = ImageOps.grayscale(current)
        if mode in ("RGB", "RGBA"):
            current = current.convert(mode)
    return current


def register_builtin(registry: Optional[FilterRegistry] = None) -> FilterRecord:
    registry = registry or get_filter_registry()
    record = FilterRecord(
        public_id=BUILTIN_FILTER_ID,
        plugin_id="",
        local_id="basic",
        title=get_text("ui.filter_basic"),
        process=process_basic,
        has_settings=True,
    )
    registry.register(record)
    return record
