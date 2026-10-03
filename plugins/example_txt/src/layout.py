"""本文をページ画像に分ける。1文字も切らず、入らなければ分割を拒否する。"""
from dataclasses import dataclass

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter


# 横書き。
HORIZONTAL = "horizontal"
# 縦書き。
VERTICAL = "vertical"

# 縦書きで回転させる文字。
_ROTATE = set("ー―‐−–—～〜…‥=＝ｰ")
# 字体が空のときの既定。
_DEFAULT_FAMILY = "Meiryo"
# サイズが空のときの既定ポイント。
_DEFAULT_SIZE = 18


@dataclass(frozen=True)
class PageSettings:
    """ページ画像の字体、色、寸法、余白、縦横。"""

    font_family: str
    font_size: int
    text_color: str
    bg_color: str
    page_width: int
    page_height: int
    margin: int
    writing: str


def read_text(path: str, charset: str = "utf-8") -> str:
    """ファイルを文字コードで読み、改行とタブを揃える。

    Args:
        path: テキストファイル。
        charset: 復号に使う文字コード。空なら utf-8。

    Returns:
        BOM を外し、改行を LF、タブを空白4つにした本文。
    """
    data = open(path, "rb").read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    encoding = charset or "utf-8"
    try:
        text = data.decode(encoding)
    except LookupError:
        # 未知の文字コードなら utf-8 で読み替える。
        text = data.decode("utf-8", errors="replace")
    except UnicodeDecodeError:
        # 復号できなければ置換して読み続ける。
        text = data.decode(encoding, errors="replace")
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ")


def resolve_settings(raw: PageSettings, app_family: str, app_size: int) -> PageSettings:
    """空の字体とサイズをアプリ側か既定で埋め、寸法を1以上に揃える。

    Args:
        raw: プラグイン設定の値。
        app_family: アプリの字体名。
        app_size: アプリのサイズ。

    Returns:
        揃えた PageSettings。縦書き以外は横書き。
    """
    family = (raw.font_family or "").strip() or (app_family or "").strip() or _DEFAULT_FAMILY
    size = raw.font_size if raw.font_size and raw.font_size > 0 else (app_size or _DEFAULT_SIZE)
    writing = VERTICAL if raw.writing == VERTICAL else HORIZONTAL
    return PageSettings(
        font_family=family,
        font_size=max(1, int(size)),
        text_color=raw.text_color or "#222222",
        bg_color=raw.bg_color or "#f7f2e8",
        page_width=max(1, int(raw.page_width)),
        page_height=max(1, int(raw.page_height)),
        margin=max(0, int(raw.margin)),
        writing=writing,
    )


def make_font(settings: PageSettings) -> QFont:
    """設定からアンチエイリアス付きの字体を作る。

    Args:
        settings: ページ設定。

    Returns:
        QFont。
    """
    font = QFont(settings.font_family, settings.font_size)
    font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    return font


def content_size(settings: PageSettings):
    """余白を除いた本文の幅と高さを返す。

    Args:
        settings: ページ設定。

    Returns:
        幅と高さ。
    """
    width = settings.page_width - settings.margin * 2
    height = settings.page_height - settings.margin * 2
    return width, height


def _metrics(settings: PageSettings) -> QFontMetrics:
    """設定の字体のメトリクスを返す。

    Args:
        settings: ページ設定。

    Returns:
        QFontMetrics。
    """
    return QFontMetrics(make_font(settings))


def _cell_size(metrics: QFontMetrics):
    """縦書き1文字分の幅と高さを返す。

    Args:
        metrics: 字体のメトリクス。

    Returns:
        1以上の幅と高さ。
    """
    sample = metrics.horizontalAdvance("あ")
    if sample <= 0:
        sample = metrics.averageCharWidth()
    height = max(metrics.height(), metrics.lineSpacing())
    width = max(sample, height)
    return max(1, width), max(1, height)


def layout_fits(settings: PageSettings) -> bool:
    """本文領域に1文字以上入るなら True。

    Args:
        settings: ページ設定。

    Returns:
        横書きは行高と1文字幅、縦書きはセルが領域に入れば True。
    """
    content_w, content_h = content_size(settings)
    if content_w < 1 or content_h < 1:
        return False
    metrics = _metrics(settings)
    if settings.writing == VERTICAL:
        cell_w, cell_h = _cell_size(metrics)
        return cell_w <= content_w and cell_h <= content_h
    line_h = max(metrics.lineSpacing(), 1)
    min_w = max(metrics.horizontalAdvance("あ"), metrics.averageCharWidth(), 1)
    return line_h <= content_h and min_w <= content_w


