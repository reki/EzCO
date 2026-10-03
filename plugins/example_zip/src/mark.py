"""表示確認用の加工。

サンプルプラグイン経由で開いていることが後から見ても分かるよう、
わざと色を重ねて「プラグイン読み込み表示」と描いている。本番プラグインの必須処理ではない。
"""
import io
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


def mark_image(data, label, tint=(210, 70, 30)):
    """画像バイト列に色とラベルを重ね、PNG バイト列にする。

    Args:
        data: 元画像のバイト列。
        label: 描く文言。
        tint: 重ねる RGB。

    Returns:
        加工後の PNG バイト列。
    """
    # label は loader がホストの get_text("plugin.watermark") で取った文言。
    image = Image.open(io.BytesIO(data)).convert("RGBA")
    overlay = Image.new("RGBA", image.size, tint + (70,))
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)
    font_size = max(40, min(72, image.size[1] // 10, image.size[0] // 14))
    font = _load_font(font_size)
    text_box = draw.textbbox((24, 24), label, font=font)
    pad = 12
    draw.rectangle(
        (text_box[0] - pad, text_box[1] - pad, text_box[2] + pad, text_box[3] + pad),
        fill=(0, 0, 0, 170),
    )
    draw.text((24, 24), label, fill=(255, 230, 80, 255), font=font)
    out = io.BytesIO()
    image.convert("RGB").save(out, format="PNG")
    return out.getvalue()
