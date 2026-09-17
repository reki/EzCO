"""プラグインが登録したスキーマから設定ダイアログを作る。"""
from PySide6.QtCore import QDate, QDateTime, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QCompleter,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ez_co.plugins.host import (
    coerce_config_value,
    coerce_field_value,
    config_choice_key,
    config_field_syncs,
    config_should_reload,
    is_config_empty,
)
from ez_co.utils.language_manager import get_text

SYNC_RELOAD_IDLE_MS = 500
_DROPDOWN_TYPES = ("choice", "charset", "language", "country")
_NUMERIC_TYPES = ("int", "float", "int_range", "float_range")
_INVALID_STYLE = "border: 1px solid #c62828;"


class PluginConfigDialog(QDialog):
    def __init__(self, host, plugin_id: str, plugin_name: str = "", parent=None):
        super().__init__(parent)
        self._host = host
        self._plugin_id = plugin_id
        self._fields = list(host.configs_for(plugin_id))
        self._widgets = {}
        self._name_items = {}
        self._snapshot = {}
        self._dirty_sync = set()
        self._previewed_sync = set()
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

    def _setup_ui(self):
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
        scoped = self._host.scoped(self._plugin_id)
        table.setRowCount(len(self._fields))
        for index, field in enumerate(self._fields):
            label = config_field_display_name(field)
            current = scoped.get_config(field.key, field.default)
            name_item = QTableWidgetItem(label)
            table.setItem(index, 0, name_item)
            self._name_items[field.key] = name_item
            widget = self._make_value_widget(field, current)
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

    def _make_value_widget(self, field, current):
        if field.multiple and field.value_type in _DROPDOWN_TYPES and field.choices:
            return _ChoiceMultiList(field, current)
        if field.multiple:
            return _MultiRows(field, current, self)
        return self._make_single_widget(field, current)

    def _make_single_widget(self, field, current):
        kind = field.value_type
        if kind == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(current))
            return widget
        if kind == "int":
            widget = QSpinBox()
            widget.setRange(-2147483647, 2147483647)
            try:
                widget.setValue(int(current))
            except (TypeError, ValueError):
                widget.setValue(0)
            return _with_suffix(widget, field)
        if kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-1e12, 1e12)
            widget.setDecimals(4)
            try:
                widget.setValue(float(current))
            except (TypeError, ValueError):
                widget.setValue(0.0)
            return _with_suffix(widget, field)
        if kind in ("int_range", "float_range"):
            return _with_suffix(_RangeRow(field, current), field)
        if kind == "path":
            return _PathRow(field, current, self)
        if kind == "password":
            widget = QLineEdit()
            widget.setEchoMode(QLineEdit.EchoMode.Password)
            widget.setText("" if current is None else str(current))
            return widget
        if kind == "color":
            color = coerce_config_value("color", current, field.default)
            button = QPushButton()
            _paint_color_button(button, color)
            button.clicked.connect(lambda _=False, widget=button: self._pick_color(widget))
            return button
        if kind == "date":
            widget = QDateEdit()
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd")
            widget.setDate(_qdate_from_seconds(current))
            return widget
        if kind == "datetime":
            widget = QDateTimeEdit()
            widget.setCalendarPopup(True)
            widget.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
            widget.setDateTime(_qdatetime_from_seconds(current))
            return widget
        if kind in _DROPDOWN_TYPES and field.choices:
            return _FilterCombo(field.choices, current)
        if kind == "font":
            widget = QFontComboBox()
            family = "" if current is None else str(current)
            if family:
                widget.setCurrentFont(QFont(family))
            return widget
        widget = QLineEdit()
        widget.setText("" if current is None else str(current))
        return widget

    def _connect_sync(self, field, widget):
        if not config_field_syncs(field):
            return
        if isinstance(widget, (_MultiRows, _SuffixRow)):
            widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))
            return
        if isinstance(widget, _RangeRow):
            widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))
            return
        widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))

    def _connect_required(self, field, widget):
        self._watch_widget(widget)

    def _watch_widget(self, widget):
        if isinstance(widget, _MultiRows):
            widget.rowsChanged.connect(self._refresh_required)
            return
        if isinstance(widget, _ChoiceMultiList):
            widget.changed.connect(self._refresh_required)
            return
        if isinstance(widget, _SuffixRow):
            self._watch_widget(widget.editor)
            return
        if isinstance(widget, _PathRow):
            widget._edit.textChanged.connect(lambda _=None: self._refresh_required())
            widget._edit.editingFinished.connect(self._refresh_required)
            return
        if isinstance(widget, QLineEdit):
            widget.textChanged.connect(lambda _=None: self._refresh_required())
            widget.editingFinished.connect(self._refresh_required)
            return
        if isinstance(widget, (QComboBox, _FilterCombo)):
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
        self._dirty_sync.add(key)
        self._sync_timer.start()

    def _flush_sync(self) -> bool:
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
            value = self._read_value(field, self._widgets[field.key])
            if field.required and is_config_empty(field, value):
                continue
            scoped.set_config(field.key, value)
            self._previewed_sync.add(field.key)
            written.append(field)
        self._reload_if_needed(written)
        return True

    def _field_for(self, key: str):
        for field in self._fields:
            if field.key == key:
                return field
        return None

    def _capture_snapshot(self):
        self._snapshot = {
            field.key: self._read_value(field, self._widgets[field.key])
            for field in self._fields
        }

    def _pick_color(self, button: QPushButton):
        current = button.property("color_value") or "#000000"
        color = QColorDialog.getColor(QColor(str(current)), self)
        if color.isValid():
            _paint_color_button(button, color.name())
            self._refresh_required()

    def _center_widget(self, widget):
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder_layout.addWidget(widget)
        return holder

    def _read_single(self, field, widget):
        editor = widget.editor if isinstance(widget, _SuffixRow) else widget
        kind = field.value_type
        if kind == "bool":
            return editor.isChecked()
        if kind in ("int", "float", "int_range", "float_range"):
            return editor.value()
        if kind == "path":
            return editor.text()
        if kind == "password":
            return editor.text()
        if kind == "color":
            return editor.property("color_value") or field.default
        if kind == "date":
            return _seconds_from_qdate(editor.date())
        if kind == "datetime":
            return _seconds_from_qdatetime(editor.dateTime())
        if kind in _DROPDOWN_TYPES and field.choices:
            data = editor.currentData()
            if data is None:
                text = editor.currentText()
                for value, label in field.choices:
                    if text in (value, label):
                        return value
                return field.choices[0][0]
            return data
        if kind == "font":
            return editor.currentFont().family()
        return editor.text()

    def _read_value(self, field, widget):
        if isinstance(widget, _MultiRows):
            return widget.values()
        if isinstance(widget, _ChoiceMultiList):
            return widget.values()
        return self._read_single(field, widget)

    def _set_widget_value(self, field, widget, value):
        if isinstance(widget, _MultiRows):
            widget.set_values(value)
            return
        if isinstance(widget, _ChoiceMultiList):
            widget.set_values(value)
            return
        editor = widget.editor if isinstance(widget, _SuffixRow) else widget
        kind = field.value_type
        if kind == "bool":
            editor.blockSignals(True)
            editor.setChecked(bool(value))
            editor.blockSignals(False)
            return
        if kind in ("int", "float"):
            editor.blockSignals(True)
            editor.setValue(value)
            editor.blockSignals(False)
            return
        if kind in ("int_range", "float_range"):
            editor.setValue(value)
            return
        if kind == "path":
            editor.setText("" if value is None else str(value))
            return
        if kind == "password":
            editor.blockSignals(True)
            editor.setText("" if value is None else str(value))
            editor.blockSignals(False)
            return
        if kind == "color":
            _paint_color_button(editor, coerce_config_value("color", value, field.default))
            return
        if kind == "date":
            editor.blockSignals(True)
            editor.setDate(_qdate_from_seconds(value))
            editor.blockSignals(False)
            return
        if kind == "datetime":
            editor.blockSignals(True)
            editor.setDateTime(_qdatetime_from_seconds(value))
            editor.blockSignals(False)
            return
        if kind in _DROPDOWN_TYPES and field.choices:
            editor.blockSignals(True)
            index = editor.findData(config_choice_key(value))
            editor.setCurrentIndex(max(0, index))
            editor.blockSignals(False)
            return
        if kind == "font":
            editor.blockSignals(True)
            family = "" if value is None else str(value)
            if family:
                editor.setCurrentFont(QFont(family))
            editor.blockSignals(False)
            return
        editor.blockSignals(True)
        editor.setText("" if value is None else str(value))
        editor.blockSignals(False)

    def _missing_required(self):
        missing = []
        for field in self._fields:
            value = self._read_value(field, self._widgets[field.key])
            if field.required and is_config_empty(field, value):
                missing.append(field)
        return missing

    def _refresh_required(self):
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
                    widget.setToolTip(field.description or "")
            if name_item is not None:
                if invalid:
                    name_item.setToolTip(message)
                elif field.description:
                    name_item.setToolTip(field.description)
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
        for field in self._fields:
            scoped.set_config(field.key, self._read_value(field, self._widgets[field.key]))
        self._capture_snapshot()
        self._dirty_sync.clear()
        self._previewed_sync.clear()
        self._reload_if_needed(pending)
        return True

    def _reset_to_defaults(self):
        self._sync_timer.stop()
        self._dirty_sync.clear()
        scoped = self._host.scoped(self._plugin_id)
        written = []
        for field in self._fields:
            value = coerce_field_value(field, field.default)
            self._set_widget_value(field, self._widgets[field.key], value)
            if config_field_syncs(field):
                if not (field.required and is_config_empty(field, value)):
                    scoped.set_config(field.key, value)
                    self._previewed_sync.add(field.key)
                    written.append(field)
        self._reload_if_needed(written)
        self._refresh_required()

    def _restore_preview(self):
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
        self._reload_if_needed(restored)

    def _reload_if_needed(self, fields):
        if config_should_reload(fields):
            self._host.reload_current()

    def _apply_and_accept(self):
        if self._save():
            self.accept()

    def reject(self):
        self._restore_preview()
        super().reject()

    def _blank_value(self, field):
        kind = field.value_type
        if kind == "bool":
            return False
        if kind in ("int", "int_range"):
            if field.minimum is not None:
                return field.minimum
            return 0
        if kind in ("float", "float_range"):
            if field.minimum is not None:
                return field.minimum
            return 0.0
        if kind == "color":
            return coerce_config_value("color", None, field.default)
        if kind in ("date", "datetime"):
            return 0
        if kind == "font":
            return ""
        return ""


