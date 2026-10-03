"""登録済み config からサイドバー用フォームを組み立てる。"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ez_co.plugins.host import coerce_field_value, is_config_empty
from ez_co.ui.plugins.config_widgets import (
    NUMERIC_TYPES,
    SYNC_RELOAD_IDLE_MS,
    SuffixRow,
    config_field_display_name,
    connect_value_changed,
    make_value_widget,
    read_value,
    set_widget_value,
)
from ez_co.utils.language_manager import get_text


class PluginConfigForm(QWidget):
    """プラグインの登録済み設定をサイドバー用フォームにする。"""

    def __init__(self, host, plugin_id: str, parent=None):
        """ホストとプラグイン ID から項目と、数値保存の遅延を用意する。

        Args:
            host: 設定の読み書きに使うホスト。
            plugin_id: 対象プラグイン。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._host = host
        self._plugin_id = plugin_id
        self._scoped = host.scoped(plugin_id)
        self._fields = list(host.configs_for(plugin_id))
        self._widgets = {}
        self._labels = {}
        self._reset_button = None
        self._applying = False
        self._dirty = set()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SYNC_RELOAD_IDLE_MS)
        self._timer.timeout.connect(self._flush)
        self._setup_ui()
        self._scoped.on("config_changed", self._on_config)

    def refresh_labels(self) -> None:
        """項目名、説明、接尾辞、リセットボタンの文言を現在の言語で出し直す。"""
        for field in self._fields:
            label = self._labels.get(field.key)
            if label is not None:
                label.setText(config_field_display_name(field, expand=self._expand))
            widget = self._widgets.get(field.key)
            if widget is not None and field.description:
                widget.setToolTip(self._expand(field.description))
            if isinstance(widget, SuffixRow) and field.suffix:
                widget.set_suffix(self._expand(field.suffix))
        if self._reset_button is not None:
            self._reset_button.setText(get_text("ui.reset"))

    def _expand(self, value) -> str:
        """表示文のプレースホルダを展開する。

        Args:
            value: 展開する文。

        Returns:
            展開した文字列。
        """
        return self._scoped.expand_text(value)

    def _setup_ui(self):
        """各設定の入力とリセットボタンを配置する。"""
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        form = QFormLayout(body)
        form.setContentsMargins(0, 0, 0, 0)
        scoped = self._scoped
        for field in self._fields:
            current = scoped.get_config(field.key, field.default)
            widget = make_value_widget(field, current, expand=self._expand)
            if field.description:
                widget.setToolTip(self._expand(field.description))
            label = QLabel(config_field_display_name(field, expand=self._expand))
            form.addRow(label, widget)
            self._widgets[field.key] = widget
            self._labels[field.key] = label
            connect_value_changed(widget, lambda key=field.key: self._on_edited(key))
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        reset = QPushButton(get_text("ui.reset"))
        reset.clicked.connect(self._reset_to_defaults)
        self._reset_button = reset
        outer.addWidget(reset, 0)

    def _on_edited(self, key: str):
        """編集を保存する。数値は間隔を空け、それ以外はすぐ書く。

        Args:
            key: 編集された項目のキー。
        """
        if self._applying:
            return
        field = self._field_for(key)
        if field is None:
            return
        if field.value_type in NUMERIC_TYPES:
            self._dirty.add(key)
            self._timer.start()
            return
        self._write_keys((key,))

    def _flush(self):
        """溜まっている数値項目を保存する。"""
        keys = tuple(self._dirty)
        self._dirty.clear()
        if keys:
            self._write_keys(keys)

    def _write_keys(self, keys):
        """指定キーを読み取り、必須が空なら戻して書かない。reload の項目があれば現在を読み直す。

        Args:
            keys: 書く項目のキー。
        """
        if self._timer.isActive():
            pending = tuple(self._dirty)
            self._timer.stop()
            self._dirty.clear()
            keys = tuple(dict.fromkeys((*keys, *pending)))
        scoped = self._scoped
        written = []
        for key in keys:
            field = self._field_for(key)
            if field is None:
                continue
            value = read_value(field, self._widgets[field.key])
            if field.required and is_config_empty(field, value):
                self._restore_widget(field)
                continue
            self._applying = True
            try:
                if scoped.set_config(field.key, value):
                    written.append(field)
            finally:
                self._applying = False
        if any(field.reload for field in written):
            self._host.reload_current()

    def _on_config(self, payload=None):
        """外からの設定変更をウィジェットへ反映する。自分が書いている最中は無視する。

        Args:
            payload: 変わったキーを持つ辞書。無ければ全項目。
        """
        if self._applying:
            return
        key = payload.get("key") if isinstance(payload, dict) else None
        fields = self._fields
        if key:
            field = self._field_for(key)
            fields = [field] if field is not None else []
        self._applying = True
        try:
            for field in fields:
                widget = self._widgets.get(field.key)
                if widget is None:
                    continue
                value = self._scoped.get_config(field.key, field.default)
                set_widget_value(field, widget, value)
        finally:
            self._applying = False

    def _reset_to_defaults(self):
        """確認のあと、各項目を既定値に戻す。"""
        reply = QMessageBox.question(
            self,
            get_text("ui.reset"),
            get_text("ui.plugin_config_sidebar_reset_confirm"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._timer.stop()
        self._dirty.clear()
        scoped = self._scoped
        written = []
        self._applying = True
        try:
            for field in self._fields:
                value = coerce_field_value(field, field.default)
                set_widget_value(field, self._widgets[field.key], value)
                if scoped.reset_config(field.key):
                    written.append(field)
        finally:
            self._applying = False
        if any(field.reload for field in written):
            self._host.reload_current()

    def _restore_widget(self, field):
        """ウィジェットを保存されている値に戻す。

        Args:
            field: 戻す項目。
        """
        widget = self._widgets.get(field.key)
        if widget is None:
            return
        was = self._applying
        self._applying = True
        try:
            set_widget_value(field, widget, self._scoped.get_config(field.key, field.default))
        finally:
            self._applying = was

    def _field_for(self, key: str):
        """キーに対応する項目を返す。

        Args:
            key: 項目のキー。

        Returns:
            見つかった項目。無ければ None。
        """
        for field in self._fields:
            if field.key == key:
                return field
        return None
