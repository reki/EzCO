"""表示確認用の加工。

サンプルプラグイン経由で開いていることが後から見ても分かるよう、
わざと色を重ねて「プラグイン読み込み表示」と描いている。本番プラグインの必須処理ではない。
"""
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_FONT_CANDIDATES = (
    "YuGothB.ttc",
    "YuGothM.ttc",
    "meiryo.ttc",
    "msgothic.ttc",
    "arial.ttf",
)


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


def mark_image(data, label, tint=(30, 120, 220)):
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
