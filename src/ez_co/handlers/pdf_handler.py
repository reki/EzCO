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
    normalize_archive_path,
    set_session_password,
)
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)

PAGE_NAME_RE = re.compile(r"^page_(\d+)\.png$", re.IGNORECASE)
IMAGE_NAME_RE = re.compile(r"^image_(\d+)\.png$", re.IGNORECASE)
DEFAULT_DPI = 150
MAX_RENDER_EDGE = 4000
_render_lock = threading.Lock()
_qtpdf_available: Optional[bool] = None


def page_virtual_name(page_number: int) -> str:
    return f"page_{page_number:04d}.png"


def image_virtual_name(image_number: int) -> str:
    return f"image_{image_number:04d}.png"


def parse_page_index(filename: str) -> Optional[int]:
    match = PAGE_NAME_RE.match(filename)
    if not match:
        return None
    return int(match.group(1)) - 1


def parse_image_index(filename: str) -> Optional[int]:
    match = IMAGE_NAME_RE.match(filename)
    if not match:
        return None
    return int(match.group(1)) - 1


def can_render_pages() -> bool:
    """QtPdf と QApplication が使えればページをそのまま描画できる。"""
    global _qtpdf_available
    if _qtpdf_available is False:
        return False
    try:
        from PySide6.QtPdf import QPdfDocument  # noqa: F401
        from PySide6.QtWidgets import QApplication
    except Exception:
        _qtpdf_available = False
        return False
    _qtpdf_available = True
    return QApplication.instance() is not None


def normalize_pdf_path(pdf_path: str) -> str:
    return normalize_archive_path(pdf_path)


def is_pdf_encrypted(pdf_path: str) -> bool:
    from ez_co.handlers.archive_password import is_encrypted
    return is_encrypted(pdf_path)


def try_unlock_pdf(pdf_path: str, password: str) -> bool:
    from ez_co.handlers.archive_password import try_unlock
    return try_unlock(pdf_path, password)


def _open_reader(pdf_path: str) -> PdfReader:
    reader = PdfReader(pdf_path)
    if not reader.is_encrypted:
        return reader
    password = get_session_password(pdf_path)
    if password is None:
        password = ""
    try:
        unlocked = reader.decrypt(password)
    except Exception as exc:
        reader.close()
        raise ValueError(get_log_text("debug_pdf_encrypted", pdf_path=pdf_path)) from exc
    if not unlocked:
        reader.close()
        raise ValueError(get_log_text("debug_pdf_encrypted", pdf_path=pdf_path))
    return reader


def list_pdf_entries(pdf_path: str) -> List[str]:
    """仮想ファイル名の一覧。描画可能なら各ページ、不可なら埋め込み画像。"""
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
    try:
        images = page.images
    except Exception as exc:
        logger.debug(get_log_text("debug_pdf_image_extract_failed", error=exc))
        return
    for item in images:
        yield item


def _image_from_embedded(item) -> Optional[Image.Image]:
    data = getattr(item, "data", None)
    if not data:
        return None
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image.convert("RGB") if image.mode not in ("RGB", "RGBA") else image
    except Exception as exc:
        logger.debug(get_log_text("debug_pdf_image_extract_failed", error=exc))
        return None


def _largest_embedded_image(pdf_path: str, page_index: int) -> Optional[Image.Image]:
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
    width = max(point_w * dpi / 72.0, 1.0)
    height = max(point_h * dpi / 72.0, 1.0)
    scale = min(1.0, MAX_RENDER_EDGE / max(width, height))
    return max(1, int(width * scale)), max(1, int(height * scale))


def _qimage_to_pil(qimage) -> Optional[Image.Image]:
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
