"""起動時のプラグイン ID 重複選択。OK 以外では閉じない。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ez_co.plugins.api import SKIP_PROVIDER_ID
from ez_co.plugins.manager import PluginCandidate, sort_conflict_candidates
from ez_co.utils.language_manager import get_text


class NoWheelComboBox(QComboBox):
    """一覧が開いていないときのホイールは、親のスクロールへ渡す。"""

    def wheelEvent(self, event):
        """一覧が開いているときだけ自分でホイールを処理し、閉じているときは親のスクロール領域へ渡す。

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


class PluginConflictDialog(QDialog):
    """同じプラグイン ID の候補から、使う提供元を選ぶ。"""

    def __init__(self, groups: dict[str, list[PluginCandidate]], parent=None, initial=None):
        """重複グループと初期選択でダイアログを組み立てる。閉じるボタンは出さない。

        Args:
            groups: プラグイン ID ごとの候補。
            parent: 親ウィジェット。
            initial: プラグイン ID から、初期選択のファイル名またはスキップ。
        """
        super().__init__(parent)
        self._groups = {
            plugin_id: sort_conflict_candidates(list(items))
            for plugin_id, items in groups.items()
        }
        self._initial = dict(initial or {})
        self._combos: dict[str, QComboBox] = {}
        self._can_close = False
        self.setWindowTitle(get_text("ui.plugin_conflict_title"))
        self.setMinimumSize(560, 280)
        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowCloseButtonHint
        flags &= ~Qt.WindowType.WindowContextHelpButtonHint
        self.setWindowFlags(flags)
        self._setup_ui()

    def _setup_ui(self):
        """説明、候補の表、OK ボタンを配置する。"""
        layout = QVBoxLayout(self)
        message = QLabel(get_text("ui.plugin_conflict_message"))
        message.setWordWrap(True)
        layout.addWidget(message)

        rows = list(self._groups.items())
        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels([
            get_text("ui.plugin_id"),
            get_text("ui.plugin_conflict_source"),
        ])
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        skip_label = get_text("ui.plugin_conflict_skip")
        for index, (plugin_id, items) in enumerate(rows):
            id_item = QTableWidgetItem(plugin_id)
            id_item.setToolTip(plugin_id)
            table.setItem(index, 0, id_item)
            combo = NoWheelComboBox()
            for item in items:
                label = get_text("ui.plugin_conflict_option").format(
                    filename=item.path.name,
                    version=item.version or "-",
                )
                combo.addItem(label, item.path.name)
                combo.setItemData(combo.count() - 1, label, Qt.ItemDataRole.ToolTipRole)
            combo.addItem(skip_label, SKIP_PROVIDER_ID)
            combo.setItemData(combo.count() - 1, skip_label, Qt.ItemDataRole.ToolTipRole)
            selected = self._initial.get(plugin_id)
            selected_index = combo.findData(selected) if selected else -1
            combo.setCurrentIndex(selected_index if selected_index >= 0 else 0)
            combo.setToolTip(combo.currentText())
            combo.currentIndexChanged.connect(
                lambda _i, widget=combo: widget.setToolTip(widget.currentText())
            )
            table.setCellWidget(index, 1, combo)
            self._combos[plugin_id] = combo
        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        escape = getattr(buttons, "setEscapeButton", None)
        if callable(escape):
            escape(None)
        layout.addWidget(buttons)

    def choices(self) -> dict[str, str]:
        """各プラグイン ID の選択を返す。

        Returns:
            プラグイン ID から、ファイル名またはスキップ ID。
        """
        result = {}
        for plugin_id, combo in self._combos.items():
            value = combo.currentData()
            result[plugin_id] = str(value or SKIP_PROVIDER_ID)
        return result

    def accept(self):
        """OK のときだけ閉じられるようにして確定する。"""
        self._can_close = True
        super().accept()

    def reject(self):
        """OK で閉じてよいときだけ拒否を親へ渡す。"""
        if self._can_close:
            super().reject()

    def closeEvent(self, event):
        """OK で閉じてよいときだけ閉じる。

        Args:
            event: 閉じるイベント。
        """
        if self._can_close:
            event.accept()
            return
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        """Esc では閉じない。

        Args:
            event: キーイベント。
        """
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)
