"""表示確認用の加工。

サンプルフィルターが乗っていることが後から見ても分かるよう、
わざと色を重ねてラベルを描いている。本番プラグインの必須処理ではない。
example_zip の mark.py と同じ意図。色は青緑にしてローダー重ねと区別する。
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# 加工表示に試す Windows 字体。
_FONT_CANDIDATES = (
    "YuGothB.ttc",
    "YuGothM.ttc",
    "meiryo.ttc",
    "msgothic.ttc",
    "arial.ttf",
)
# 加工表示に重ねる色。
_TINT = (20, 140, 170)


def _load_font(size):
    """候補の Windows 字体を読み、無ければ既定字体を返す。

    Args:
        size: ポイントサイズ。

    Returns:
        読み込んだ字体。失敗時は既定字体。
    """
    fonts_dir = Path("C:/Windows/Fonts")
    for name in _FONT_CANDIDATES:
        path = fonts_dir / name
        if not path.is_file():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except OSError:
            # 字体を開けなければ次の候補へ進む。
            continue
    return ImageFont.load_default()


def overlay_image(image, label, font_size, tint=_TINT):
    """画像に色とラベルを重ね、元のモードに合わせて返す。

    Args:
        image: 加工する画像。
        label: 描く文言。
        font_size: ラベルのサイズ。
        tint: 重ねる RGB。

    Returns:
        RGBA の元画像なら RGBA、それ以外は RGB。
    """
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
