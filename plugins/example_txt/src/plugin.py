"""EzCo 向けテキスト画像サンプル。

ホストは Class() のあと load(root, get_text, host) を渡す。

ホストが呼ぶ必須メソッド:
    get_file_count(path) -> int
    list_entries(path) -> [エントリ名, ...]
    read_entry(path, index) -> オブジェクト(name, data: bytes)

.txt / .log をアーカイブとして開き、折り返した本文を PNG ページにする。
サイドバーの変更は即時反映し、今のページの先頭文字から再分割する。
担当拡張子は manifest.formats と同じ並びの _SOURCE_SUFFIXES。
"""
import os
import threading

from layout import (
    HORIZONTAL,
    VERTICAL,
    PageSettings,
    layout_fits,
    page_index_for_start,
    paginate,
    paginate_anchored,
    read_text,
    render_page,
    resolve_settings,
)

_DEFAULTS = {
    "font_family": "",
    "font_size": 0,
    "text_color": "#222222",
    "bg_color": "#f7f2e8",
    "page_width": 900,
    "page_height": 1200,
    "margin": 48,
    "writing": HORIZONTAL,
    "charset": "utf-8",
}
_DEBOUNCE_MS = 150
_SOURCE_SUFFIXES = (".txt", ".log")


class TextImagePlugin:
    def __init__(self):
        self.root = None
        self.get_text = None
        self.host = None
        self.widget = None
        self._listening = False
        self._applying = False
        self._lock = threading.Lock()
        self._cache = {}
        self._fields = {}
        self._timer = None
        self._pending_keys = set()
        self._last_txt = None

    def load(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self.host.register_config_json("fields.json")

    def get_file_count(self, file_path):
        return len(self.list_entries(file_path))

    def list_entries(self, file_path):
        self._last_txt = str(file_path)
        pages = self._pages_for(file_path)
        if not pages:
            return ["page_001.png"]
        return [_page_name(index) for index in range(len(pages))]

    def read_entry(self, file_path, index):
        text, pages, settings = self._layout_for(file_path)
        if not pages:
            pages = [(0, 0)]
            text = text or ""
        index = max(0, min(int(index), len(pages) - 1))
        start, end = pages[index]
        return _Entry(_page_name(index), render_page(text, start, end, settings))

    def setup(self):
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QWidget

        if not _alive(self.widget):
            self.widget = QWidget()
            self._build_sidebar(self.widget)
            self._timer = QTimer(self.widget)
            self._timer.setSingleShot(True)
            self._timer.setInterval(_DEBOUNCE_MS)
            self._timer.timeout.connect(self._flush_pending)
        self._sync_ui_from_config()
        if not self._listening:
            self.host.on("config_changed", self._on_config)
            self._listening = True
        self.host.register_sidebar("text_image", "{title}", self.widget)

    def teardown(self):
        if self._timer is not None:
            self._timer.stop()
        self._listening = False
        self.widget = None
        self._fields = {}
        self._timer = None

    def _build_sidebar(self, widget):
        from PySide6.QtWidgets import (
            QComboBox,
            QFontComboBox,
            QFormLayout,
            QPushButton,
            QSpinBox,
        )

        layout = QFormLayout(widget)
        font_box = QFontComboBox()
        size = QSpinBox()
        size.setRange(8, 96)
        text_color = QPushButton()
        bg_color = QPushButton()
        width = QSpinBox()
        width.setRange(200, 4000)
        height = QSpinBox()
        height.setRange(200, 4000)
        margin = QSpinBox()
        margin.setRange(0, 400)
        writing = QComboBox()
        writing.addItem(self.get_text("writing_horizontal"), HORIZONTAL)
        writing.addItem(self.get_text("writing_vertical"), VERTICAL)

        layout.addRow(self.get_text("font_family"), font_box)
        layout.addRow(self.get_text("font_size"), size)
        layout.addRow(self.get_text("text_color"), text_color)
        layout.addRow(self.get_text("bg_color"), bg_color)
        layout.addRow(self.get_text("page_width"), width)
        layout.addRow(self.get_text("page_height"), height)
        layout.addRow(self.get_text("margin"), margin)
        layout.addRow(self.get_text("writing"), writing)
        refresh = QPushButton(self.get_text("refresh"))
        layout.addRow(refresh)

        self._fields = {
            "font_family": font_box,
            "font_size": size,
            "text_color": text_color,
            "bg_color": bg_color,
            "page_width": width,
            "page_height": height,
            "margin": margin,
            "writing": writing,
            "refresh": refresh,
        }

        font_box.currentFontChanged.connect(lambda _font: self._apply_keys(("font_family",)))
        size.valueChanged.connect(lambda _value: self._queue_keys(("font_size",)))
        text_color.clicked.connect(lambda: self._pick_color("text_color"))
        bg_color.clicked.connect(lambda: self._pick_color("bg_color"))
        width.valueChanged.connect(lambda _value: self._queue_keys(("page_width",)))
        height.valueChanged.connect(lambda _value: self._queue_keys(("page_height",)))
        margin.valueChanged.connect(lambda _value: self._queue_keys(("margin",)))
        writing.currentIndexChanged.connect(lambda _index: self._apply_keys(("writing",)))
        refresh.clicked.connect(self._refresh_clicked)

    def _sync_ui_from_config(self):
        if not self._fields:
            return
        raw = self._raw_settings()
        resolved = self._resolved(raw)
        self._applying = True
        try:
            font_box = self._fields["font_family"]
            font_box.blockSignals(True)
            font_box.setCurrentFont(_qfont(resolved.font_family, resolved.font_size))
            font_box.blockSignals(False)
            for key, value in (
                ("font_size", resolved.font_size),
                ("page_width", resolved.page_width),
                ("page_height", resolved.page_height),
                ("margin", resolved.margin),
            ):
                box = self._fields[key]
                box.blockSignals(True)
                box.setValue(value)
                box.blockSignals(False)
            self._paint_color_button(self._fields["text_color"], resolved.text_color)
            self._paint_color_button(self._fields["bg_color"], resolved.bg_color)
            writing = self._fields["writing"]
            writing.blockSignals(True)
            index = writing.findData(resolved.writing)
            writing.setCurrentIndex(max(0, index))
            writing.blockSignals(False)
        finally:
            self._applying = False

    def _read_ui(self) -> PageSettings:
        fields = self._fields
        writing = fields["writing"].currentData()
        return PageSettings(
            font_family=fields["font_family"].currentFont().family(),
            font_size=int(fields["font_size"].value()),
            text_color=_button_color(fields["text_color"], _DEFAULTS["text_color"]),
            bg_color=_button_color(fields["bg_color"], _DEFAULTS["bg_color"]),
            page_width=int(fields["page_width"].value()),
            page_height=int(fields["page_height"].value()),
            margin=int(fields["margin"].value()),
            writing=VERTICAL if writing == VERTICAL else HORIZONTAL,
        )

    def _queue_keys(self, keys):
        if self._applying:
            return
        self._pending_keys.update(keys)
        if self._timer is not None:
            self._timer.start()

    def _flush_pending(self):
        keys = tuple(self._pending_keys)
        self._pending_keys.clear()
        if keys:
            self._apply_keys(keys)

    def _apply_keys(self, keys):
        if self._applying or not self._fields:
            return
        if self._timer is not None:
            self._timer.stop()
            self._pending_keys.difference_update(keys)
        raw = self._read_ui()
        resolved = self._resolved(raw)
        if not layout_fits(resolved):
            self._sync_ui_from_config()
            return
        snapshot = {
            "font_family": raw.font_family,
            "font_size": raw.font_size,
            "text_color": raw.text_color,
            "bg_color": raw.bg_color,
            "page_width": raw.page_width,
            "page_height": raw.page_height,
            "margin": raw.margin,
            "writing": raw.writing,
        }
        self._applying = True
        try:
            for key in keys:
                self.host.set_config(key, snapshot[key])
        finally:
            self._applying = False
        self._reload_from_anchor()

    def _refresh_clicked(self):
        self._apply_keys(tuple(key for key in _DEFAULTS if key != "charset"))

    def _pick_color(self, key):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog

        current = _button_color(self._fields[key], _DEFAULTS[key])
        color = QColorDialog.getColor(QColor(current), self.widget)
        if not color.isValid():
            return
        self._paint_color_button(self._fields[key], color.name())
        self._apply_keys((key,))

    def _on_config(self, _payload=None):
        if self._applying:
            return
        self._sync_ui_from_config()
        self._reload_from_anchor()

    def _reload_from_anchor(self):
        path = self._current_txt_path()
        if not path:
            return
        try:
            text = read_text(path, self._charset())
        except OSError as exc:
            self.host.report_error("read_text", exc)
            return
        page = self.host.get_current("page")
        try:
            page_index = max(0, int(page) - 1)
        except (TypeError, ValueError):
            page_index = 0
        old_pages = None
        with self._lock:
            cached = self._cache.get(_norm(path))
            if cached is not None:
                old_pages = cached.get("pages")
        if old_pages and 0 <= page_index < len(old_pages):
            anchor = old_pages[page_index][0]
        else:
            anchor = 0
        settings = self._resolved(self._raw_settings())
        pages = paginate_anchored(text, settings, anchor)
        if not pages:
            self._sync_ui_from_config()
            return
        new_page = page_index_for_start(pages, anchor) + 1
        with self._lock:
            self._cache[_norm(path)] = {
                "mtime": _mtime(path),
                "settings": settings,
                "charset": self._charset(),
                "text": text,
                "pages": pages,
            }
        self.host.reload_current(new_page)

    def _current_txt_path(self):
        parsed = _txt_path(self.host.get_current("path"))
        if parsed:
            self._last_txt = parsed
            return parsed
        last = self._last_txt
        if not last:
            return None
        current = str(self.host.get_current("path") or "").replace("\\", "/")
        name = os.path.basename(last)
        if name and name.replace("\\", "/") in current:
            return last
        return None

    def _charset(self) -> str:
        return str(self.host.get_config("charset", _DEFAULTS["charset"]) or "utf-8")

    def _raw_settings(self) -> PageSettings:
        return PageSettings(
            font_family=str(self.host.get_config("font_family", _DEFAULTS["font_family"]) or ""),
            font_size=int(self.host.get_config("font_size", _DEFAULTS["font_size"]) or 0),
            text_color=str(self.host.get_config("text_color", _DEFAULTS["text_color"]) or _DEFAULTS["text_color"]),
            bg_color=str(self.host.get_config("bg_color", _DEFAULTS["bg_color"]) or _DEFAULTS["bg_color"]),
            page_width=int(self.host.get_config("page_width", _DEFAULTS["page_width"])),
            page_height=int(self.host.get_config("page_height", _DEFAULTS["page_height"])),
            margin=int(self.host.get_config("margin", _DEFAULTS["margin"])),
            writing=str(self.host.get_config("writing", _DEFAULTS["writing"]) or HORIZONTAL),
        )

    def _app_font(self):
        ui = {}
        try:
            ui = dict(self.host.get_app_config().get("ui_font") or {})
        except Exception:
            ui = {}
        family = str(ui.get("font_family") or "")
        try:
            size = int(ui.get("font_size") or 0)
        except (TypeError, ValueError):
            size = 0
        return family, size

    def _resolved(self, raw: PageSettings) -> PageSettings:
        family, size = self._app_font()
        return resolve_settings(raw, family, size)

    def _pages_for(self, file_path):
        _text, pages, _settings = self._layout_for(file_path)
        return pages

    def _layout_for(self, file_path):
        path = str(file_path)
        key = _norm(path)
        mtime = _mtime(path)
        settings = self._resolved(self._raw_settings())
        charset = self._charset()
        with self._lock:
            cached = self._cache.get(key)
            if (
                cached
                and cached.get("mtime") == mtime
                and cached.get("settings") == settings
                and cached.get("charset") == charset
            ):
                return cached["text"], cached["pages"], cached["settings"]
        try:
            text = read_text(path, charset)
        except OSError as exc:
            self.host.report_error("read_text", exc)
            return "", [(0, 0)], settings
        pages = paginate(text, settings)
        if pages is None:
            pages = [(0, len(text))]
        with self._lock:
            self._cache[key] = {
                "mtime": mtime,
                "settings": settings,
                "charset": charset,
                "text": text,
                "pages": pages,
            }
        return text, pages, settings

    def _paint_color_button(self, button, color: str):
        button.setProperty("color_value", color)
        button.setText(color)
        fg = "#111111" if _is_light(color) else "#f5f5f5"
        button.setStyleSheet(
            f"background-color: {color}; color: {fg}; min-width: 72px; min-height: 22px;"
        )


class _Entry:
    def __init__(self, name, data):
        self.name = name
        self.data = data


def _page_name(index: int) -> str:
    return f"page_{index + 1:03d}.png"


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(str(path)))


