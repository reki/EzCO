"""プラグインが登録したスキーマから設定ダイアログを作る。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
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
        self.setMinimumSize(480, 240)
        self.resize(560, 300)
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
        table.setColumnWidth(1, 100)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(False)
        table.verticalHeader().setDefaultSectionSize(28)
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
        if field.value_type == "bool":
            widget = QCheckBox()
            widget.setChecked(bool(current))
            return widget
        if field.value_type == "int":
            widget = QSpinBox()
            widget.setRange(-2147483647, 2147483647)
            try:
                widget.setValue(int(current))
            except (TypeError, ValueError):
                widget.setValue(int(field.default or 0))
            return widget
        widget = QLineEdit()
        widget.setText("" if current is None else str(current))
        return widget

    def _center_widget(self, widget):
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        holder_layout.addWidget(widget)
        return holder

    def _save(self):
        scoped = self._host.scoped(self._plugin_id)
        for field in self._fields:
            widget = self._widgets[field.key]
            if field.value_type == "bool":
                value = widget.isChecked()
            elif field.value_type == "int":
                value = widget.value()
            else:
                value = widget.text()
            scoped.set_config(field.key, value)

    def _apply_and_accept(self):
        self._save()
        self.accept()
