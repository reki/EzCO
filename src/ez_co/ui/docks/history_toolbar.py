"""閲覧履歴の一覧サイドバー。"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QFrame, QLabel, QMessageBox, QScrollArea, QSizePolicy, QMenu, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QTimer, QEvent
from PySide6.QtGui import QFont, QIcon, QAction
from ez_co.utils.database import DatabaseManager
from ez_co.handlers.virtual_path_handler import VirtualPathHandler
from ez_co.enums.archives import ArchiveInfo
from ez_co.enums.entry_types import EntryType
from ez_co.utils.language_manager import get_text, get_log_text
logger = logging.getLogger(__name__)
class HistoryToolbar(QWidget):
    """履歴ツールバー"""
    history_selected = Signal(str, int, bool)  # file_path, page_number, new_tab
    def __init__(self, db_manager: DatabaseManager, parent=None):
        """履歴一覧を作り、2秒ごとに更新する。

        Args:
            db_manager: 履歴を読むデータベース。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.db_manager = db_manager
        # 自動更新用タイマー
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_history)
        self.auto_refresh_timer.start(2000)  # 2秒ごとに更新
        logger.info(get_log_text("history_toolbar_initialized"))
        self.setup_ui()
        self.refresh_history()

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.history"))
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        # フォーカスポリシーを設定（フォーカスを奪わないように）
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        # タイトル
        title_label = QLabel(get_text("ui.history"))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        # 履歴リスト
        self.history_list = QListWidget()
        self.history_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_list.customContextMenuRequested.connect(self.show_context_menu)
        self.history_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.history_list.itemClicked.connect(self.on_history_clicked)
        self.history_list.viewport().installEventFilter(self)
        layout.addWidget(self.history_list)
        # ボタンレイアウト
        button_layout = QHBoxLayout()
        # クリアボタン
        self.clear_button = QPushButton(get_text("ui.history_clear"))
        self.clear_button.clicked.connect(self.clear_history)
        button_layout.addWidget(self.clear_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        # サイズポリシーを設定
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def refresh_history(self):
        """履歴一覧を更新"""
        try:
            self.history_list.clear()
            history = self.db_manager.get_history(limit=20)
            # logger.info(get_log_text("debug_history_refresh_start", total_entries=len(history)))
            for entry in history:
                file_path = entry['file_path']
                page_number = entry['page_number']
                title = entry.get('title', Path(file_path).name)
                entry_type = entry.get('entry_type', EntryType.FILE.value)
                # ファイルが存在するかチェック
                if not self._check_file_exists(file_path):
                    title += f" {get_text('ui.deleted_file')}"
                # リストアイテムを作成
                item_text = f"{title} - ページ {page_number}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, (file_path, page_number, entry_type))
                # 削除済みファイルの場合は色を変更
                if not self._check_file_exists(file_path):
                    item.setForeground(Qt.GlobalColor.gray)
                self.history_list.addItem(item)
            # logger.info(get_log_text("history_refreshed", count=len(history)))
        except Exception as e:
            # 履歴の読み込みに失敗したらログして、一覧の更新をやめる。
            logger.error(get_log_text("history_refresh_error", error=str(e)))

    def _check_file_exists(self, file_path: str) -> bool:
        """ファイルの存在確認（アーカイブファイルやフォルダも含む）

        Args:
            file_path: 確認するパス。仮想パスのときはアーカイブ側を見る。

        Returns:
            存在するとき True。
        """
        if VirtualPathHandler.is_virtual_path(file_path):
            result = VirtualPathHandler.parse_virtual_path(file_path)
            if result:
                archive_path, _ = result
                exists = archive_path.exists()
                # logger.debug(get_log_text("debug_history_virtual_path_check", file_path=file_path, archive_path=archive_path, exists=exists))
                return exists
            else:
                # logger.debug(get_log_text("debug_history_file_exists_check", file_path=file_path, exists=False))
                return False
        path = Path(file_path)
        if path.exists():
            # logger.debug(get_log_text("debug_history_file_exists_check", file_path=file_path, exists=True))
            return True
        if ArchiveInfo.is_archive_file(file_path):
            exists = path.exists()
            # logger.debug(get_log_text("debug_history_file_exists_check", file_path=file_path, exists=exists))
            return exists
        # logger.debug(get_log_text("debug_history_file_exists_check", file_path=file_path, exists=False))
        return False

    def clear_history(self):
        """履歴をクリア"""
        reply = QMessageBox.question(
            self, get_text("dialogs.question"),
            get_text("ui.history_clear_confirm"),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.db_manager.clear_history()
            if success:
                logger.info(get_log_text("history_cleared_success_log"))
                self.refresh_history()
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.history_clear_success"))
            else:
                logger.error(get_log_text("history_cleared_failed_log"))
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.history_clear_failed"))

    def eventFilter(self, obj, event):
        """一覧上の中ボタンで、その履歴を新しいタブで開く。

        Args:
            obj: イベントの対象。
            event: 受け取ったイベント。

        Returns:
            中ボタンが項目に当たったとき True。それ以外は親の結果。
        """
        if obj is self.history_list.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                item = self.history_list.itemAt(event.position().toPoint())
                if item is not None:
                    self._open_history_item(item, new_tab=True)
                    return True
        return super().eventFilter(obj, event)

    def _open_history_item(self, item, new_tab: bool):
        """履歴項目を開く。ファイルが無ければ警告して開かない。

        Args:
            item: 履歴の一覧項目。
            new_tab: 新しいタブで開くとき True。
        """
        entry = item.data(Qt.ItemDataRole.UserRole)
        file_path = entry[0]
        logger.info(get_log_text("history_item_clicked", file_path=file_path, page_number=entry[1]))
        if not self._check_file_exists(file_path):
            QMessageBox.warning(self, get_text("dialogs.error"), f"{get_text('dialogs.file_not_found')}\n{file_path}")
            return
        self.history_selected.emit(file_path, entry[1], new_tab)

    def on_history_clicked(self, item):
        """履歴をクリックした時の処理

        Args:
            item: クリックされた項目。Ctrl のときは新しいタブで開く。
        """
        new_tab = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        self._open_history_item(item, new_tab)

    def on_item_double_clicked(self, item):
        """履歴をダブルクリックした時の処理

        Args:
            item: ダブルクリックされた項目。
        """
        self.on_history_clicked(item)

    def show_context_menu(self, pos):
        """コンテキストメニューを表示

        Args:
            pos: 一覧上の位置。
        """
        item = self.history_list.itemAt(pos)
        if item:
            entry = item.data(Qt.ItemDataRole.UserRole)
            menu = QMenu(self)
            open_current = QAction(get_text("ui.open_in_current_tab"), self)
            open_current.triggered.connect(lambda: self.history_selected.emit(entry[0], entry[1], False))
            menu.addAction(open_current)
            open_new = QAction(get_text("ui.open_in_new_tab"), self)
            open_new.triggered.connect(lambda: self.history_selected.emit(entry[0], entry[1], True))
            menu.addAction(open_new)
            menu.addSeparator()
            delete_action = QAction(get_text("ui.delete"), self)
            delete_action.triggered.connect(lambda: self.delete_history_item(item))
            menu.addAction(delete_action)
            menu.exec(self.history_list.mapToGlobal(pos))

    def delete_history_item(self, item):
        """履歴アイテムを削除

        Args:
            item: 消す履歴項目。
        """
        entry = item.data(Qt.ItemDataRole.UserRole)
        file_path = entry[0]
        entry_type = entry[2]
        reply = QMessageBox.question(
            self, get_text("dialogs.question"),
            get_text("ui.history_delete_confirm").format(file_path=file_path),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.db_manager.delete_history_item(file_path, entry[1], entry_type)
            if success:
                logger.info(get_log_text("history_item_deleted_success_log", file_path=file_path))
                self.refresh_history()
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.history_delete_success").format(file_path=file_path))
            else:
                logger.error(get_log_text("history_item_deleted_failed_log", file_path=file_path))
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.history_delete_failed").format(file_path=file_path))
