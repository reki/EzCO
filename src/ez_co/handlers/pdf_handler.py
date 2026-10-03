"""PDF を ZIP と同様の仮想パスとして扱う。

ページは QtPdf でそのまま描画する。描画できない場合のみ pypdf で
埋め込み画像を取り出す。
"""
from __future__ import annotations

import io
import logging
import re
import threading
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image
from pypdf import PdfReader

from ez_co.handlers.archive_password import (
    get_session_password,
)
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)

# ページ画像名から番号を取る正規表現
PAGE_NAME_RE = re.compile(r"^page_(\d+)\.png$", re.IGNORECASE)
# 埋め込み画像名から番号を取る正規表現
IMAGE_NAME_RE = re.compile(r"^image_(\d+)\.png$", re.IGNORECASE)
# PDF を描画するときの既定 DPI
DEFAULT_DPI = 150
# 描画画像の長辺の上限
MAX_RENDER_EDGE = 4000
_render_lock = threading.Lock()
_qtpdf_available: Optional[bool] = None


def page_virtual_name(page_number: int) -> str:
    """ページ番号から仮想ファイル名を作る。

    Args:
        page_number: 1 始まりのページ番号。

    Returns:
        page_ に続く 4 桁の png 名。
    """
    return f"page_{page_number:04d}.png"


def image_virtual_name(image_number: int) -> str:
    """埋め込み画像の番号から仮想ファイル名を作る。

    Args:
        image_number: 1 始まりの画像番号。

    Returns:
        image_ に続く 4 桁の png 名。
    """
    return f"image_{image_number:04d}.png"


def parse_page_index(filename: str) -> Optional[int]:
    """ページ用の仮想ファイル名から 0 始まりの番号を取り出す。

    Args:
        filename: 仮想ファイル名。

    Returns:
        ページ名なら 0 始まりの番号。違えば None。
    """
    match = PAGE_NAME_RE.match(filename)
    if not match:
        return None
    return int(match.group(1)) - 1


def parse_image_index(filename: str) -> Optional[int]:
    """埋め込み画像用の仮想ファイル名から 0 始まりの番号を取り出す。

    Args:
        filename: 仮想ファイル名。

    Returns:
        画像名なら 0 始まりの番号。違えば None。
    """
    match = IMAGE_NAME_RE.match(filename)
    if not match:
        return None
    return int(match.group(1)) - 1


def can_render_pages() -> bool:
    """QtPdf と QApplication が使えればページをそのまま描画できる。

    Returns:
        両方使えるとき真。QtPdf を読み込めないときは以降も偽。
    """
    global _qtpdf_available
    if _qtpdf_available is False:
        return False
    try:
        from PySide6.QtPdf import QPdfDocument  # noqa: F401
        from PySide6.QtWidgets import QApplication
    except Exception:
        # QtPdf を読み込めなければ、以降は描画できないものとして偽を返す
        _qtpdf_available = False
        return False
    _qtpdf_available = True
    return QApplication.instance() is not None


def _open_reader(pdf_path: str) -> PdfReader:
    """パスワードが要る PDF ならセッションのパスワードで開く。

    Args:
        pdf_path: PDF のパス。

    Returns:
        開けたリーダ。

    Raises:
        ValueError: 暗号化されていて、セッションのパスワードか空文字で解けないとき。
    """
    reader = PdfReader(pdf_path)
    if not reader.is_encrypted:
        return reader
    password = get_session_password(pdf_path)
    if password is None:
        password = ""
    try:
        unlocked = reader.decrypt(password)
    except Exception as exc:
        # 復号に失敗したらリーダを閉じて、暗号化エラーとして送出する
        reader.close()
        raise ValueError(get_log_text("debug_pdf_encrypted", pdf_path=pdf_path)) from exc
    if not unlocked:
        reader.close()
        raise ValueError(get_log_text("debug_pdf_encrypted", pdf_path=pdf_path))
    return reader


def list_pdf_entries(pdf_path: str) -> List[str]:
    """仮想ファイル名の一覧を返す。

    Args:
        pdf_path: PDF のパス。

    Returns:
        描画可能なら各ページ、不可なら埋め込み画像。ページが無ければ空。
    """
    reader = _open_reader(pdf_path)
    try:
        page_count = len(reader.pages)
        if page_count == 0:
            logger.warning(get_log_text("debug_pdf_no_pages", pdf_path=pdf_path))
            return []
        if can_render_pages():
            return [page_virtual_name(i + 1) for i in range(page_count)]
        names = []
        image_number = 1
        for page in reader.pages:
            for _ in _iter_page_images(page):
                names.append(image_virtual_name(image_number))
                image_number += 1
        if not names:
            logger.warning(get_log_text("debug_pdf_no_embedded_images", pdf_path=pdf_path))
        return names
    finally:
        reader.close()


def load_pdf_image(pdf_path: str, filename: str) -> Optional[Image.Image]:
    """仮想ファイル名に対応する PDF の画像を返す。

    Args:
        pdf_path: PDF のパス。
        filename: ページ名か埋め込み画像名。

    Returns:
        読めた画像。名前がどちらでもなければ None。ページ描画に失敗したときはそのページの最大の埋め込み画像。
    """
    page_index = parse_page_index(filename)
    if page_index is not None:
        image = _render_page(pdf_path, page_index)
        if image is not None:
            return image
        logger.info(get_log_text("debug_pdf_render_fallback_images", pdf_path=pdf_path, page=page_index + 1))
        return _largest_embedded_image(pdf_path, page_index)

    image_index = parse_image_index(filename)
    if image_index is not None:
        return _embedded_image_at(pdf_path, image_index)

    logger.error(get_log_text("debug_file_not_found_in_archive", filename=filename))
    return None


