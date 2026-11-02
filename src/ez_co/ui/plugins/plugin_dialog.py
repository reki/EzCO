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

# プラグイン一覧の列キー。
PLUGIN_COLUMNS = ("enabled", "name", "id", "version", "description", "kind", "extensions", "status", "settings", "license")
# プラグイン一覧の列キーと、見出しの言語キー。
PLUGIN_HEADER_KEYS = {
    "enabled": "ui.plugin_enabled",
    "name": "ui.plugin_name",
    "id": "ui.plugin_id",
    "version": "ui.version",
    "description": "ui.plugin_description",
    "kind": "ui.plugin_kind",
    "extensions": "ui.plugin_supported_extensions",
    "status": "ui.plugin_status",
    "settings": "ui.settings",
    "license": "ui.about_license",
}
# プラグイン一覧の初期列幅。
PLUGIN_DEFAULT_WIDTHS = {
    "enabled": 56,
    "name": 160,
    "id": 200,
    "version": 72,
    "description": 220,
    "kind": 90,
    "extensions": 90,
    "status": 220,
    "settings": 100,
    "license": 110,
}
# プラグイン一覧でこれより狭くしない列幅。
PLUGIN_MIN_WIDTHS = {
    "settings": 88,
    "license": 100,
}
# 拡張子一覧の列キー。
EXT_COLUMNS = ("extension", "kind", "handler")
# 拡張子一覧の初期列幅。
EXT_DEFAULT_WIDTHS = {
    "extension": 100,
    "kind": 110,
    "handler": 280,
}


