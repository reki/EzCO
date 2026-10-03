"""プラグインが登録したスキーマから設定ダイアログを作る。"""
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ez_co.plugins.host import (
    coerce_field_value,
    config_field_syncs,
    config_should_reload,
    is_config_empty,
)
from ez_co.ui.plugins.config_widgets import (
    ChoiceMultiList,
    FilterCombo,
    MultiRows,
    PathRow,
    RangeRow,
    SYNC_RELOAD_IDLE_MS,
    SuffixRow,
    config_field_display_name,
    make_value_widget,
    read_value,
    set_widget_value,
)
from ez_co.utils.language_manager import get_text

# 必須が欠けた入力へ付ける赤い枠。
_INVALID_STYLE = "border: 1px solid #c62828;"


class PluginConfigDialog(QDialog):
    """プラグインの設定を表で編集し、即時保存と必須の不足を扱う。"""

    def __init__(self, host, plugin_id: str, plugin_name: str = "", parent=None):
        """項目と現在値の表を作り、開いたときの値を控える。

        Args:
            host: 設定の読み書きに使うホスト。
            plugin_id: 対象プラグイン。
            plugin_name: タイトルに出す名前。空なら ID。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._host = host
        self._plugin_id = plugin_id
        self._scoped = host.scoped(plugin_id)
        self._fields = list(host.configs_for(plugin_id))
        self._widgets = {}
        self._name_items = {}
        self._snapshot = {}
        self._dirty_sync = set()
        self._previewed_sync = set()
        self._reset_keys = set()
        self._resetting = False
        self._sync_timer = QTimer(self)
        self._sync_timer.setSingleShot(True)
        self._sync_timer.setInterval(SYNC_RELOAD_IDLE_MS)
        self._sync_timer.timeout.connect(self._flush_sync)
        title = plugin_name or plugin_id
        self.setWindowTitle(get_text("ui.plugin_config_title").format(name=title))
        self.setMinimumSize(520, 280)
        self.resize(720, 360)
        self._setup_ui()
        self._capture_snapshot()
        self._refresh_required()

    def _expand(self, value) -> str:
        """表示文を展開する。

        Args:
            value: 展開する文。

        Returns:
            展開した文字列。
        """
        return self._scoped.expand_text(value)

    def _setup_ui(self):
        """項目名と値の表を配置し、即時保存する入力をつなぐ。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        table = QTableWidget(0, 2)
        self._table = table
        table.setHorizontalHeaderLabels([
            get_text("ui.plugin_config_item"),
            get_text("ui.plugin_config_value"),
        ])
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setMinimumSectionSize(48)
        has_range = any(field.value_type in ("int_range", "float_range") for field in self._fields)
        table.setColumnWidth(1, 280 if has_range else 200)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(False)
        table.verticalHeader().setMinimumSectionSize(36 if has_range else 32)
        scoped = self._scoped
        table.setRowCount(len(self._fields))
        for index, field in enumerate(self._fields):
            label = config_field_display_name(field, expand=self._expand)
            current = scoped.get_config(field.key, field.default)
            name_item = QTableWidgetItem(label)
            table.setItem(index, 0, name_item)
            self._name_items[field.key] = name_item
            widget = make_value_widget(field, current, expand=self._expand)
            if field.value_type == "bool" and not field.multiple:
                table.setCellWidget(index, 1, self._center_widget(widget))
            else:
                table.setCellWidget(index, 1, widget)
            self._widgets[field.key] = widget
            self._connect_sync(field, widget)
            self._connect_required(field, widget)
        table.resizeRowsToContents()
        layout.addWidget(table)
        buttons = QHBoxLayout()
        buttons.addStretch()
        reset_button = QPushButton(get_text("ui.reset"))
        reset_button.clicked.connect(self._reset_to_defaults)
        self._apply_button = QPushButton(get_text("ui.apply"))
        self._apply_button.clicked.connect(self._save)
        self._ok_button = QPushButton(get_text("ui.ok"))
        self._ok_button.clicked.connect(self._apply_and_accept)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(reset_button)
        buttons.addWidget(self._apply_button)
        buttons.addWidget(self._ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _connect_sync(self, field, widget):
        """即時保存の項目なら、値の変化で保存を予約する。

        Args:
            field: つなぐ項目。
            widget: つなぐ入力。
        """
        if not config_field_syncs(field):
            return
        if isinstance(widget, (MultiRows, SuffixRow, RangeRow)):
            widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))
            return
        widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))

    def _connect_required(self, field, widget):
        """必須の不足を見るために入力を監視する。

        Args:
            field: 監視する項目。
            widget: 監視する入力。
        """
        self._watch_widget(widget)

    def _watch_widget(self, widget):
        """入力の変化で必須表示を更新する。接尾辞付きは中の入力を見る。

        Args:
            widget: 監視する入力。
        """
        if isinstance(widget, MultiRows):
            widget.rowsChanged.connect(self._refresh_required)
            return
        if isinstance(widget, ChoiceMultiList):
            widget.changed.connect(self._refresh_required)
            return
        if isinstance(widget, SuffixRow):
            self._watch_widget(widget.editor)
            return
        if isinstance(widget, PathRow):
            widget._edit.textChanged.connect(lambda _=None: self._refresh_required())
            widget._edit.editingFinished.connect(self._refresh_required)
            return
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _=None: self._refresh_required())
            widget.editingFinished.connect(self._refresh_required)
            return
        if isinstance(widget, (QComboBox, FilterCombo)):
            widget.currentIndexChanged.connect(lambda _=None: self._refresh_required())
            widget.editTextChanged.connect(lambda _=None: self._refresh_required())
            return
        if isinstance(widget, (QSpinBox, QDoubleSpinBox, QDateEdit, QDateTimeEdit, QFontComboBox)):
            if hasattr(widget, "editingFinished"):
                widget.editingFinished.connect(self._refresh_required)
            return
        if isinstance(widget, QCheckBox):
            widget.toggled.connect(lambda _=None: self._refresh_required())

    def _on_sync_changed(self, key: str):
        """リセット中でなければ、その項目の即時保存を予約する。

        Args:
            key: 変わった項目のキー。
        """
        if self._resetting:
            return
        self._reset_keys.discard(key)
        self._dirty_sync.add(key)
        self._sync_timer.start()

    def _flush_sync(self) -> bool:
        """予約された即時保存を書く。必須が空の項目は書かない。

        Returns:
            書いたとき True。予約が無ければ False。
        """
        if not self._dirty_sync:
            return False
        scoped = self._host.scoped(self._plugin_id)
        keys = list(self._dirty_sync)
        self._dirty_sync.clear()
        written = []
        for key in keys:
            field = self._field_for(key)
            if field is None:
                continue
            value = read_value(field, self._widgets[field.key])
            if field.required and is_config_empty(field, value):
                continue
            scoped.set_config(field.key, value)
            self._previewed_sync.add(field.key)
            written.append(field)
        self._reload_if_needed(written)
        return True

    def _field_for(self, key: str):
        """キーの項目を返す。

        Args:
            key: 項目のキー。

        Returns:
            見つかった項目。無ければ None。
        """
        for field in self._fields:
            if field.key == key:
                return field
        return None

    def _capture_snapshot(self):
        """いまの入力を、戻すための値として控える。"""
        self._snapshot = {
            field.key: read_value(field, self._widgets[field.key])
            for field in self._fields
        }
        self._reset_keys.clear()

    def _center_widget(self, widget):
        """入力を中央に置く入れ物を返す。

        Args:
            widget: 中央に置く入力。

        Returns:
            その入れ物。
        """
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder_layout.addWidget(widget)
        return holder

    def _missing_required(self):
        """必須なのに空で、リセット対象でない項目を返す。

        Returns:
            足りない項目。
        """
        missing = []
        for field in self._fields:
            value = read_value(field, self._widgets[field.key])
            if (
                field.key not in self._reset_keys
                and field.required
                and is_config_empty(field, value)
            ):
                missing.append(field)
        return missing

    def _refresh_required(self):
        """足りない必須を印し、OK と適用を止める。"""
        if not hasattr(self, "_ok_button"):
            return
        missing_keys = {field.key for field in self._missing_required()}
        message = get_text("ui.plugin_config_required_missing")
        for field in self._fields:
            widget = self._widgets.get(field.key)
            name_item = self._name_items.get(field.key)
            invalid = field.key in missing_keys
            if widget is not None:
                if invalid:
                    widget.setStyleSheet(_INVALID_STYLE)
                    widget.setToolTip(message)
                else:
                    widget.setStyleSheet("")
                    widget.setToolTip(self._expand(field.description) if field.description else "")
            if name_item is not None:
                if invalid:
                    name_item.setToolTip(message)
                elif field.description:
                    name_item.setToolTip(self._expand(field.description))
                else:
                    name_item.setToolTip("")
        blocked = bool(missing_keys)
        self._ok_button.setEnabled(not blocked)
        self._apply_button.setEnabled(not blocked)
        tip = message if blocked else ""
        self._ok_button.setToolTip(tip)
        self._apply_button.setToolTip(tip)
        if hasattr(self, "_table"):
            self._table.resizeRowsToContents()

    def _save(self):
        """必須が足りなければ警告して保存しない。足りれば書いて、開いたときの値を取り直す。

        Returns:
            保存したとき True。
        """
        missing = self._missing_required()
        if missing:
            QMessageBox.warning(
                self,
                get_text("ui.plugin_config_title").format(name=self._plugin_id),
                get_text("ui.plugin_config_required_missing"),
            )
            self._refresh_required()
            return False
        pending = [self._field_for(key) for key in self._dirty_sync]
        pending = [field for field in pending if field is not None]
        self._sync_timer.stop()
        scoped = self._host.scoped(self._plugin_id)
        written = []
        for field in self._fields:
            value = read_value(field, self._widgets[field.key])
            default = coerce_field_value(field, field.default)
            if field.key in self._reset_keys and value == default:
                if field.key not in self._previewed_sync and scoped.reset_config(field.key):
                    written.append(field)
            elif scoped.set_config(field.key, value):
                written.append(field)
        self._capture_snapshot()
        self._dirty_sync.clear()
        self._previewed_sync.clear()
        self._reload_if_needed([*pending, *written])
        return True

    def _reset_to_defaults(self):
        """各項目を既定値にし、即時保存の項目は保存も戻す。"""
        self._sync_timer.stop()
        self._dirty_sync.clear()
        scoped = self._host.scoped(self._plugin_id)
        written = []
        self._resetting = True
        try:
            for field in self._fields:
                value = coerce_field_value(field, field.default)
                self._reset_keys.add(field.key)
                set_widget_value(field, self._widgets[field.key], value)
                if config_field_syncs(field):
                    if scoped.reset_config(field.key):
                        self._previewed_sync.add(field.key)
                        written.append(field)
        finally:
            self._resetting = False
        self._reload_if_needed(written)
        self._refresh_required()

    def _restore_preview(self):
        """即時保存した値を、開いたときの値へ戻す。"""
        self._sync_timer.stop()
        self._dirty_sync.clear()
        if not self._previewed_sync:
            return
        scoped = self._host.scoped(self._plugin_id)
        restored = []
        for key in list(self._previewed_sync):
            field = self._field_for(key)
            if field is None:
                continue
            original = self._snapshot.get(key)
            current = scoped.get_config(field.key, field.default)
            if current != original:
                scoped.set_config(field.key, original)
                restored.append(field)
        self._previewed_sync.clear()
        self._reset_keys.clear()
        self._reload_if_needed(restored)

    def _reload_if_needed(self, fields):
        """読み直しが要る項目があれば現在を読み直す。

        Args:
            fields: 保存した項目。
        """
        if config_should_reload(fields):
            self._host.reload_current()

    def _apply_and_accept(self):
        """保存できたらダイアログを閉じる。"""
        if self._save():
            self.accept()

    def reject(self):
        """即時保存を開いたときの値に戻してから閉じる。"""
        self._restore_preview()
        super().reject()