def paginate(text: str, settings: PageSettings, start: int = 0, end: int | None = None):
    """本文をページの文字範囲に分ける。入らなければ None。

    Args:
        text: 本文。
        settings: ページ設定。
        start: 開始位置。
        end: 終了位置。None なら文末。

    Returns:
        各ページの開始と終了。1文字も入らなければ None。空範囲は1ページ。
    """
    if end is None:
        end = len(text)
    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))
    if not layout_fits(settings):
        return None
    if start == end:
        return [(start, end)]
    if settings.writing == VERTICAL:
        return _paginate_vertical(text, settings, start, end)
    return _paginate_horizontal(text, settings, start, end)


def paginate_anchored(text: str, settings: PageSettings, anchor: int):
    """anchor の位置で前後に分けてページ範囲を繋ぐ。

    Args:
        text: 本文。
        settings: ページ設定。
        anchor: 残したい文字位置。

    Returns:
        前後を繋いだページ範囲。どちらかが失敗なら None。先頭なら通常の分割。
    """
    anchor = max(0, min(int(anchor), len(text)))
    if anchor <= 0:
        return paginate(text, settings)
    before = paginate(text, settings, 0, anchor)
    after = paginate(text, settings, anchor, len(text))
    if before is None or after is None:
        return None
    return before + after


def page_index_for_start(pages, start: int) -> int:
    """開始位置を含むページ番号を返す。

    Args:
        pages: ページの開始と終了。
        start: 探す文字位置。

    Returns:
        一致するページ。無ければ含むページ、それも無ければ最後。
    """
    for index, (begin, _) in enumerate(pages):
        if begin == start:
            return index
    for index, (begin, finish) in enumerate(pages):
        if begin <= start < finish:
            return index
    return max(0, len(pages) - 1)


def render_page(text: str, start: int, end: int, settings: PageSettings) -> bytes:
    """指定範囲を PNG バイト列にする。

    Args:
        text: 本文。
        start: 開始位置。
        end: 終了位置。
        settings: ページ設定。

    Returns:
        PNG バイト列。
    """
    image = QImage(settings.page_width, settings.page_height, QImage.Format.Format_RGB32)
    image.fill(QColor(settings.bg_color))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setFont(make_font(settings))
    painter.setPen(QColor(settings.text_color))
    if settings.writing == VERTICAL:
        _draw_vertical(painter, text, start, end, settings)
    else:
        _draw_horizontal(painter, text, start, end, settings)
    painter.end()
    blob = QByteArray()
    buffer = QBuffer(blob)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    return bytes(blob)


def _is_cjk(char: str) -> bool:
    """ひらがな、カタカナ、CJK、句読点の範囲なら True。

    Args:
        char: 1文字。

    Returns:
        その範囲なら True。
    """
    code = ord(char)
    return (
        0x3040 <= code <= 0x30FF
        or 0x3400 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0xFF66 <= code <= 0xFF9D
        or 0x3000 <= code <= 0x303F
    )


def _iter_horizontal_lines(text: str, start: int, end: int, metrics: QFontMetrics, max_width: int):
    """幅に収まる行の開始と終了を順に出す。

    Args:
        text: 本文。
        start: 開始位置。
        end: 終了位置。
        metrics: 字体のメトリクス。
        max_width: 行の最大幅。

    Returns:
        各行の開始位置と終了位置。改行も含む。
    """
    index = start
    while index < end:
        if text[index] == "\n":
            yield index, index + 1
            index += 1
            continue
        cursor = index
        last_break = index
        width = 0
        while cursor < end and text[cursor] != "\n":
            advance = max(metrics.horizontalAdvance(text[cursor]), 1)
            if width + advance > max_width and cursor > index:
                break
            width += advance
            cursor += 1
            prev = text[cursor - 1]
            if prev.isspace() or _is_cjk(prev):
                last_break = cursor
        if cursor < end and text[cursor] != "\n" and last_break > index:
            nxt = text[cursor]
            if not _is_cjk(nxt) and not nxt.isspace():
                cursor = last_break
        if cursor == index:
            cursor = index + 1
        yield index, cursor
        index = cursor