def config_field_display_name(field) -> str:
    """設定ダイアログの項目名。range は末尾に範囲、float_range は step も付ける。"""
    name = str(field.label or field.key or "")
    kind = field.value_type
    if kind in ("int_range", "float_range"):
        if field.minimum is not None and field.maximum is not None:
            as_int = kind == "int_range"
            step = field.step
            lo = _format_range_number(field.minimum, as_int, step)
            hi = _format_range_number(field.maximum, as_int, step)
            if as_int:
                name = get_text("ui.plugin_config_int_range_name", name=name, minimum=lo, maximum=hi)
            else:
                st = _format_range_number(step if step is not None else 0.01, False, step)
                name = get_text(
                    "ui.plugin_config_float_range_name",
                    name=name,
                    minimum=lo,
                    maximum=hi,
                    step=st,
                )
    if field.multiple and kind in _DROPDOWN_TYPES:
        return name + get_text("ui.plugin_config_multiple")
    return name


def _format_range_number(value, as_int: bool, step) -> str:
    if as_int:
        return str(int(value))
    decimals = _decimals_from_step(step if step is not None else 0.01)
    text = f"{float(value):.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _with_suffix(widget, field):
    if not field.suffix or field.value_type not in _NUMERIC_TYPES:
        return widget
    return _SuffixRow(widget, field.suffix)


