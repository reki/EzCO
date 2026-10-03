"""本体の基本補正。台帳上は builtin:basic の1件。内部順は明るさ→コントラスト→ガンマ→グレースケール。"""
from __future__ import annotations

from typing import Mapping, Optional

from PIL import ImageEnhance, ImageOps
from PIL.Image import Image

from ez_co.filters.registry import FilterRecord, FilterRegistry, get_filter_registry
from ez_co.utils.language_manager import get_text

# 本体の基本補正のフィルター ID
BUILTIN_FILTER_ID = "builtin:basic"
# ガンマをかけないとみなす差の下限
_IDENTITY_GAMMA = 1e-9
# 明るさの下限と上限
_BRIGHTNESS_RANGE = (-100, 100)
# コントラストの下限と上限
_CONTRAST_RANGE = (-100, 100)
# ガンマの下限と上限
_GAMMA_RANGE = (0.2, 3.0)


def default_basic_settings() -> dict:
    """基本補正の初期設定を返す。

    Returns:
        明るさ 0、コントラスト 0、ガンマ 1.0、グレースケール無効。
    """
    return {
        "brightness": 0,
        "contrast": 0,
        "gamma": 1.0,
        "grayscale": False,
    }


def _as_int(value, fallback: int) -> int:
    """値を整数にする。

    Args:
        value: 整数へ変換する値。
        fallback: 真偽値、または変換できないときの値。

    Returns:
        変換した整数。真偽値と変換失敗は fallback。
    """
    try:
        if isinstance(value, bool):
            return fallback
        return int(value)
    except (TypeError, ValueError):
        # 整数にできなければ fallback を返す
        return fallback


def _as_float(value, fallback: float) -> float:
    """値を浮動小数にする。

    Args:
        value: 浮動小数へ変換する値。
        fallback: 真偽値、または変換できないときの値。

    Returns:
        変換した数値。真偽値と変換失敗は fallback。
    """
    try:
        if isinstance(value, bool):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        # 数値にできなければ fallback を返す
        return fallback


def normalize_basic_settings(raw: Optional[Mapping] = None) -> dict:
    """基本補正の設定を範囲内に揃える。

    Args:
        raw: 補正設定。Mapping でなければ初期値を返す。

    Returns:
        明るさとコントラストは -100 から 100、ガンマは 0.2 から 3.0 に収め、グレースケールを真偽値にした設定。
    """
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
    """基本補正が未適用と同じかを返す。

    Args:
        settings: 調べる基本補正の設定。

    Returns:
        明るさとコントラストが 0、ガンマと 1.0 の差が微小値以下、グレースケールでなければ True。
    """
    values = normalize_basic_settings(settings)
    return (
        values["brightness"] == 0
        and values["contrast"] == 0
        and abs(values["gamma"] - 1.0) <= _IDENTITY_GAMMA
        and not values["grayscale"]
    )


def _enhanceable(image: Image) -> Image:
    """明るさとコントラストを掛けられるモードにする。

    Args:
        image: 調べる画像。

    Returns:
        RGB、RGBA、L はそのまま。それ以外は RGB に変換した画像。
    """
    if image.mode in ("RGB", "RGBA", "L"):
        return image
    return image.convert("RGB")


def _apply_gamma(image: Image, gamma: float) -> Image:
    """ガンマ補正を掛ける。

    Args:
        image: 補正する画像。
        gamma: 適用するガンマ。

    Returns:
        補正した画像。RGB は各チャンネル、RGBA は色だけ、それ以外はそのモードのテーブルで補正する。
    """
    inv = 1.0 / gamma
    lut = [min(255, max(0, int(round(((index / 255.0) ** inv) * 255.0)))) for index in range(256)]
    if image.mode == "RGB":
        return image.point(lut * 3)
    if image.mode == "RGBA":
        return image.point(lut * 3 + list(range(256)))
    return image.point(lut)


def process_basic(image: Image, context) -> Image:
    """明るさ、コントラスト、ガンマ、グレースケールの順に基本補正を掛ける。

    Args:
        image: 処理する画像。
        context: settings を持つ処理文脈。

    Returns:
        未適用と同じ設定なら元の画像。そうでなければ補正した画像。グレースケール後、直前のモードが RGB か RGBA ならそのモードに戻す。
    """
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
    """基本補正を台帳へ登録する。

    Args:
        registry: 登録先の台帳。省略時は共有台帳。

    Returns:
        登録した builtin:basic の記録。
    """
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
