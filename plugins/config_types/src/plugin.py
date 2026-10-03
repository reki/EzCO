"""ホストの設定種別を全部登録して、保存値をサイドバーに出す確認用。"""
from datetime import datetime, timezone
from enum import Enum

from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

# パスワード型の設定キー。
_PASSWORD_KEYS = ("secret", "secret_multi")
# 色型の設定キー。
_COLOR_KEYS = ("tint", "tint_multi")
# 日付型の設定キー。
_DATE_KEYS = ("day", "day_multi")
# 日時型の設定キー。
_DATETIME_KEYS = ("moment", "moment_multi")


class Style(Enum):
    """確認用の choice に使う書式。"""

    # 通常の書式。
    PLAIN = "plain"
    # 太字の書式。
    BOLD = "bold"


class ConfigTypesPlugin:
    """全設定種別の保存値をサイドバーに出す。"""

    def __init__(self):
        """root、get_text、host と、表示ラベルの入れ物を空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None
        self.widget = None
        self._values = {}
        self._raw = {}
        self._listening = False
        self._keys = []

    def load(self, root, get_text, host):
        """設定 JSON と Enum の choice を登録し、表示するキーを並べる。

        Args:
            root: プラグインルート。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
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
        """値と保存形のラベルを作り、変更を購読してサイドバーを登録する。"""
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
        """ウィジェットと表示ラベルを捨て、購読フラグを下ろす。"""
        self._listening = False
        self.widget = None
        self._values = {}
        self._raw = {}

    def _on_config(self, _payload=None):
        """表示を読み直す。

        Args:
            _payload: config_changed の内容。表示の更新には使わない。
        """
        self._refresh()

    def _refresh(self):
        """各キーの表示と repr を更新し、パスワードは伏せ、単色は背景色にする。"""
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
    """値を画面用の文字列にする。

    Args:
        key: 設定キー。日付系のとき書式を選ぶ。
        value: 表示する値。列なら要素を繋ぐ。

    Returns:
        画面用の文字列。Enum は名前。
    """
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
    """UNIX 秒を UTC の書式にする。

    Args:
        value: UNIX 秒。
        fmt: strftime の書式。

    Returns:
        UTC の文字列。整数にできなければそのまま文字列。
    """
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        # 秒にできなければそのまま文字列にする。
        return str(value)
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(fmt)


def _contrast(color: str) -> str:
    """背景色に対する文字色を返す。

    Args:
        color: #rrggbb。

    Returns:
        明るい背景なら暗い文字色、暗い背景なら明るい文字色。
    """
    text = (color or "").lstrip("#")
    if len(text) != 6:
        return "#111111"
    try:
        red = int(text[0:2], 16)
        green = int(text[2:4], 16)
        blue = int(text[4:6], 16)
    except ValueError:
        # 色コードを解釈できなければ暗い文字色を返す。
        return "#111111"
    if (red * 299 + green * 587 + blue * 114) >= 140000:
        return "#111111"
    return "#f5f5f5"
