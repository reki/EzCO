"""ホストの設定種別を全部登録して、保存値をサイドバーに出す確認用。"""
from datetime import datetime, timezone
from enum import Enum

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

_DATE_DEFAULT = 1789344000  # 2026-09-14 00:00:00 UTC
_DATETIME_DEFAULT = 1789387200  # 2026-09-14 12:00:00 UTC


class Style(Enum):
    PLAIN = "plain"
    BOLD = "bold"


_SINGLE = (
    ("flag", "bool", True, None, None),
    ("label", "string", "sample", None, None),
    ("count", "int", 3, None, {"suffix": "px"}),
    ("ratio", "float", 1.25, None, {"suffix": "%"}),
    ("strength", "int_range", 50, None, {"minimum": 0, "maximum": 100, "step": 1, "sync": True, "suffix": "px"}),
    ("gamma", "float_range", 1.0, None, {"minimum": 0.2, "maximum": 3.0, "step": 0.05, "sync": True, "suffix": "%"}),
    ("lut", "path", "", None, {"path_kind": "file"}),
    ("secret", "password", "", None, None),
    ("tint", "color", "#3366cc", None, None),
    ("day", "date", _DATE_DEFAULT, None, None),
    ("moment", "datetime", _DATETIME_DEFAULT, None, None),
    ("mode", "choice", "plain", (("plain", "mode_plain"), ("bold", "mode_bold")), None),
    ("style", "choice", Style.PLAIN, None, {"enum": True}),
    ("face", "font", "Segoe UI", None, None),
    ("charset", "charset", "utf-8", None, None),
    ("language", "language", "ja", None, None),
    ("country", "country", "JP", None, None),
)

_REQUIRED = (
    ("need_text", "string", "", None, {"required": True}),
    ("need_texts", "string", [], None, {"required": True, "multiple": True}),
)


class ConfigTypesPlugin:
    def __init__(self):
        self.root = None
        self.get_text = None
        self.host = None
        self.widget = None
        self._values = {}
        self._raw = {}
        self._listening = False
        self._rows = []

    def load(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self._rows = []
        for spec in _SINGLE:
            self._rows.append(self._register(spec[0], *spec[1:], multiple=False))
        for spec in _SINGLE:
            self._rows.append(self._register(f"{spec[0]}_multi", *spec[1:], multiple=True))
        for spec in _REQUIRED:
            extra = dict(spec[4] or {})
            self._rows.append(
                self._register(
                    spec[0],
                    spec[1],
                    spec[2],
                    spec[3],
                    extra,
                    multiple=bool(extra.get("multiple")),
                )
            )

    def _register(self, field_key, value_type, default, choices, extra, multiple):
        kwargs = dict(extra or {})
        use_enum = bool(kwargs.pop("enum", False))
        field_default = default
        if multiple:
            kwargs["multiple"] = True
            if not isinstance(field_default, list):
                field_default = [] if field_default is None else [field_default]
        if use_enum:
            kwargs["choices"] = [
                (Style.PLAIN, self.get_text("style_plain")),
                (Style.BOLD, self.get_text("style_bold")),
            ]
            field_default = [Style.PLAIN] if multiple else Style.PLAIN
        elif choices:
            kwargs["choices"] = [
                (value, self.get_text(label_key)) for value, label_key in choices
            ]
        self.host.register_config(
            field_key,
            value_type,
            field_default,
            label=self.get_text(field_key),
            description=self.get_text(f"{_base_key(field_key)}_help"),
            **kwargs,
        )
        return field_key, value_type, field_default

    def setup(self):
        if self.widget is None:
            self.widget = QWidget()
            layout = QFormLayout(self.widget)
            for key, _value_type, _default in self._rows:
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
        self._listening = False
        self.widget = None
        self._values = {}
        self._raw = {}

    def _on_config(self, _payload=None):
        self._refresh()

    def _refresh(self):
        for key, value_type, default in self._rows:
            value = self.host.get_config(key, default)
            label = self._values.get(key)
            raw = self._raw.get(key)
            if label is None or raw is None:
                continue
            if value_type == "password":
                shown = "••••••••" if value else ""
                label.setText(shown)
                raw.setText(shown)
                label.setStyleSheet("")
                continue
            label.setText(_display(value_type, value))
            raw.setText(repr(value))
            if value_type == "color" and not isinstance(value, list):
                label.setStyleSheet(
                    f"background-color: {value}; color: {_contrast(value)}; padding: 2px 6px;"
                )
            else:
                label.setStyleSheet("")


def _base_key(field_key: str) -> str:
    if field_key.endswith("_multi"):
        return field_key[: -len("_multi")]
    return field_key


def _display(value_type: str, value) -> str:
    if isinstance(value, list):
        return ", ".join(_display(value_type, item) for item in value)
    if isinstance(value, Enum):
        return value.name
    if value_type == "date":
        return _utc(value, "%Y-%m-%d")
    if value_type == "datetime":
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
