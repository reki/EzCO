"""表示確認用の加工。

サンプルフィルターが乗っていることが後から見ても分かるよう、
わざと色を重ねてラベルを描いている。本番プラグインの必須処理ではない。
example_zip の mark.py と同じ意図。色は青緑にしてローダー重ねと区別する。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "YuGothB.ttc",
    "YuGothM.ttc",
    "meiryo.ttc",
    "msgothic.ttc",
    "arial.ttf",
)
_TINT = (20, 140, 170)


def _load_font(size):
    fonts_dir = Path("C:/Windows/Fonts")
    for name in _FONT_CANDIDATES:
        path = fonts_dir / name
        if not path.is_file():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            continue
    return ImageFont.load_default()


def overlay_image(image, label, font_size, tint=_TINT):
    original_mode = image.mode
    rgba = image.convert("RGBA")
    wash = Image.new("RGBA", rgba.size, tint + (70,))
    rgba = Image.alpha_composite(rgba, wash)
    draw = ImageDraw.Draw(rgba)
    font = _load_font(max(1, int(font_size)))
    text_box = draw.textbbox((24, 24), label, font=font)
    pad = 12
    draw.rectangle(
        (text_box[0] - pad, text_box[1] - pad, text_box[2] + pad, text_box[3] + pad),
        fill=(0, 0, 0, 170),
    )
    draw.text((24, 24), label, fill=(180, 255, 240, 255), font=font)
    if original_mode == "RGBA":
        return rgba
    return rgba.convert("RGB")
