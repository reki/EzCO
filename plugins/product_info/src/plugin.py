import json
import logging
import re
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap

from fetch import fetch_product, match_product

logger = logging.getLogger(__name__)

_AGE_STYLES = {
    "R18": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #d32f2f; color: white;",
    "R-15": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #388e3c; color: white;",
    "全年齢": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #1976d2; color: white;",
}
_CATEGORY_STYLES = {
    "maniax": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #e91e63; color: white;",
    "books": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #ff9800; color: white;",
    "home": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #2196f3; color: white;",
    "pro": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #9c27b0; color: white;",
}
_WORK_STYLES = {
    "ゲーム": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #f44336; color: white;",
    "マンガ": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #ff9800; color: white;",
    "CG・イラスト": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #4caf50; color: white;",
    "ノベル": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #2196f3; color: white;",
    "動画": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #9c27b0; color: white;",
    "ボイス・ASMR": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #e91e63; color: white;",
    "音楽": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #ff5722; color: white;",
    "ツール/アクセサリ": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #607d8b; color: white;",
    "DMM": "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #ff6f00; color: white;",
}


class _FetchWorker(QObject):
    finished = Signal(str, object)

    def __init__(self, folder, kind, product_id):
        super().__init__()
        self.folder = folder
        self.kind = kind
        self.product_id = product_id

    def run(self):
        data = None
        try:
            data = fetch_product(self.kind, self.product_id)
        except Exception:
            data = None
        self.finished.emit(self.folder, data)


def _alive(widget):
    if widget is None:
        return False
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


