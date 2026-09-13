"""ホストの設定種別を全部登録して、保存値をサイドバーに出す確認用。"""
from datetime import datetime, timezone

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

_DATE_DEFAULT = 1789344000  # 2026-09-14 00:00:00 UTC
_DATETIME_DEFAULT = 1789387200  # 2026-09-14 12:00:00 UTC

_FIELDS = (
    ("flag", "bool", True, None),
    ("label", "string", "sample", None),
    ("count", "int", 3, None),
    ("ratio", "float", 1.25, None),
    ("tint", "color", "#3366cc", None),
    ("day", "date", _DATE_DEFAULT, None),
    ("moment", "datetime", _DATETIME_DEFAULT, None),
    ("mode", "choice", "plain", (("plain", "mode_plain"), ("bold", "mode_bold"))),
    ("face", "font", "Segoe UI", None),
)


class ConfigTypesPlugin:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self.widget = None
        self._values = {}
        self._raw = {}
        self._listening = False
        for key, value_type, default, choices in _FIELDS:
            kwargs = {}
            if choices:
                kwargs["choices"] = [
                    (value, self.get_text(label_key)) for value, label_key in choices
                ]
            self.host.register_config(
                key,
                value_type,
                default,
                label=self.get_text(key),
                description=self.get_text(f"{key}_help"),
                **kwargs,
            )

    def setup(self):
        if self.widget is None:
            self.widget = QWidget()
            layout = QFormLayout(self.widget)
            for key, _value_type, _default, _choices in _FIELDS:
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
        self.host.register_sidebar("config_types", self.get_text("title"), self.widget)

    def teardown(self):
        if self._listening:
            self.host.off("config_changed", self._on_config)
            self._listening = False
        self.host.unregister_sidebar("config_types")
        self.widget = None
        self._values = {}
        self._raw = {}

    def _on_config(self, _payload=None):
        self._refresh()

    def _refresh(self):
        for key, value_type, default, _choices in _FIELDS:
            value = self.host.get_config(key, default)
            label = self._values.get(key)
            raw = self._raw.get(key)
            if label is None or raw is None:
                continue
            label.setText(_display(value_type, value))
            raw.setText(repr(value))
            if value_type == "color":
                label.setStyleSheet(
                    f"background-color: {value}; color: {_contrast(value)}; padding: 2px 6px;"
                )
            else:
                label.setStyleSheet("")


def _display(value_type: str, value) -> str:
    if value_type == "date":
        return _utc(value, "%Y-%m-%d")
    if value_type == "datetime":
        return _utc(value, "%Y-%m-%d %H:%M:%S UTC")
    return str(value)


def _utc(value, fmt: str) -> str:
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
