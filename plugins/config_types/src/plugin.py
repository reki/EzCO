"""ホストの設定種別を全部登録して、保存値をサイドバーに出す確認用。"""
from datetime import datetime, timezone
from enum import Enum

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

_PASSWORD_KEYS = ("secret", "secret_multi")
_COLOR_KEYS = ("tint", "tint_multi")
_DATE_KEYS = ("day", "day_multi")
_DATETIME_KEYS = ("moment", "moment_multi")


class Style(Enum):
    PLAIN = "plain"
    BOLD = "bold"


class ConfigTypesPlugin:
    def __init__(self):
        self.root = None
        self.get_text = None
        self.host = None
        self.widget = None
        self._values = {}
        self._raw = {}
        self._listening = False
        self._keys = []

    def load(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self.host.register_config_json("fields.json")
        self.host.register_config(
            "style",
            "choice",
            Style.PLAIN,
            label="{style}",
            description="{style_help}",
            choices=[(Style.PLAIN, "{style_plain}"), (Style.BOLD, "{style_bold}")],
        )
        self.host.register_config(
            "style_multi",
            "choice",
            [],
            label="{style_multi}",
            description="{style_help}",
            choices=[(Style.PLAIN, "{style_plain}"), (Style.BOLD, "{style_bold}")],
            multiple=True,
        )
        self._keys = [
            "flag",
            "label",
            "count",
            "ratio",
            "strength",
            "gamma",
            "lut",
            "secret",
            "tint",
            "day",
            "moment",
            "mode",
            "face",
            "charset",
            "language",
            "country",
            "flag_multi",
            "label_multi",
            "count_multi",
            "ratio_multi",
            "strength_multi",
            "gamma_multi",
            "lut_multi",
            "secret_multi",
            "tint_multi",
            "day_multi",
            "moment_multi",
            "mode_multi",
            "face_multi",
            "charset_multi",
            "language_multi",
            "country_multi",
            "need_text",
            "need_texts",
            "style",
            "style_multi",
        ]

    def setup(self):
        if self.widget is None:
            self.widget = QWidget()
            layout = QFormLayout(self.widget)
            for key in self._keys:
                value_label = QLabel()
                value_label.setWordWrap(True)
                raw_label = QLabel()
                raw_label.setWordWrap(True)
                raw_label.setStyleSheet("color: #666666; font-size: 11px;")
                self._values[key] = value_label
                self._raw[key] = raw_label
                layout.addRow(self.get_text(key), value_label)
                layout.addRow(self.get_text("stored"), raw_label)
        if not self._listening:
            self.host.on("config_changed", self._on_config)
            self._listening = True
        self._refresh()
        self.host.register_sidebar("config_types", "{title}", self.widget)

    def teardown(self):
        self._listening = False
        self.widget = None
        self._values = {}
        self._raw = {}

    def _on_config(self, _payload=None):
        self._refresh()

    def _refresh(self):
        for key in self._keys:
            value = self.host.get_config(key)
            label = self._values.get(key)
            raw = self._raw.get(key)
            if label is None or raw is None:
                continue
            if key in _PASSWORD_KEYS:
                shown = "••••••••" if value else ""
                label.setText(shown)
                raw.setText(shown)
                label.setStyleSheet("")
                continue
            label.setText(_display(key, value))
            raw.setText(repr(value))
            if key in _COLOR_KEYS and not isinstance(value, list):
                label.setStyleSheet(
                    f"background-color: {value}; color: {_contrast(value)}; padding: 2px 6px;"
                )
            else:
                label.setStyleSheet("")


def _display(key, value) -> str:
    if isinstance(value, list):
        return ", ".join(_display(key, item) for item in value)
    if isinstance(value, Enum):
        return value.name
    if key in _DATE_KEYS:
        return _utc(value, "%Y-%m-%d")
    if key in _DATETIME_KEYS:
        return _utc(value, "%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def _utc(value, fmt) -> str:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        return str(value)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(fmt)


def _contrast(color: str) -> str:
    text = (color or "").lstrip("#")
    if len(text) != 6:
        return "#111111"
    try:
        red = int(text[0:2], 16)
        green = int(text[2:4], 16)
        blue = int(text[4:6], 16)
    except ValueError:
        return "#111111"
    if (red * 299 + green * 587 + blue * 114) >= 140000:
        return "#111111"
    return "#f5f5f5"