class _SuffixRow(QWidget):
    valueChanged = Signal(object)

    def __init__(self, editor, suffix: str, parent=None):
        super().__init__(parent)
        self.editor = editor
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(editor, 1)
        layout.addWidget(QLabel(suffix), 0)
        if hasattr(editor, "valueChanged"):
            editor.valueChanged.connect(self.valueChanged.emit)


class _FilterCombo(QComboBox):
    def __init__(self, choices, current, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        for value, label in choices:
            self.addItem(label, value)
        completer = self.completer()
        if completer is None:
            completer = QCompleter(self)
            self.setCompleter(completer)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        index = self.findData(config_choice_key(current))
        self.setCurrentIndex(max(0, index))


class _ChoiceMultiList(QWidget):
    changed = Signal()

    def __init__(self, field, current, parent=None):
        super().__init__(parent)
        self._choices = list(field.choices)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        self._filter = QLineEdit()
        layout.addWidget(self._filter)
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for value, label in self._choices:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, value)
            self._list.addItem(item)
        layout.addWidget(self._list)
        self.set_values(current)
        self._filter.textChanged.connect(self._apply_filter)
        self._list.itemSelectionChanged.connect(self.changed.emit)

    def values(self):
        selected = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.isSelected():
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def set_values(self, values):
        wanted = {config_choice_key(item) for item in (values or [])}
        self._list.blockSignals(True)
        for index in range(self._list.count()):
            item = self._list.item(index)
            item.setSelected(str(item.data(Qt.ItemDataRole.UserRole)) in wanted)
        self._list.blockSignals(False)

    def _apply_filter(self, text: str):
        needle = (text or "").casefold()
        for index in range(self._list.count()):
            item = self._list.item(index)
            label = item.text().casefold()
            value = str(item.data(Qt.ItemDataRole.UserRole) or "").casefold()
            item.setHidden(bool(needle) and needle not in label and needle not in value)


