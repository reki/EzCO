"""プラグインが登録したスキーマから設定ダイアログを作る。"""
from PySide6.QtCore import QDate, QDateTime, Qt, QTime
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDateEdit,
    QDateTimeEdit,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ez_co.plugins.host import coerce_config_value
from ez_co.utils.language_manager import get_text


class PluginConfigDialog(QDialog):
    def __init__(self, host, plugin_id: str, plugin_name: str = "", parent=None):
        super().__init__(parent)
        self._host = host
        self._plugin_id = plugin_id
        self._fields = list(host.configs_for(plugin_id))
        self._widgets = {}
        title = plugin_name or plugin_id
        self.setWindowTitle(get_text("ui.plugin_config_title").format(name=title))
        self.setMinimumSize(520, 280)
        self.resize(620, 360)
        self._setup_ui()

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
        table.setColumnWidth(1, 200)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(False)
        table.verticalHeader().setMinimumSectionSize(32)
        scoped = self._host.scoped(self._plugin_id)
        table.setRowCount(len(self._fields))
        for index, field in enumerate(self._fields):
            label = field.label or field.key
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
        table.resizeRowsToContents()
        layout.addWidget(table)
        buttons = QHBoxLayout()
        buttons.addStretch()
        apply_button = QPushButton(get_text("ui.apply"))
        apply_button.clicked.connect(self._save)
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self._apply_and_accept)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
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
        if kind == "int":
            return widget.value()
        if kind == "float":
            return widget.value()
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

    def _save(self):
        scoped = self._host.scoped(self._plugin_id)
        for field in self._fields:
            scoped.set_config(field.key, self._read_value(field, self._widgets[field.key]))

    def _apply_and_accept(self):
        self._save()
        self.accept()


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
