"""ファイル設定（プラグイン一覧と拡張子ごとの読み込み方式）。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ez_co.enums.archives import ArchiveInfo
from ez_co.plugins.api import BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID, FileKind
from ez_co.plugins.manager import get_plugin_manager
from ez_co.utils.language_manager import get_text

PLUGIN_COLUMNS = ("name", "id", "version", "extensions", "status")
PLUGIN_DEFAULT_WIDTHS = {
    "name": 180,
    "id": 220,
    "version": 80,
    "extensions": 90,
    "status": 110,
}
EXT_COLUMNS = ("extension", "kind", "handler")
EXT_DEFAULT_WIDTHS = {
    "extension": 100,
    "kind": 110,
    "handler": 280,
}


class NoWheelComboBox(QComboBox):
    """閉じているときはホイールで値を変えず、親の一覧をスクロールさせる。"""

    def wheelEvent(self, event):
        if self.view() is not None and self.view().isVisible():
            super().wheelEvent(event)
            return
        target = self.parent()
        while target is not None and not isinstance(target, QAbstractScrollArea):
            target = target.parent()
        if target is not None:
            QApplication.sendEvent(target.viewport(), event)
        else:
            event.ignore()


class PluginDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.plugin_manager = get_plugin_manager()
        self._ext_rows = self.plugin_manager.extension_rows(self.config)
        self._handler_choices = {row.extension: row.selected for row in self._ext_rows}
        self._ext_sort_column = 0
        self._ext_sort_asc = True
        self._combos = {}
        self.setWindowTitle(get_text("ui.plugin_dialog_title"))
        self.setMinimumSize(720, 520)
        self._setup_ui()
        self.finished.connect(self.apply_layout_to_config)

    def _setup_ui(self):
        layout = QVBoxLayout()

        layout.addWidget(QLabel(get_text("ui.plugin_list")))
        self.plugin_table = QTableWidget(0, len(PLUGIN_COLUMNS))
        self.plugin_table.setHorizontalHeaderLabels([
            get_text("ui.plugin_name"),
            get_text("ui.plugin_id"),
            get_text("ui.plugin_version"),
            get_text("ui.plugin_supported_extensions"),
            get_text("ui.plugin_status"),
        ])
        self._prepare_table(self.plugin_table)
        self.plugin_table.setSortingEnabled(True)
        layout.addWidget(self.plugin_table, 1)
        self._fill_plugin_table()
        self._restore_table_layout(self.plugin_table, PLUGIN_COLUMNS, PLUGIN_DEFAULT_WIDTHS, "plugin_table")

        layout.addWidget(QLabel(get_text("ui.plugin_extensions")))
        self.ext_filter = QLineEdit()
        self.ext_filter.setPlaceholderText(get_text("ui.plugin_filter_placeholder"))
        self.ext_filter.setClearButtonEnabled(True)
        self.ext_filter.textChanged.connect(self._render_extension_table)
        layout.addWidget(self.ext_filter)

        self.ext_table = QTableWidget(0, len(EXT_COLUMNS))
        self.ext_table.setHorizontalHeaderLabels([
            get_text("ui.plugin_extension"),
            get_text("ui.plugin_kind"),
            get_text("ui.plugin_handler"),
        ])
        self._prepare_table(self.ext_table)
        self.ext_table.horizontalHeader().sectionClicked.connect(self._on_ext_header_clicked)
        self.ext_table.setSortingEnabled(False)
        layout.addWidget(self.ext_table, 2)
        self._render_extension_table()
        self._restore_table_layout(self.ext_table, EXT_COLUMNS, EXT_DEFAULT_WIDTHS, "ext_table")

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _prepare_table(self, table: QTableWidget):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(48)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.setWordWrap(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.setHorizontalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)

    def _dialog_table_state(self, key: str) -> dict:
        dialog = self.config.plugins.get("dialog") or {}
        if not isinstance(dialog, dict):
            return {}
        state = dialog.get(key) or {}
        return state if isinstance(state, dict) else {}

    def _restore_table_layout(self, table: QTableWidget, keys, default_widths, state_key: str):
        state = self._dialog_table_state(state_key)
        widths = dict(default_widths)
        saved_widths = state.get("widths") or {}
        if isinstance(saved_widths, dict):
            for key, value in saved_widths.items():
                if key in default_widths:
                    try:
                        widths[key] = max(48, int(value))
                    except (TypeError, ValueError):
                        pass
        for logical, key in enumerate(keys):
            table.setColumnWidth(logical, widths[key])

        order = [key for key in (state.get("order") or []) if key in keys]
        for key in keys:
            if key not in order:
                order.append(key)
        header = table.horizontalHeader()
        for visual, key in enumerate(order):
            logical = keys.index(key)
            current = header.visualIndex(logical)
            if current != visual:
                header.moveSection(current, visual)

    def _table_layout(self, table: QTableWidget, keys) -> dict:
        header = table.horizontalHeader()
        visual_keys = [None] * len(keys)
        widths = {}
        for logical, key in enumerate(keys):
            visual = header.visualIndex(logical)
            if 0 <= visual < len(visual_keys):
                visual_keys[visual] = key
            widths[key] = table.columnWidth(logical)
        return {
            "order": [key for key in visual_keys if key],
            "widths": widths,
        }

    def apply_layout_to_config(self):
        dialog = dict(self.config.plugins.get("dialog") or {})
        dialog["plugin_table"] = self._table_layout(self.plugin_table, PLUGIN_COLUMNS)
        dialog["ext_table"] = self._table_layout(self.ext_table, EXT_COLUMNS)
        self.config.plugins["dialog"] = dialog

    def _text_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        return item

    def _fill_plugin_table(self):
        rows = list(self.plugin_manager.plugins)
        failed = list(self.plugin_manager.failed)
        self.plugin_table.setSortingEnabled(False)
        self.plugin_table.setRowCount(len(rows) + len(failed))
        for index, plugin in enumerate(rows):
            extensions = ", ".join(spec.extension for spec in plugin.formats)
            self.plugin_table.setItem(index, 0, self._text_item(plugin.name))
            self.plugin_table.setItem(index, 1, self._text_item(plugin.plugin_id))
            self.plugin_table.setItem(index, 2, self._text_item(plugin.manifest.version))
            self.plugin_table.setItem(index, 3, self._text_item(extensions))
            self.plugin_table.setItem(index, 4, self._text_item(get_text("ui.plugin_status_ok")))
        for offset, (path, error) in enumerate(failed):
            index = len(rows) + offset
            status = get_text("ui.plugin_status_error").format(error=error)
            self.plugin_table.setItem(index, 0, self._text_item(path.name))
            self.plugin_table.setItem(index, 1, self._text_item("-"))
            self.plugin_table.setItem(index, 2, self._text_item("-"))
            self.plugin_table.setItem(index, 3, self._text_item("-"))
            self.plugin_table.setItem(index, 4, self._text_item(status))
        if self.plugin_table.rowCount() == 0:
            self.plugin_table.setRowCount(1)
            empty = self._text_item(get_text("ui.plugin_no_plugins"))
            self.plugin_table.setItem(0, 0, empty)
            self.plugin_table.setSpan(0, 0, 1, 5)
            self.plugin_table.setSortingEnabled(False)
            return
        self.plugin_table.setSortingEnabled(True)

    def _kind_label(self, kind: FileKind) -> str:
        if kind == FileKind.IMAGE:
            return get_text("ui.plugin_kind_image")
        return get_text("ui.plugin_kind_archive")

    def _provider_label(self, provider_id: str, plugin_name: str) -> str:
        if provider_id == BUILTIN_PROVIDER_ID:
            return get_text("ui.plugin_handler_builtin")
        if provider_id == SKIP_PROVIDER_ID:
            return get_text("ui.plugin_handler_skip")
        if plugin_name:
            return f"{plugin_name} ({provider_id})"
        return provider_id or ""

    def _on_ext_header_clicked(self, column: int):
        if column == self._ext_sort_column:
            self._ext_sort_asc = not self._ext_sort_asc
        else:
            self._ext_sort_column = column
            self._ext_sort_asc = True
        self._render_extension_table()

    def _visible_ext_rows(self):
        query = self.ext_filter.text().strip().lower()
        rows = list(self._ext_rows)
        if query:
            filtered = []
            for row in rows:
                kind = self._kind_label(row.kind)
                handlers = [
                    self._provider_label(provider_id, plugin_name)
                    for provider_id, plugin_name in row.providers
                ]
                haystack = " ".join([row.extension, kind, *handlers]).lower()
                if query in haystack:
                    filtered.append(row)
            rows = filtered
        column = self._ext_sort_column

        def sort_key(row):
            if column == 1:
                return self._kind_label(row.kind)
            if column == 2:
                selected = self._handler_choices.get(row.extension, row.selected)
                name = next((plugin_name for provider_id, plugin_name in row.providers if provider_id == selected), "")
                return self._provider_label(selected, name)
            return row.extension

        rows.sort(key=sort_key, reverse=not self._ext_sort_asc)
        return rows

    def _render_extension_table(self):
        rows = self._visible_ext_rows()
        self._combos.clear()
        self.ext_table.clearContents()
        self.ext_table.setRowCount(len(rows))
        if not rows:
            self.ext_table.setRowCount(1)
            empty = self._text_item(get_text("ui.plugin_filter_empty"))
            self.ext_table.setItem(0, 0, empty)
            self.ext_table.setSpan(0, 0, 1, 3)
            return
        self.ext_table.setSpan(0, 0, 1, 1)
        for index, row in enumerate(rows):
            kind = self._kind_label(row.kind)
            self.ext_table.setItem(index, 0, self._text_item(row.extension))
            self.ext_table.setItem(index, 1, self._text_item(kind))
            combo = NoWheelComboBox()
            for provider_id, plugin_name in row.providers:
                label = self._provider_label(provider_id, plugin_name)
                combo.addItem(label, provider_id)
                combo.setItemData(combo.count() - 1, label, Qt.ItemDataRole.ToolTipRole)
            selected = self._handler_choices.get(row.extension, row.selected)
            selected_index = max(0, combo.findData(selected))
            combo.setCurrentIndex(selected_index)
            combo.setEnabled(len(row.providers) > 1)
            combo.setToolTip(combo.currentText())
            combo.currentIndexChanged.connect(
                lambda _i, extension=row.extension, widget=combo: self._on_handler_changed(extension, widget)
            )
            self.ext_table.setCellWidget(index, 2, combo)
            self._combos[row.extension] = combo

    def _on_handler_changed(self, extension: str, combo: QComboBox):
        combo.setToolTip(combo.currentText())
        provider_id = combo.currentData()
        if provider_id:
            self._handler_choices[extension] = provider_id

    def has_handler_changes(self) -> bool:
        original = {row.extension: row.selected for row in self._ext_rows}
        return self._handler_choices != original

    def apply_to_config(self):
        handlers = {}
        archive_enabled_by_key = {}
        for extension, provider_id in self._handler_choices.items():
            if provider_id:
                handlers[extension] = provider_id
            archive_type = ArchiveInfo.get_archive_type_by_extension(extension)
            if archive_type is None:
                archive_type = ArchiveInfo.get_archive_type_by_path(f"file{extension}")
            if archive_type is not None:
                key = ArchiveInfo.get_config_key(archive_type)
                if provider_id != SKIP_PROVIDER_ID:
                    archive_enabled_by_key[key] = True
                else:
                    archive_enabled_by_key.setdefault(key, False)
        self.config.plugins["extension_handlers"] = handlers
        for key, enabled in archive_enabled_by_key.items():
            self.config.archive[key] = enabled
        if archive_enabled_by_key:
            self.config.archive["enabled"] = any(archive_enabled_by_key.values())