class _MultiRows(QWidget):
    valueChanged = Signal(object)
    rowsChanged = Signal()

    def __init__(self, field, current, dialog, parent=None):
        super().__init__(parent)
        self._field = field
        self._dialog = dialog
        self._inners = []
        self._column = QVBoxLayout(self)
        self._column.setContentsMargins(0, 0, 0, 0)
        self._column.setSpacing(4)
        self._rows_box = QVBoxLayout()
        self._rows_box.setContentsMargins(0, 0, 0, 0)
        self._rows_box.setSpacing(4)
        self._column.addLayout(self._rows_box)
        self._add_button = QPushButton("+")
        self._add_button.setFixedWidth(28)
        self._add_button.clicked.connect(self._add_blank)
        self._column.addWidget(self._add_button, 0, Qt.AlignmentFlag.AlignLeft)
        values = list(current or [])
        for value in values:
            self._append_row(value)

    def values(self):
        return [self._dialog._read_single(self._field, inner) for inner in self._inners]

    def set_values(self, values):
        while self._inners:
            self._remove_at(0)
        for value in values or []:
            self._append_row(value)
        self.rowsChanged.emit()

    def _add_blank(self):
        self._append_row(self._dialog._blank_value(self._field))
        self.rowsChanged.emit()
        self.valueChanged.emit(self.values())

    def _append_row(self, value):
        inner = self._dialog._make_single_widget(self._field, value)
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(inner, 1)
        remove = QPushButton("-")
        remove.setFixedWidth(28)
        layout.addWidget(remove, 0)
        self._rows_box.addWidget(row)
        self._inners.append(inner)
        remove.clicked.connect(lambda _=False, widget=inner: self._remove_inner(widget))
        if hasattr(inner, "valueChanged"):
            inner.valueChanged.connect(lambda _=None: self.valueChanged.emit(self.values()))

    def _remove_inner(self, inner):
        try:
            index = self._inners.index(inner)
        except ValueError:
            return
        self._remove_at(index)
        self.rowsChanged.emit()
        self.valueChanged.emit(self.values())

    def _remove_at(self, index: int):
        inner = self._inners.pop(index)
        row = inner.parentWidget()
        self._rows_box.removeWidget(row)
        row.deleteLater()