class ProductInfoPlugin:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self.widget = None
        self._url = ""
        self._listening = False
        self._folder = None
        self._cache = {}
        self._fetch_token = 0
        self._thread = None
        self._worker = None
        self.host.register_config(
            "fetch_web",
            "bool",
            True,
            label=self.get_text("fetch_web"),
            description=self.get_text("fetch_web_help"),
        )

    def setup(self):
        if not _alive(self.widget):
            self.widget = self.host.load_ui(self.root.read_bytes("resources/sidebar.ui"))
            self._wire()
        if not self._listening:
            self.host.on("current_changed", self._on_current)
            self.host.on("config_changed", self._on_config)
            self._listening = True
        self.host.register_sidebar(
            "product_info",
            self.get_text("title"),
            self.widget,
            aliases=("toggle_product_info_dock",),
        )
        self.refresh(self.host.get_current("folder"))

    def teardown(self):
        self._stop_fetch()
        if self._listening:
            self.host.off("current_changed", self._on_current)
            self.host.off("config_changed", self._on_config)
            self._listening = False
        self.host.unregister_sidebar("product_info")
        self.widget = None

    def _wire(self):
        from PySide6.QtWidgets import QFrame, QLabel, QPushButton

        self.emptyLabel = self.widget.findChild(QLabel, "emptyLabel")
        self.errorLabel = self.widget.findChild(QLabel, "errorLabel")
        self.titleLabel = self.widget.findChild(QLabel, "titleLabel")
        self.ageLabel = self.widget.findChild(QLabel, "ageLabel")
        self.categoryLabel = self.widget.findChild(QLabel, "categoryLabel")
        self.workTypeLabel = self.widget.findChild(QLabel, "workTypeLabel")
        self.urlButton = self.widget.findChild(QPushButton, "urlButton")
        self.coverLabel = self.widget.findChild(QLabel, "coverLabel")
        self.basicFrame = self.widget.findChild(QFrame, "basicFrame")
        self.pidLabel = self.widget.findChild(QLabel, "pidLabel")
        self.brandLabel = self.widget.findChild(QLabel, "brandLabel")
        self.fileFormatLabel = self.widget.findChild(QLabel, "fileFormatLabel")
        self.workFormatLabel = self.widget.findChild(QLabel, "workFormatLabel")
        self.genreTitleLabel = self.widget.findChild(QLabel, "genreTitleLabel")
        self.genreLabel = self.widget.findChild(QLabel, "genreLabel")
        self.overviewTitleLabel = self.widget.findChild(QLabel, "overviewTitleLabel")
        self.overviewLabel = self.widget.findChild(QLabel, "overviewLabel")
        header = self.widget.findChild(QLabel, "headerLabel")
        if header is not None:
            header.setText(self.get_text("title"))
        if self.emptyLabel is not None:
            self.emptyLabel.setText(self.get_text("empty"))
        if self.urlButton is not None:
            self.urlButton.setText(self.get_text("open_page"))
            self.urlButton.clicked.connect(self._open_url)
        if self.genreTitleLabel is not None:
            self.genreTitleLabel.setText(self.get_text("genre") + ":")
        if self.overviewTitleLabel is not None:
            self.overviewTitleLabel.setText(self.get_text("overview") + ":")
        self._show_empty()

    def _on_current(self, payload=None):
        folder = None
        if isinstance(payload, dict):
            folder = payload.get("folder")
        if not folder:
            folder = self.host.get_current("folder")
        self.refresh(folder)

    def _on_config(self, payload=None):
        if isinstance(payload, dict) and payload.get("key") not in (None, "fetch_web"):
            return
        if not self.host.get_config("fetch_web", True):
            self._stop_fetch()
            if self._folder and not (Path(self._folder) / "info.json").exists():
                self._cache.pop(self._folder, None)
                if _alive(self.widget):
                    self._show_empty()
            return
        self.refresh(self._folder or self.host.get_current("folder"))

    def _fetch_enabled(self) -> bool:
        return bool(self.host.get_config("fetch_web", True))

    def refresh(self, folder_path):
        if not _alive(self.widget):
            return
        self._folder = folder_path
        if not folder_path:
            self._stop_fetch()
            self._show_empty()
            return
        info_path = Path(folder_path) / "info.json"
        if info_path.exists():
            self._stop_fetch()
            try:
                with open(info_path, "r", encoding="utf-8") as handle:
                    data = json.load(handle)
            except Exception as exc:
                self._show_error(self.get_text("load_failed", error=str(exc)))
                return
            self._show_info(data, folder_path)
            return
        cached = self._cache.get(folder_path)
        if cached is not None:
            self._show_info(cached[0], folder_path, cached[1])
            return
        self._show_empty()
        if not self._fetch_enabled():
            self._stop_fetch()
            return
        matched = match_product(Path(folder_path).name)
        if matched is None:
            current = self.host.get_current("path")
            if current:
                matched = match_product(Path(str(current)).name)
        if matched is None:
            self._stop_fetch()
            return
        self._start_fetch(folder_path, matched[0], matched[1])

    def _start_fetch(self, folder_path, kind, product_id):
        self._stop_fetch()
        self._fetch_token += 1
        worker = _FetchWorker(folder_path, kind, product_id)
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_fetched)
        worker.finished.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        thread.start()

    def _stop_fetch(self):
        self._fetch_token += 1
        thread = self._thread
        self._thread = None
        self._worker = None
        if thread is not None and thread.isRunning():
            thread.quit()

    def _on_fetched(self, folder_path, data):
        if folder_path != self._folder or not _alive(self.widget):
            return
        if not data:
            return
        cover = data.pop("_cover", None)
        self._cache[folder_path] = (data, cover)
        self._show_info(data, folder_path, cover)

    def _set_visible(self, widget, visible):
        if widget is not None:
            widget.setVisible(bool(visible))

    def _hide_content(self):
        for name in (
            "titleLabel", "ageLabel", "categoryLabel", "workTypeLabel", "urlButton",
            "coverLabel", "basicFrame", "pidLabel", "brandLabel", "fileFormatLabel",
            "workFormatLabel", "genreTitleLabel", "genreLabel", "overviewTitleLabel",
            "overviewLabel",
        ):
            self._set_visible(getattr(self, name, None), False)

    def _show_empty(self):
        self._hide_content()
        self._set_visible(self.errorLabel, False)
        self._set_visible(self.emptyLabel, True)

    def _show_error(self, message):
        self._hide_content()
        self._set_visible(self.emptyLabel, False)
        if self.errorLabel is not None:
            self.errorLabel.setText(message)
        self._set_visible(self.errorLabel, True)

    def _show_info(self, data, folder_path, cover_bytes=None):
        self._set_visible(self.emptyLabel, False)
        self._set_visible(self.errorLabel, False)
        title = data.get("タイトル") or self.get_text("unknown_title")
        if self.titleLabel is not None:
            self.titleLabel.setText(str(title))
        self._set_visible(self.titleLabel, True)

        is_dmm = data.get("作品種別") == "DMM"
        age = "" if is_dmm else str(data.get("年齢種別") or "")
        category = "" if is_dmm else str(data.get("カテゴリー") or "")
        work_type = str(data.get("作品種別") or "")
        self._badge(self.ageLabel, age, _AGE_STYLES)
        self._badge(self.categoryLabel, category, _CATEGORY_STYLES)
        self._badge(self.workTypeLabel, work_type, _WORK_STYLES)

        self._url = str(data.get("URL") or "")
        self._set_visible(self.urlButton, bool(self._url))

        shown_cover = False
        pixmap = QPixmap()
        if cover_bytes:
            pixmap.loadFromData(cover_bytes)
        else:
            cover = Path(folder_path) / "folder.jpg"
            if cover.exists():
                pixmap = QPixmap(str(cover))
        if self.coverLabel is not None and not pixmap.isNull():
            self.coverLabel.setPixmap(pixmap.scaled(180, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            shown_cover = True
        if self.coverLabel is not None and not shown_cover:
            self.coverLabel.clear()
        self._set_visible(self.coverLabel, shown_cover)

        basics = [
            (self.pidLabel, "PID", "pid"),
            (self.brandLabel, "ブランド名", "brand"),
            (self.fileFormatLabel, "ファイル形式", "file_format"),
            (self.workFormatLabel, "作品形式", "work_format"),
        ]
        any_basic = False
        for label, key, text_key in basics:
            value = data.get(key)
            if value is None or label is None:
                self._set_visible(label, False)
                continue
            if isinstance(value, list):
                value = ", ".join(str(item) for item in value)
            label.setText(f"{self.get_text(text_key)}: {value}")
            self._set_visible(label, True)
            any_basic = True
        self._set_visible(self.basicFrame, any_basic)

        genres = str(data.get("genre一覧") or "").strip()
        self._set_visible(self.genreTitleLabel, bool(genres))
        if self.genreLabel is not None:
            self.genreLabel.setText(genres)
        self._set_visible(self.genreLabel, bool(genres))

        overview = re.sub(r"\n{2,}", "\n", str(data.get("概要") or "").strip())
        if len(overview) > 200:
            overview = overview[:200] + "..."
        self._set_visible(self.overviewTitleLabel, bool(overview))
        if self.overviewLabel is not None:
            self.overviewLabel.setText(overview)
        self._set_visible(self.overviewLabel, bool(overview))

    def _badge(self, label, text, styles):
        if label is None:
            return
        if not text:
            label.clear()
            label.setVisible(False)
            return
        label.setText(text)
        label.setStyleSheet(styles.get(text, "padding: 2px 4px; border-radius: 2px; font-weight: bold; font-size: 9px; background-color: #757575; color: white;"))
        label.setVisible(True)

    def _open_url(self):
        if self._url:
            QDesktopServices.openUrl(QUrl(self._url))