def _paginate_horizontal(text: str, settings: PageSettings, start: int, end: int):
    """横書きでページ範囲を作る。

    Args:
        text: 本文。
        settings: ページ設定。
        start: 開始位置。
        end: 終了位置。

    Returns:
        各ページの開始と終了。
    """
    metrics = _metrics(settings)
    content_w, content_h = content_size(settings)
    line_h = max(metrics.lineSpacing(), 1)
    pages = []
    page_start = start
    used = 0
    for begin, finish in _iter_horizontal_lines(text, start, end, metrics, content_w):
        if used + line_h > content_h and used > 0:
            pages.append((page_start, begin))
            page_start = begin
            used = 0
        used += line_h
    if page_start < end or not pages:
        pages.append((page_start, end))
    return pages


def _paginate_vertical(text: str, settings: PageSettings, start: int, end: int):
    """縦書きでページ範囲を作る。

    Args:
        text: 本文。
        settings: ページ設定。
        start: 開始位置。
        end: 終了位置。

    Returns:
        各ページの開始と終了。
    """
    metrics = _metrics(settings)
    content_w, content_h = content_size(settings)
    cell_w, cell_h = _cell_size(metrics)
    max_rows = content_h // cell_h
    max_cols = content_w // cell_w
    pages = []
    page_start = start
    col = 0
    row = 0
    index = start
    while index < end:
        if text[index] == "\n":
            index += 1
            if row > 0:
                col += 1
                row = 0
            else:
                col += 1
            if col >= max_cols:
                pages.append((page_start, index))
                page_start = index
                col = 0
                row = 0
            continue
        if row >= max_rows:
            col += 1
            row = 0
            if col >= max_cols:
                pages.append((page_start, index))
                page_start = index
                col = 0
                row = 0
            continue
        index += 1
        row += 1
    if page_start < end or not pages:
        pages.append((page_start, end))
    return pages


def _draw_horizontal(painter: QPainter, text: str, start: int, end: int, settings: PageSettings):
    """横書きで範囲を描く。

    Args:
        painter: 描画先。
        text: 本文。
        start: 開始位置。
        end: 終了位置。
        settings: ページ設定。
    """
    metrics = QFontMetrics(painter.font())
    content_w, _content_h = content_size(settings)
    line_h = max(metrics.lineSpacing(), 1)
    top = settings.margin
    y = top
    for begin, finish in _iter_horizontal_lines(text, start, end, metrics, content_w):
        line = text[begin:finish].rstrip("\n")
        rect = QRect(settings.margin, y, content_w, line_h)
        if line:
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), line)
        y += line_h


def _draw_vertical(painter: QPainter, text: str, start: int, end: int, settings: PageSettings):
    """縦書きで範囲を描く。

    Args:
        painter: 描画先。
        text: 本文。
        start: 開始位置。
        end: 終了位置。
        settings: ページ設定。
    """
    metrics = QFontMetrics(painter.font())
    content_w, content_h = content_size(settings)
    cell_w, cell_h = _cell_size(metrics)
    max_rows = max(1, content_h // cell_h)
    max_cols = max(1, content_w // cell_w)
    right = settings.margin + content_w
    col = 0
    row = 0
    index = start
    while index < end and col < max_cols:
        char = text[index]
        if char == "\n":
            index += 1
            if row > 0:
                col += 1
                row = 0
            else:
                col += 1
            continue
        if row >= max_rows:
            col += 1
            row = 0
            continue
        x = right - (col + 1) * cell_w
        y = settings.margin + row * cell_h
        rect = QRect(x, y, cell_w, cell_h)
        if char != " ":
            _draw_vertical_char(painter, rect, char)
        index += 1
        row += 1


def _draw_vertical_char(painter: QPainter, rect: QRect, char: str):
    """1文字を描き、伸ばし棒などは90度回す。

    Args:
        painter: 描画先。
        rect: 1文字の矩形。
        char: 描く文字。
    """
    align = int(Qt.AlignmentFlag.AlignCenter)
    if char not in _ROTATE:
        painter.drawText(rect, align, char)
        return
    painter.save()
    painter.translate(rect.center())
    painter.rotate(90)
    rotated = QRect(-rect.width() // 2, -rect.height() // 2, rect.width(), rect.height())
    painter.drawText(rotated, align, char)
    painter.restore()