class _RangeRow(QWidget):
    valueChanged = Signal(object)

    def __init__(self, field, current, parent=None):
        super().__init__(parent)
        self._as_int = field.value_type == "int_range"
        self._minimum = field.minimum
        self._maximum = field.maximum
        self._step = field.step
        if self._minimum is None or self._maximum is None or self._step is None:
            lo, hi, st = (0, 100, 1) if self._as_int else (0.0, 1.0, 0.01)
            self._minimum = lo if self._minimum is None else self._minimum
            self._maximum = hi if self._maximum is None else self._maximum
            self._step = st if self._step is None else self._step
        span = self._maximum - self._minimum
        if self._step <= 0 or span <= 0:
            self._ticks = 0
        else:
            self._ticks = max(1, int(round(span / self._step)))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, self._ticks)
        if self._as_int:
            self._spin = QSpinBox()
            self._spin.setRange(int(self._minimum), int(self._maximum))
            self._spin.setSingleStep(max(1, int(self._step)))
        else:
            self._spin = QDoubleSpinBox()
            self._spin.setRange(float(self._minimum), float(self._maximum))
            self._spin.setSingleStep(float(self._step))
            self._spin.setDecimals(_decimals_from_step(self._step))
        self._spin.setMaximumWidth(96)
        layout.addWidget(self._slider, 1)
        layout.addWidget(self._spin, 0)
        self._slider.valueChanged.connect(self._from_slider)
        self._spin.valueChanged.connect(self._from_spin)
        seed = current
        if isinstance(seed, (list, tuple)):
            seed = seed[0] if seed else None
        self.setValue(seed if seed is not None else self._minimum)

    def value(self):
        return self._spin.value()

    def setValue(self, value):
        number = self._clamp(value)
        tick = self._tick_for(number)
        self._slider.blockSignals(True)
        self._spin.blockSignals(True)
        self._slider.setValue(tick)
        self._spin.setValue(number)
        self._slider.blockSignals(False)
        self._spin.blockSignals(False)

    def _clamp(self, value):
        try:
            number = int(value) if self._as_int else float(value)
        except (TypeError, ValueError):
            number = self._minimum
        if number < self._minimum:
            return int(self._minimum) if self._as_int else float(self._minimum)
        if number > self._maximum:
            return int(self._maximum) if self._as_int else float(self._maximum)
        return int(number) if self._as_int else float(number)

    def _tick_for(self, value) -> int:
        if self._ticks <= 0 or self._step <= 0:
            return 0
        tick = int(round((value - self._minimum) / self._step))
        if tick < 0:
            return 0
        if tick > self._ticks:
            return self._ticks
        return tick

    def _from_slider(self, tick: int):
        number = self._minimum + tick * self._step
        number = self._clamp(number)
        self._spin.blockSignals(True)
        self._spin.setValue(number)
        self._spin.blockSignals(False)
        self.valueChanged.emit(self.value())

    def _from_spin(self, number):
        tick = self._tick_for(number)
        self._slider.blockSignals(True)
        self._slider.setValue(tick)
        self._slider.blockSignals(False)
        self.valueChanged.emit(self.value())


class _PathRow(QWidget):
    def __init__(self, field, current, parent=None):
        super().__init__(parent)
        self._kind = field.path_kind
        self._filter = field.path_filter
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._edit = QLineEdit()
        self._edit.setText("" if current is None else str(current))
        browse = QPushButton(get_text("ui.plugin_config_browse"))
        browse.clicked.connect(self._browse)
        layout.addWidget(self._edit, 1)
        layout.addWidget(browse, 0)

    def text(self) -> str:
        return self._edit.text()

    def setText(self, value: str):
        self._edit.setText("" if value is None else str(value))

    def _browse(self):
        start = self._edit.text().strip() or ""
        if self._kind == "directory":
            path = QFileDialog.getExistingDirectory(self, get_text("ui.plugin_config_browse"), start)
        else:
            path, _ = QFileDialog.getOpenFileName(
                self,
                get_text("ui.plugin_config_browse"),
                start,
                self._filter or "",
            )
        if path:
            self._edit.setText(path)


def _decimals_from_step(step) -> int:
    text = f"{float(step):.10f}".rstrip("0").rstrip(".")
    if "." in text:
        return min(6, max(1, len(text.split(".", 1)[1])))
    return 2


def _qdate_from_seconds(value) -> QDate:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = 0
    return QDateTime.fromSecsSinceEpoch(seconds, Qt.TimeSpec.UTC).date()


def _qdatetime_from_seconds(value) -> QDateTime:
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = 0
    return QDateTime.fromSecsSinceEpoch(seconds, Qt.TimeSpec.UTC).toLocalTime()


def _seconds_from_qdate(value: QDate) -> int:
    return int(QDateTime(value, QTime(0, 0, 0), Qt.TimeSpec.UTC).toSecsSinceEpoch())


def _seconds_from_qdatetime(value: QDateTime) -> int:
    return int(value.toUTC().toSecsSinceEpoch())


def _paint_color_button(button: QPushButton, color: str):
    button.setProperty("color_value", color)
    button.setText(color)
    value = (color or "").lstrip("#")
    light = True
    if len(value) == 6:
        try:
            red = int(value[0:2], 16)
            green = int(value[2:4], 16)
            blue = int(value[4:6], 16)
            light = (red * 299 + green * 587 + blue * 114) >= 140000
        except ValueError:
            light = True
    fg = "#111111" if light else "#f5f5f5"
    button.setStyleSheet(
        f"background-color: {color}; color: {fg}; min-width: 72px; min-height: 22px;"
    )
