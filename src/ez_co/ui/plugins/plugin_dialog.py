"""プラグイン設定（一覧、ON/OFF、拡張子ごとの読み込み方式）。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ez_co.enums.archives import ArchiveInfo
from ez_co.plugins.api import BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID, FileKind
from ez_co.plugins.manager import get_plugin_manager
from ez_co.utils.language_manager import get_text

PLUGIN_COLUMNS = ("enabled", "name", "id", "version", "kind", "extensions", "status", "settings", "license")
PLUGIN_DEFAULT_WIDTHS = {
    "enabled": 56,
    "name": 160,
    "id": 200,
    "version": 72,
    "kind": 90,
    "extensions": 90,
    "status": 220,
    "settings": 100,
    "license": 110,
}
PLUGIN_MIN_WIDTHS = {
    "settings": 88,
    "license": 100,
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
    applied = Signal()

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.plugin_manager = get_plugin_manager()
        self._enabled = {
            plugin.plugin_id: self.plugin_manager.is_enabled(plugin.plugin_id, self.config)
            for plugin in self.plugin_manager.plugins
        }
        self._original_enabled = dict(self._enabled)
        self._handler_stash = {}
        self._ext_rows = self.plugin_manager.extension_rows(self.config, enabled_ids=self._enabled_ids())
        self._handler_choices = {row.extension: row.selected for row in self._ext_rows}
        self._original_handlers = dict(self._handler_choices)
        self._ext_sort_column = 0
        self._ext_sort_asc = True
        self._combos = {}
        self._source_choices = dict(self.plugin_manager.current_source_choices(self.config))
        self._original_source_choices = dict(self._source_choices)
        self.last_applied_source_changes = False
        self.setWindowTitle(get_text("ui.plugin_dialog_title"))
        self.setMinimumSize(760, 540)
        self._setup_ui()
        self.finished.connect(self.apply_layout_to_config)

    def _enabled_ids(self):
        return {plugin_id for plugin_id, enabled in self._enabled.items() if enabled}

    def _setup_ui(self):
        layout = QVBoxLayout()

        list_header = QHBoxLayout()
        list_header.addWidget(QLabel(get_text("ui.plugin_list")))
        list_header.addStretch()
        conflict_button = QPushButton(get_text("ui.plugin_conflict_title"))
        conflict_button.clicked.connect(self._open_conflict_dialog)
        list_header.addWidget(conflict_button)
        layout.addLayout(list_header)
        self.plugin_table = QTableWidget(0, len(PLUGIN_COLUMNS))
        self.plugin_table.setHorizontalHeaderLabels([
            get_text("ui.plugin_enabled"),
            get_text("ui.plugin_name"),
            get_text("ui.plugin_id"),
            get_text("ui.version"),
            get_text("ui.plugin_kind"),
            get_text("ui.plugin_supported_extensions"),
            get_text("ui.plugin_status"),
            get_text("ui.settings"),
            get_text("ui.about_license"),
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
        apply_button = QPushButton(get_text("ui.apply"))
        apply_button.clicked.connect(self._apply)
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(apply_button)
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def _apply(self):
        if not self.has_changes():
            return
        self.last_applied_source_changes = self.has_source_choice_changes()
        self.apply_to_config()
        self._original_enabled = dict(self._enabled)
        self._original_handlers = dict(self._handler_choices)
        self._original_source_choices = dict(self._source_choices)
        self.apply_layout_to_config()
        self.applied.emit()
        if self.last_applied_source_changes:
            self._enabled = {
                plugin.plugin_id: self.plugin_manager.is_enabled(plugin.plugin_id, self.config)
                for plugin in self.plugin_manager.plugins
            }
            self._original_enabled = dict(self._enabled)
            self._fill_plugin_table()
            self._refresh_extension_rows()

    def _prepare_table(self, table: QTableWidget):
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionsClickable(True)
        header.setSectionsMovable(True)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(48)
        table.verticalHeader().setDefaultSectionSize(36)
        table.verticalHeader().setMinimumSectionSize(32)
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
                        widths[key] = max(PLUGIN_MIN_WIDTHS.get(key, 48), int(value))
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

    def _plugin_kind_label(self, plugin) -> str:
        has_file = bool(plugin.formats)
        has_sidebar = plugin.has_sidebar
        if has_file and has_sidebar:
            return get_text("ui.plugin_kind_both")
        if has_sidebar:
            return get_text("ui.plugin_kind_sidebar")
        return get_text("ui.plugin_kind_file")

    def _fill_plugin_table(self):
        rows = list(self.plugin_manager.plugins)
        skipped = list(self.plugin_manager.skipped)
        failed = list(self.plugin_manager.failed)
        self.plugin_table.setSortingEnabled(False)
        self.plugin_table.setRowCount(len(rows) + len(skipped) + len(failed))
        for index, plugin in enumerate(rows):
            checkbox = QCheckBox()
            checkbox.setChecked(self._enabled.get(plugin.plugin_id, True))
            checkbox.toggled.connect(
                lambda checked, plugin_id=plugin.plugin_id: self._on_enabled_changed(plugin_id, checked)
            )
            holder = QWidget()
            holder_layout = QHBoxLayout(holder)
            holder_layout.setContentsMargins(0, 0, 0, 0)
            holder_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            holder_layout.addWidget(checkbox)
            self.plugin_table.setCellWidget(index, 0, holder)
            extensions = ", ".join(spec.extension for spec in plugin.formats)
            self.plugin_table.setItem(index, 1, self._text_item(plugin.name))
            self.plugin_table.setItem(index, 2, self._text_item(plugin.plugin_id))
            self.plugin_table.setItem(index, 3, self._text_item(plugin.manifest.version))
            self.plugin_table.setItem(index, 4, self._text_item(self._plugin_kind_label(plugin)))
            self.plugin_table.setItem(index, 5, self._text_item(extensions))
            if plugin.error:
                status = get_text("ui.plugin_status_error").format(error=plugin.error)
                self.plugin_table.setItem(index, 6, self._text_item(status))
                self._set_dash_cells(index, "settings", "license")
            else:
                self.plugin_table.setItem(index, 6, self._text_item(get_text("ui.plugin_status_ok")))
                self._set_action_cells(index, plugin)
        for offset, item in enumerate(skipped):
            index = len(rows) + offset
            if item.reason == "duplicate":
                status = get_text("ui.plugin_status_duplicate").format(
                    selected=item.selected_name or "-"
                )
            else:
                status = get_text("ui.plugin_status_not_selected")
            display_name = item.name or item.path.name
            if item.path.name and item.path.name != display_name:
                display_name = f"{display_name} ({item.path.name})"
            self.plugin_table.setItem(index, 0, self._text_item("-"))
            self.plugin_table.setItem(index, 1, self._text_item(display_name))
            self.plugin_table.setItem(index, 2, self._text_item(item.plugin_id or "-"))
            self.plugin_table.setItem(index, 3, self._text_item(item.version or "-"))
            self.plugin_table.setItem(index, 4, self._text_item("-"))
            self.plugin_table.setItem(index, 5, self._text_item("-"))
            self.plugin_table.setItem(index, 6, self._text_item(status))
            self._set_dash_cells(index, "settings", "license")
        for offset, (path, error) in enumerate(failed):
            index = len(rows) + len(skipped) + offset
            status = get_text("ui.plugin_status_error").format(error=error)
            self.plugin_table.setItem(index, 0, self._text_item("-"))
            self.plugin_table.setItem(index, 1, self._text_item(path.name))
            self.plugin_table.setItem(index, 2, self._text_item("-"))
            self.plugin_table.setItem(index, 3, self._text_item("-"))
            self.plugin_table.setItem(index, 4, self._text_item("-"))
            self.plugin_table.setItem(index, 5, self._text_item("-"))
            self.plugin_table.setItem(index, 6, self._text_item(status))
            self._set_dash_cells(index, "settings", "license")
        if self.plugin_table.rowCount() == 0:
            self.plugin_table.setRowCount(1)
            empty = self._text_item(get_text("ui.plugin_no_plugins"))
            self.plugin_table.setItem(0, 0, empty)
            self.plugin_table.setSpan(0, 0, 1, len(PLUGIN_COLUMNS))
            self.plugin_table.setSortingEnabled(False)
            return
        self.plugin_table.resizeRowsToContents()
        self.plugin_table.setSortingEnabled(True)

    def _column(self, key: str) -> int:
        return PLUGIN_COLUMNS.index(key)

    def _set_dash_cells(self, index: int, *keys: str):
        for key in keys:
            self.plugin_table.setItem(index, self._column(key), self._text_item("-"))

    def _set_action_cells(self, index: int, plugin):
        from ez_co.plugins.zip_loader import peek_license

        fields = self.plugin_manager.host.configs_for(plugin.plugin_id)
        license_info = peek_license(plugin.zip_path)
        if fields:
            button = QPushButton(get_text("ui.settings"))
            button.clicked.connect(lambda _=False, item=plugin: self._open_plugin_config(item))
            self._set_button_cell(index, "settings", button)
        else:
            self._set_dash_cells(index, "settings")
        if license_info:
            license_button = QPushButton(get_text("ui.about_license"))
            license_button.clicked.connect(
                lambda _=False, item=plugin, info=license_info: self._open_plugin_license(item, info)
            )
            self._set_button_cell(index, "license", license_button)
        else:
            self._set_dash_cells(index, "license")

    def _set_button_cell(self, index: int, key: str, button: QPushButton):
        button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        hint = button.sizeHint()
        button.setMinimumSize(hint)
        button.setFixedHeight(hint.height())
        holder = QWidget()
        holder_layout = QHBoxLayout(holder)
        holder_layout.setContentsMargins(4, 2, 4, 2)
        holder_layout.addWidget(button)
        holder_layout.addStretch()
        self.plugin_table.setCellWidget(index, self._column(key), holder)

    def _open_plugin_license(self, plugin, info):
        from ez_co.ui.plugins.plugin_license_dialog import PluginLicenseDialog

        dialog = PluginLicenseDialog(
            plugin.name,
            info.get("kind") or "text",
            info.get("text") or "",
            self,
        )
        dialog.exec()

    def _open_plugin_config(self, plugin):
        from ez_co.ui.plugins.plugin_config_dialog import PluginConfigDialog

        dialog = PluginConfigDialog(
            self.plugin_manager.host,
            plugin.plugin_id,
            plugin.name,
            self,
        )
        dialog.exec()

    def _on_enabled_changed(self, plugin_id: str, checked: bool):
        self._enabled[plugin_id] = bool(checked)
        self._refresh_extension_rows()

    def _fallback_provider(self, row) -> str:
        valid = [provider_id for provider_id, _name in row.providers]
        if BUILTIN_PROVIDER_ID in valid:
            return BUILTIN_PROVIDER_ID
        for provider_id in valid:
            if provider_id != SKIP_PROVIDER_ID:
                return provider_id
        if SKIP_PROVIDER_ID in valid:
            return SKIP_PROVIDER_ID
        return valid[0] if valid else SKIP_PROVIDER_ID

    def _refresh_extension_rows(self):
        new_rows = self.plugin_manager.extension_rows(self.config, enabled_ids=self._enabled_ids())
        new_exts = {row.extension for row in new_rows}
        old_exts = {row.extension for row in self._ext_rows}
        for extension in old_exts - new_exts:
            if extension in self._handler_choices:
                self._handler_stash[extension] = self._handler_choices.pop(extension)
        for row in new_rows:
            selected = self._handler_choices.get(row.extension)
            if selected is None and row.extension in self._handler_stash:
                selected = self._handler_stash.pop(row.extension)
            valid = {provider_id for provider_id, _name in row.providers}
            if selected not in valid:
                selected = self._fallback_provider(row)
            self._handler_choices[row.extension] = selected
        self._ext_rows = new_rows
        self._render_extension_table()

    def _kind_label(self, kind: FileKind) -> str:
        if kind == FileKind.IMAGE:
            return get_text("ui.plugin_kind_image")
        return get_text("ui.plugin_kind_archive")

    def _provider_label(self, provider_id: str, plugin_name: str) -> str:
        if provider_id == BUILTIN_PROVIDER_ID:
            return get_text("ui.plugin_handler_builtin")
        if provider_id == SKIP_PROVIDER_ID:
            return get_text("ui.plugin_conflict_skip")
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
        self.ext_table.clearSpans()
        self.ext_table.setRowCount(len(rows))
        if not rows:
            self.ext_table.setRowCount(1)
            empty = self._text_item(get_text("ui.plugin_filter_empty"))
            self.ext_table.setItem(0, 0, empty)
            self.ext_table.setSpan(0, 0, 1, 3)
            return
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
        return self._handler_choices != self._original_handlers

    def has_enabled_changes(self) -> bool:
        return self._enabled != self._original_enabled

    def has_source_choice_changes(self) -> bool:
        return self._source_choices != self._original_source_choices

    def has_changes(self) -> bool:
        return (
            self.has_handler_changes()
            or self.has_enabled_changes()
            or self.has_source_choice_changes()
        )

    def _open_conflict_dialog(self):
        groups = self.plugin_manager.conflict_groups()
        if not groups:
            QMessageBox.information(
                self,
                get_text("ui.plugin_conflict_title"),
                get_text("ui.plugin_conflict_none"),
            )
            return
        from ez_co.ui.plugins.plugin_conflict_dialog import PluginConflictDialog

        dialog = PluginConflictDialog(groups, self, initial=self._source_choices)
        dialog.exec()
        self._source_choices.update(dialog.choices())

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
        self.config.plugins["enabled"] = dict(self._enabled)
        if self._source_choices:
            self.plugin_manager.record_choices(self._source_choices, self.config)
        for key, enabled in archive_enabled_by_key.items():
            self.config.archive[key] = enabled
        if archive_enabled_by_key:
            self.config.archive["enabled"] = any(archive_enabled_by_key.values())