class NoWheelComboBox(QComboBox):
    """閉じているときはホイールで値を変えず、親の一覧をスクロールさせる。"""

    def wheelEvent(self, event):
        """一覧が開いているときだけ自分でホイールを処理し、閉じているときは親のスクロールへ渡す。

        Args:
            event: ホイールイベント。
        """
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
    """プラグインの有効、拡張子の読み込み方式、重複の提供元を選ぶ。"""
    applied = Signal()

    def __init__(self, config, parent=None):
        """有効、拡張子の方式、提供元の選択を控えて画面を出す。

        Args:
            config: プラグイン設定を持つ設定。
            parent: 親ウィジェット。
        """
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
        """有効なプラグイン ID を返す。

        Returns:
            有効な ID の集合。
        """
        return {plugin_id for plugin_id, enabled in self._enabled.items() if enabled}

    def _setup_ui(self):
        """プラグイン表、拡張子の絞り込み、拡張子表を配置する。"""
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
            get_text(PLUGIN_HEADER_KEYS[key]) for key in PLUGIN_COLUMNS
        ])
        self._prepare_table(self.plugin_table)
        self.plugin_table.cellClicked.connect(self._on_plugin_cell_clicked)
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
        """変更が無ければ何もしない。あれば設定へ書き、元の値を更新する。提供元が変わっていれば表を読み直す。"""
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
        """列の幅変更と行選択だけができる表にする。

        Args:
            table: 整える表。
        """
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
        """保存された表レイアウトを返す。

        Args:
            key: 表のキー。

        Returns:
            そのキーの辞書。無ければ空。
        """
        dialog = self.config.plugins.get("dialog") or {}
        if not isinstance(dialog, dict):
            return {}
        state = dialog.get(key) or {}
        return state if isinstance(state, dict) else {}

    def _restore_table_layout(self, table: QTableWidget, keys, default_widths, state_key: str):
        """保存された幅と列順を表へ戻す。保存に無い列は、既定順で直前にある列の次へ入れる。

        Args:
            table: 戻す表。
            keys: 列のキー。
            default_widths: 保存が無いときの幅。
            state_key: 保存されたレイアウトのキー。
        """
        state = self._dialog_table_state(state_key)
        widths = dict(default_widths)
        saved_widths = state.get("widths") or {}
        if isinstance(saved_widths, dict):
            for key, value in saved_widths.items():
                if key in default_widths:
                    try:
                        widths[key] = max(PLUGIN_MIN_WIDTHS.get(key, 48), int(value))
                    except (TypeError, ValueError):
                        # 保存された列幅が整数でないときは捨てて、既定幅のままにする。
                        pass
        for logical, key in enumerate(keys):
            table.setColumnWidth(logical, widths[key])

        order = [key for key in (state.get("order") or []) if key in keys]
        for key in keys:
            if key in order:
                continue
            earlier = keys[:keys.index(key)]
            anchor = next((item for item in reversed(earlier) if item in order), None)
            if anchor is None:
                order.insert(0, key)
            else:
                order.insert(order.index(anchor) + 1, key)
        header = table.horizontalHeader()
        for visual, key in enumerate(order):
            logical = keys.index(key)
            current = header.visualIndex(logical)
            if current != visual:
                header.moveSection(current, visual)

    def _table_layout(self, table: QTableWidget, keys) -> dict:
        """いまの列順と幅を返す。

        Args:
            table: 読む表。
            keys: 列のキー。

        Returns:
            order と widths を持つ辞書。
        """
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
        """プラグイン表と拡張子表の列順と幅を設定へ書く。"""
        dialog = dict(self.config.plugins.get("dialog") or {})
        dialog["plugin_table"] = self._table_layout(self.plugin_table, PLUGIN_COLUMNS)
        dialog["ext_table"] = self._table_layout(self.ext_table, EXT_COLUMNS)
        self.config.plugins["dialog"] = dialog

    def _text_item(self, text: str) -> QTableWidgetItem:
        """同じ文字をツールチップにしたセルを返す。

        Args:
            text: セルの文字。

        Returns:
            そのセル。
        """
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        return item

    def _plugin_kind_label(self, plugin) -> str:
        """ファイル、サイドバー、両方のどれかを返す。

        Args:
            plugin: 種類を見るプラグイン。

        Returns:
            種類の表示文。
        """
        has_file = bool(plugin.formats)
        has_sidebar = plugin.has_sidebar
        if has_file and has_sidebar:
            return get_text("ui.plugin_kind_both")
        if has_sidebar:
            return get_text("ui.plugin_kind_sidebar")
        return get_text("ui.plugin_kind_file")

    def _fill_plugin_table(self):
        """読み込めたプラグイン、読み飛ばし、失敗を表に出す。"""
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
            self.plugin_table.setCellWidget(index, self._column("enabled"), holder)
            extensions = ", ".join(spec.extension for spec in plugin.formats)
            name_item = self._text_item(plugin.name)
            name_item.setData(Qt.ItemDataRole.UserRole, plugin.plugin_id)
            self.plugin_table.setItem(index, self._column("name"), name_item)
            self.plugin_table.setItem(index, self._column("id"), self._text_item(plugin.plugin_id))
            self.plugin_table.setItem(index, self._column("version"), self._text_item(plugin.manifest.version))
            self.plugin_table.setItem(
                index, self._column("description"), self._text_item(plugin.manifest.description or "")
            )
            self.plugin_table.setItem(index, self._column("kind"), self._text_item(self._plugin_kind_label(plugin)))
            self.plugin_table.setItem(index, self._column("extensions"), self._text_item(extensions))
            if plugin.error:
                status = get_text("ui.plugin_status_error").format(error=plugin.error)
                self.plugin_table.setItem(index, self._column("status"), self._text_item(status))
                self._set_dash_cells(index, "settings", "license")
            else:
                self.plugin_table.setItem(
                    index, self._column("status"), self._text_item(get_text("ui.plugin_status_ok"))
                )
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
            self.plugin_table.setItem(index, self._column("enabled"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("name"), self._text_item(display_name))
            self.plugin_table.setItem(index, self._column("id"), self._text_item(item.plugin_id or "-"))
            self.plugin_table.setItem(index, self._column("version"), self._text_item(item.version or "-"))
            self.plugin_table.setItem(index, self._column("description"), self._text_item(item.description or ""))
            self.plugin_table.setItem(index, self._column("kind"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("extensions"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("status"), self._text_item(status))
            self._set_dash_cells(index, "settings", "license")
        for offset, (path, error) in enumerate(failed):
            index = len(rows) + len(skipped) + offset
            status = get_text("ui.plugin_status_error").format(error=error)
            self.plugin_table.setItem(index, self._column("enabled"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("name"), self._text_item(path.name))
            self.plugin_table.setItem(index, self._column("id"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("version"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("description"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("kind"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("extensions"), self._text_item("-"))
            self.plugin_table.setItem(index, self._column("status"), self._text_item(status))
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

    def _on_plugin_cell_clicked(self, row: int, column: int):
        """設定項目がある行なら、ライセンスと有効以外のクリックで設定を開く。

        Args:
            row: 行番号。
            column: 列番号。
        """
        if column in (self._column("license"), self._column("enabled")):
            return
        item = self.plugin_table.item(row, self._column("name"))
        if item is None:
            return
        plugin_id = item.data(Qt.ItemDataRole.UserRole)
        if not plugin_id:
            return
        plugin = next(
            (entry for entry in self.plugin_manager.plugins if entry.plugin_id == plugin_id),
            None,
        )
        if plugin is None or plugin.error:
            return
        if not self.plugin_manager.host.configs_for(plugin.plugin_id):
            return
        self._open_plugin_config(plugin)

    def _column(self, key: str) -> int:
        """列キーの番号を返す。

        Args:
            key: 列のキー。

        Returns:
            列番号。
        """
        return PLUGIN_COLUMNS.index(key)

    def _set_dash_cells(self, index: int, *keys: str):
        """指定列をハイフンにする。

        Args:
            index: 行番号。
            keys: ハイフンにする列のキー。
        """
        for key in keys:
            self.plugin_table.setItem(index, self._column(key), self._text_item("-"))

    def _set_action_cells(self, index: int, plugin):
        """設定とライセンスのボタンを置く。無い列はハイフンにする。

        Args:
            index: 行番号。
            plugin: その行のプラグイン。
        """
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
        """ボタンを列の中に置く。

        Args:
            index: 行番号。
            key: 列のキー。
            button: 置くボタン。
        """
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
        """LICENSE のダイアログを出す。

        Args:
            plugin: 表示するプラグイン。
            info: kind と text を持つライセンス情報。
        """
        from ez_co.ui.plugins.plugin_license_dialog import PluginLicenseDialog

        dialog = PluginLicenseDialog(
            plugin.name,
            info.get("kind") or "text",
            info.get("text") or "",
            self,
        )
        dialog.exec()

    def _open_plugin_config(self, plugin):
        """プラグイン設定のダイアログを出す。

        Args:
            plugin: 設定するプラグイン。
        """
        from ez_co.ui.plugins.plugin_config_dialog import PluginConfigDialog

        dialog = PluginConfigDialog(
            self.plugin_manager.host,
            plugin.plugin_id,
            plugin.name,
            self,
        )
        dialog.exec()

    def _on_enabled_changed(self, plugin_id: str, checked: bool):
        """有効を更新し、拡張子の行を読み直す。

        Args:
            plugin_id: 変わったプラグイン。
            checked: 有効にするとき True。
        """
        self._enabled[plugin_id] = bool(checked)
        self._refresh_extension_rows()

    def _fallback_provider(self, row) -> str:
        """ビルトイン、それ以外、スキップの順で残す提供元を返す。

        Args:
            row: 拡張子の行。

        Returns:
            残す提供元。候補が無ければ None。
        """
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
        """有効なプラグインに合わせて拡張子の行と選択を組み直す。消えた選択は控える。"""
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
        """画像かアーカイブの表示を返す。

        Args:
            kind: ファイルの種類。

        Returns:
            種類の表示文。
        """
        if kind == FileKind.IMAGE:
            return get_text("ui.plugin_kind_image")
        return get_text("ui.plugin_kind_archive")

    def _provider_label(self, provider_id: str, plugin_name: str) -> str:
        """ビルトイン、スキップ、または名前と ID の表示を返す。

        Args:
            provider_id: 提供元の ID。
            plugin_name: プラグイン名。空でもよい。

        Returns:
            表示文。
        """
        if provider_id == BUILTIN_PROVIDER_ID:
            return get_text("ui.plugin_handler_builtin")
        if provider_id == SKIP_PROVIDER_ID:
            return get_text("ui.plugin_conflict_skip")
        if plugin_name:
            return f"{plugin_name} ({provider_id})"
        return provider_id or ""

    def _on_ext_header_clicked(self, column: int):
        """同じ列なら昇降を反転し、別の列なら昇順で並べ直す。

        Args:
            column: クリックされた列。
        """
        if column == self._ext_sort_column:
            self._ext_sort_asc = not self._ext_sort_asc
        else:
            self._ext_sort_column = column
            self._ext_sort_asc = True
        self._render_extension_table()

    def _visible_ext_rows(self):
        """絞り込みと並びを適用した拡張子の行を返す。

        Returns:
            表示する行。
        """
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
            """いまの並び列に応じた比較用の文字列を返す。

            Args:
                row: 拡張子の行。

            Returns:
                種類、提供元、または拡張子の文字列。
            """
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
        """見える拡張子の行を表に出す。無ければ空の文言を出す。"""
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
        """選ばれた提供元を控え、ツールチップを更新する。

        Args:
            extension: 変わった拡張子。
            combo: 提供元の選択。
        """
        combo.setToolTip(combo.currentText())
        provider_id = combo.currentData()
        if provider_id:
            self._handler_choices[extension] = provider_id

    def has_handler_changes(self) -> bool:
        """拡張子の読み込み方式に変更があるかを返す。

        Returns:
            変更があるとき True。
        """
        return self._handler_choices != self._original_handlers

    def has_enabled_changes(self) -> bool:
        """プラグインの有効に変更があるかを返す。

        Returns:
            変更があるとき True。
        """
        return self._enabled != self._original_enabled

    def has_source_choice_changes(self) -> bool:
        """重複の提供元に変更があるかを返す。

        Returns:
            変更があるとき True。
        """
        return self._source_choices != self._original_source_choices

    def has_changes(self) -> bool:
        """方式、有効、提供元のいずれかに変更があるかを返す。

        Returns:
            変更があるとき True。
        """
        return (
            self.has_handler_changes()
            or self.has_enabled_changes()
            or self.has_source_choice_changes()
        )

    def _open_conflict_dialog(self):
        """重複が無ければその旨を出す。あれば選ばせて提供元の選択を更新する。"""
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
        """拡張子の方式、有効、提供元、アーカイブの有効を設定へ書く。"""
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
