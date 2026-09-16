"""プラグインが登録したスキーマから設定ダイアログを作る。"""
from PySide6.QtCore import QDate, QDateTime, Qt, QTime, QTimer, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFontComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
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
    config_field_syncs,
    config_should_reload,
)
from ez_co.utils.language_manager import get_text

SYNC_RELOAD_IDLE_MS = 500


class PluginConfigDialog(QDialog):
    def __init__(self, host, plugin_id: str, plugin_name: str = "", parent=None):
        super().__init__(parent)
        self._host = host
        self._plugin_id = plugin_id
        self._fields = list(host.configs_for(plugin_id))
        self._widgets = {}
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

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        table = QTableWidget(0, 2)
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
            name_item.setToolTip(field.description or label)
            table.setItem(index, 0, name_item)
            widget = self._make_value_widget(field, current)
            if field.description:
                widget.setToolTip(field.description)
            if field.value_type == "bool":
                table.setCellWidget(index, 1, self._center_widget(widget))
            else:
                table.setCellWidget(index, 1, widget)
            self._widgets[field.key] = widget
            self._connect_sync(field, widget)
        table.resizeRowsToContents()
        layout.addWidget(table)
        buttons = QHBoxLayout()
        buttons.addStretch()
        reset_button = QPushButton(get_text("ui.reset"))
        reset_button.clicked.connect(self._reset_to_defaults)
        apply_button = QPushButton(get_text("ui.apply"))
        apply_button.clicked.connect(self._save)
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self._apply_and_accept)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(reset_button)
        buttons.addWidget(apply_button)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def _make_value_widget(self, field, current):
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
                widget.setValue(int(field.default or 0))
            return widget
        if kind == "float":
            widget = QDoubleSpinBox()
            widget.setRange(-1e12, 1e12)
            widget.setDecimals(4)
            try:
                widget.setValue(float(current))
            except (TypeError, ValueError):
                try:
                    widget.setValue(float(field.default or 0))
                except (TypeError, ValueError):
                    widget.setValue(0.0)
            return widget
        if kind in ("int_range", "float_range"):
            return _RangeRow(field, current)
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
        if kind == "choice" and field.choices:
            widget = QComboBox()
            for value, label in field.choices:
                widget.addItem(label, value)
            index = widget.findData("" if current is None else str(current))
            widget.setCurrentIndex(max(0, index))
            return widget
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
        if isinstance(widget, _RangeRow):
            widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))
            return
        widget.valueChanged.connect(lambda _=None, key=field.key: self._on_sync_changed(key))

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
            scoped.set_config(field.key, self._read_value(field, self._widgets[field.key]))
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

    def _center_widget(self, widget):
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder_layout.addWidget(widget)
        return holder

    def _read_value(self, field, widget):
        kind = field.value_type
        if kind == "bool":
            return widget.isChecked()
        if kind in ("int", "float", "int_range", "float_range"):
            return widget.value()
        if kind == "path":
            return widget.text()
        if kind == "password":
            return widget.text()
        if kind == "color":
            return widget.property("color_value") or field.default
        if kind == "date":
            return _seconds_from_qdate(widget.date())
        if kind == "datetime":
            return _seconds_from_qdatetime(widget.dateTime())
        if kind == "choice" and field.choices:
            data = widget.currentData()
            return field.choices[0][0] if data is None else data
        if kind == "font":
            return widget.currentFont().family()
        return widget.text()

    def _set_widget_value(self, field, widget, value):
        kind = field.value_type
        if kind == "bool":
            widget.blockSignals(True)
            widget.setChecked(bool(value))
            widget.blockSignals(False)
            return
        if kind in ("int", "float"):
            widget.blockSignals(True)
            widget.setValue(value)
            widget.blockSignals(False)
            return
        if kind in ("int_range", "float_range"):
            widget.setValue(value)
            return
        if kind == "path":
            widget.setText("" if value is None else str(value))
            return
        if kind == "password":
            widget.blockSignals(True)
            widget.setText("" if value is None else str(value))
            widget.blockSignals(False)
            return
        if kind == "color":
            _paint_color_button(widget, coerce_config_value("color", value, field.default))
            return
        if kind == "date":
            widget.blockSignals(True)
            widget.setDate(_qdate_from_seconds(value))
            widget.blockSignals(False)
            return
        if kind == "datetime":
            widget.blockSignals(True)
            widget.setDateTime(_qdatetime_from_seconds(value))
            widget.blockSignals(False)
            return
        if kind == "choice" and field.choices:
            widget.blockSignals(True)
            index = widget.findData("" if value is None else str(value))
            widget.setCurrentIndex(max(0, index))
            widget.blockSignals(False)
            return
        if kind == "font":
            widget.blockSignals(True)
            family = "" if value is None else str(value)
            if family:
                widget.setCurrentFont(QFont(family))
            widget.blockSignals(False)
            return
        widget.blockSignals(True)
        widget.setText("" if value is None else str(value))
        widget.blockSignals(False)

    def _save(self):
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

    def _reset_to_defaults(self):
        self._sync_timer.stop()
        self._dirty_sync.clear()
        scoped = self._host.scoped(self._plugin_id)
        written = []
        for field in self._fields:
            value = coerce_field_value(field, field.default)
            self._set_widget_value(field, self._widgets[field.key], value)
            if config_field_syncs(field):
                scoped.set_config(field.key, value)
                self._previewed_sync.add(field.key)
                written.append(field)
        self._reload_if_needed(written)

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
        self._save()
        self.accept()

    def reject(self):
        self._restore_preview()
        super().reject()


def config_field_display_name(field) -> str:
    """設定ダイアログの項目名。range は末尾に範囲、float_range は step も付ける。"""
    name = str(field.label or field.key or "")
    kind = field.value_type
    if kind not in ("int_range", "float_range"):
        return name
    if field.minimum is None or field.maximum is None:
        return name
    as_int = kind == "int_range"
    step = field.step
    lo = _format_range_number(field.minimum, as_int, step)
    hi = _format_range_number(field.maximum, as_int, step)
    if as_int:
        return get_text("ui.plugin_config_int_range_name", name=name, minimum=lo, maximum=hi)
    st = _format_range_number(step if step is not None else 0.01, False, step)
    return get_text("ui.plugin_config_float_range_name", name=name, minimum=lo, maximum=hi, step=st)


def _format_range_number(value, as_int: bool, step) -> str:
    if as_int:
        return str(int(value))
    decimals = _decimals_from_step(step if step is not None else 0.01)
    text = f"{float(value):.{decimals}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


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
        self.setValue(coerce_field_value(field, current))

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