def _iter_page_images(page):
    """ページ内の埋め込み画像を順に返す。

    Args:
        page: PDF のページ。

    Returns:
        埋め込み画像。取得に失敗したときは空。
    """
    try:
        images = page.images
    except Exception as exc:
        # 埋め込み画像を取れなければデバッグログを残して、何も返さない
        logger.debug(get_log_text("debug_pdf_image_extract_failed", error=exc))
        return
    for item in images:
        yield item


def _image_from_embedded(item) -> Optional[Image.Image]:
    """埋め込み画像のバイト列から PIL 画像を作る。

    Args:
        item: 埋め込み画像。

    Returns:
        RGB または RGBA の画像。データが無いか読めなければ None。
    """
    data = getattr(item, "data", None)
    if not data:
        return None
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image.convert("RGB") if image.mode not in ("RGB", "RGBA") else image
    except Exception as exc:
        # 画像へ変換できなければデバッグログを残して None を返す
        logger.debug(get_log_text("debug_pdf_image_extract_failed", error=exc))
        return None


def _largest_embedded_image(pdf_path: str, page_index: int) -> Optional[Image.Image]:
    """指定ページで最も大きい埋め込み画像を返す。

    Args:
        pdf_path: PDF のパス。
        page_index: 0 始まりのページ番号。

    Returns:
        画素数が最大の画像。ページが範囲外か画像が無ければ None。
    """
    reader = _open_reader(pdf_path)
    try:
        if page_index < 0 or page_index >= len(reader.pages):
            return None
        best = None
        best_pixels = -1
        for item in _iter_page_images(reader.pages[page_index]):
            image = _image_from_embedded(item)
            if image is None:
                continue
            pixels = image.width * image.height
            if pixels > best_pixels:
                if best is not None:
                    best.close()
                best = image
                best_pixels = pixels
            else:
                image.close()
        return best
    finally:
        reader.close()


def _embedded_image_at(pdf_path: str, image_index: int) -> Optional[Image.Image]:
    """文書全体で数えた埋め込み画像を返す。

    Args:
        pdf_path: PDF のパス。
        image_index: 0 始まりの画像番号。

    Returns:
        その番号の画像。無ければ None。
    """
    reader = _open_reader(pdf_path)
    try:
        current = 0
        for page in reader.pages:
            for item in _iter_page_images(page):
                if current == image_index:
                    return _image_from_embedded(item)
                current += 1
        return None
    finally:
        reader.close()


def _render_size(point_w: float, point_h: float, dpi: int = DEFAULT_DPI) -> Tuple[int, int]:
    """ポイント寸法から描画ピクセル数を決める。

    Args:
        point_w: ページ幅。
        point_h: ページ高さ。
        dpi: 描画に使う解像度。

    Returns:
        長辺を上限内に収めた幅と高さ。どちらも 1 以上。
    """
    width = max(point_w * dpi / 72.0, 1.0)
    height = max(point_h * dpi / 72.0, 1.0)
    scale = min(1.0, MAX_RENDER_EDGE / max(width, height))
    return max(1, int(width * scale)), max(1, int(height * scale))


def _qimage_to_pil(qimage) -> Optional[Image.Image]:
    """QImage を白地の RGB 画像にする。

    Args:
        qimage: 変換する画像。

    Returns:
        変換した画像。空やバイト列が足りなければ None。
    """
    from PySide6.QtGui import QImage

    if qimage is None or qimage.isNull():
        return None
    converted = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = converted.width(), converted.height()
    bytes_per_line = converted.bytesPerLine()
    ptr = converted.constBits()
    raw = bytes(ptr)
    expected = bytes_per_line * height
    if len(raw) < expected:
        return None
    image = Image.frombytes("RGBA", (width, height), raw, "raw", "RGBA", bytes_per_line, 1)
    background = Image.new("RGB", image.size, (255, 255, 255))
    background.paste(image, mask=image.split()[-1])
    return background


def _render_page(pdf_path: str, page_index: int) -> Optional[Image.Image]:
    """QtPdf でページを描画して PIL 画像にする。

    Args:
        pdf_path: PDF のパス。
        page_index: 0 始まりのページ番号。

    Returns:
        描画した画像。描画できない、準備できない、範囲外のときは None。
    """
    if not can_render_pages():
        return None
    from PySide6.QtCore import QEventLoop, QSize, QTimer
    from PySide6.QtPdf import QPdfDocument

    path = str(Path(pdf_path))
    with _render_lock:
        document = QPdfDocument()
        password = get_session_password(pdf_path)
        if password:
            document.setPassword(password)
        document.load(path)
        if document.status() == QPdfDocument.Status.Loading:
            loop = QEventLoop()
            document.statusChanged.connect(
                lambda status: loop.quit() if status != QPdfDocument.Status.Loading else None
            )
            QTimer.singleShot(15000, loop.quit)
            loop.exec()
        if document.status() != QPdfDocument.Status.Ready:
            if document.error() == QPdfDocument.Error.IncorrectPassword:
                logger.warning(get_log_text("debug_pdf_encrypted", pdf_path=pdf_path))
            else:
                logger.warning(get_log_text("debug_pdf_render_failed", pdf_path=pdf_path, page=page_index + 1))
            return None
        if page_index < 0 or page_index >= document.pageCount():
            return None
        point_size = document.pagePointSize(page_index)
        width, height = _render_size(point_size.width(), point_size.height())
        qimage = document.render(page_index, QSize(width, height))
        image = _qimage_to_pil(qimage)
        document.close()
        return image