def _mtime(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return -1


def _has_source_suffix(name: str, suffixes=_SOURCE_SUFFIXES) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(suffix) for suffix in suffixes)


def _txt_path(raw, suffixes=_SOURCE_SUFFIXES) -> str | None:
    if not raw:
        return None
    value = str(raw)
    if "|" in value:
        left = value.split("|", 1)[0].replace("\\", "/")
        for prefix in ("archive://", "archive:/", "archive:"):
            if left.lower().startswith(prefix):
                left = left[len(prefix):]
                break
        if len(left) >= 3 and left[0] == "/" and left[2] == ":":
            left = left[1:]
        if _has_source_suffix(left, suffixes):
            return left.replace("/", os.sep)
    if _has_source_suffix(value, suffixes):
        return value
    return None


def _qfont(family: str, size: int):
    from PySide6.QtGui import QFont

    return QFont(family, max(1, int(size or 18)))


def _button_color(button, fallback: str) -> str:
    value = button.property("color_value")
    if value:
        return str(value)
    return fallback


def _is_light(color: str) -> bool:
    value = (color or "").lstrip("#")
    if len(value) != 6:
        return True
    try:
        red = int(value[0:2], 16)
        green = int(value[2:4], 16)
        blue = int(value[4:6], 16)
    except ValueError:
        return True
    return (red * 299 + green * 587 + blue * 114) >= 140000


def _alive(widget):
    if widget is None:
        return False
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False
