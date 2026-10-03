"""ブックマークのフォルダ一覧サイドバー。"""
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QFrame, QLabel, QMessageBox, QScrollArea, QSizePolicy, QMenu, QInputDialog,
    QTreeWidget, QTreeWidgetItem, QComboBox
)
from PySide6.QtCore import Qt, Signal, QTimer, QMimeData, QEvent
from PySide6.QtGui import QFont, QIcon, QDrag
from ez_co.utils.database import DatabaseManager
from ez_co.ui.dialogs.bookmark_dialog import BookmarkDialog
from ez_co.handlers.virtual_path_handler import VirtualPathHandler
from ez_co.utils.language_manager import get_text, get_log_text
from ez_co.enums.entry_types import EntryType
import os
logger = logging.getLogger(__name__)
class BookmarkToolbar(QWidget):
    """ブックマークツールバー"""
    bookmark_selected = Signal(str, int, bool)  # file_path, page_number, new_tab
    def __init__(self, parent=None, config=None, db_manager=None):
        """ブックマーク一覧を作り、2秒ごとに更新する。データベースが無ければ config から作る。

        Args:
            parent: 親ウィジェット。
            config: データベースを自前で作るときに使う設定。
            db_manager: ブックマークのデータベース。
        """
        super().__init__(parent)
        if db_manager is not None:
            self.db_manager = db_manager
        else:
            self.db_manager = DatabaseManager(config)
        self.current_file = None
        self.current_page = 1
        self.current_folder_id = 0
        self.folder_stack = [0]  # フォルダの履歴（ナビゲーション用）
        # 自動更新用タイマー
        self.auto_refresh_timer = QTimer()
        self.auto_refresh_timer.timeout.connect(self.refresh_bookmarks)
        self.auto_refresh_timer.start(2000)  # 2秒ごとに更新
        self.setup_ui()
        self.refresh_bookmarks()

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.bookmarks"))
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        # フォーカスポリシーを設定（フォーカスを奪わないように）
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        # タイトル
        title_label = QLabel(get_text("ui.bookmarks"))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        # 現在のフォルダ表示
        self.current_folder_label = QLabel(get_text("ui.root_folder"))
        self.current_folder_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_folder_label)
        # ボタンレイアウト
        button_layout = QHBoxLayout()
        # 戻るボタン
        self.back_button = QPushButton("←")
        self.back_button.setMaximumWidth(30)
        self.back_button.clicked.connect(self.go_back)
        button_layout.addWidget(self.back_button)
        # 新規フォルダボタン
        self.new_folder_button = QPushButton("📁")
        self.new_folder_button.setMaximumWidth(30)
        self.new_folder_button.clicked.connect(self.create_new_folder)
        button_layout.addWidget(self.new_folder_button)
        # ブックマーク追加ボタン
        self.add_bookmark_button = QPushButton("+")
        self.add_bookmark_button.setMaximumWidth(30)
        self.add_bookmark_button.clicked.connect(self.show_bookmark_dialog)
        button_layout.addWidget(self.add_bookmark_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        # 区切り線
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        # スクロールエリア
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        # ブックマークリスト（フォルダとブックマークを混在表示）
        self.bookmark_list = QListWidget()
        self.bookmark_list.setFocusPolicy(Qt.NoFocus)  # フォーカスを奪わないように
        self.bookmark_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.bookmark_list.itemClicked.connect(self.on_item_clicked)
        self.bookmark_list.viewport().installEventFilter(self)
        self.bookmark_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bookmark_list.customContextMenuRequested.connect(self.show_context_menu)
        self.bookmark_list.setDragDropMode(QListWidget.InternalMove)
        self.bookmark_list.model().rowsMoved.connect(self.on_items_moved)
        scroll_area.setWidget(self.bookmark_list)
        layout.addWidget(scroll_area)
        # サイズポリシーを設定
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        # 初期状態で戻るボタンを無効化
        self.back_button.setEnabled(False)

    def go_back(self):
        """前のフォルダに戻る"""
        if len(self.folder_stack) > 1:
            self.folder_stack.pop()  # 現在のフォルダを削除
            self.current_folder_id = self.folder_stack[-1]  # 前のフォルダに設定
            self.refresh_bookmarks()
            self.back_button.setEnabled(len(self.folder_stack) > 1)

    def enter_folder(self, folder_id: int):
        """フォルダに入る

        Args:
            folder_id: 入るフォルダ。
        """
        self.folder_stack.append(folder_id)
        self.current_folder_id = folder_id
        self.refresh_bookmarks()
        self.back_button.setEnabled(len(self.folder_stack) > 1)

    def refresh_bookmarks(self):
        """ブックマーク一覧を更新（フォルダとブックマークを混在表示）"""
        self.bookmark_list.clear()
        # 現在のフォルダ名を更新
        if self.current_folder_id == 0:
            self.current_folder_label.setText(get_text("ui.root_folder"))
        else:
            folders = self.db_manager.get_bookmark_folders()
            folder_name = get_text("ui.unknown_folder")
            for folder in folders:
                if folder['id'] == self.current_folder_id:
                    folder_name = folder['name']
                    break
            self.current_folder_label.setText(f"📁 {folder_name}")
        # サブフォルダを表示
        folders = self.db_manager.get_bookmark_folders(self.current_folder_id)
        for folder in folders:
            item = QListWidgetItem(f"📁 {folder['name']}")
            item.setData(Qt.UserRole, {'type': 'folder', 'data': folder})
            self.bookmark_list.addItem(item)
        # ブックマークを表示
        bookmarks = self.db_manager.get_bookmarks(self.current_folder_id)
        for bookmark in bookmarks:
            file_path = bookmark['file_path']
            page_number = bookmark['page_number']
            title = bookmark['title'] or Path(file_path).name
            entry_type = bookmark.get('entry_type', EntryType.FILE.value)

            # 表示用のテキストを作成
            display_text = f"📄 {title}\nページ {page_number}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, {'type': 'bookmark', 'data': bookmark})
            # ファイルが存在しない場合はグレーアウト
            if not self._check_file_exists(file_path):
                item.setForeground(Qt.gray)
                display_text += f"\n{get_text('ui.deleted_file')}"
                item.setText(display_text)
            self.bookmark_list.addItem(item)

    def _check_file_exists(self, file_path: str) -> bool:
        """ファイルの存在確認（アーカイブファイルやフォルダも含む）

        Args:
            file_path: 確認するパス。仮想パスのときはアーカイブ本体を見る。

        Returns:
            存在するとき True。
        """
        from ez_co.handlers.virtual_path_handler import VirtualPathHandler
        import os
        # 仮想パス（archive://...）の場合はアーカイブ本体の存在のみチェック
        if VirtualPathHandler.is_virtual_path(file_path):
            result = VirtualPathHandler.parse_virtual_path(file_path)
            if result:
                archive_path, _ = result
                logger.info(get_log_text("debug_bmk_archive_path_type", archive_path_type=type(archive_path)))
                logger.info(get_log_text("debug_bmk_archive_path_str", archive_path_str=str(archive_path)))
                logger.info(get_log_text("debug_bmk_archive_path_absolute", archive_path_absolute=archive_path.absolute()))
                logger.info(get_log_text("debug_bmk_archive_path_resolve", archive_path_resolve=archive_path.resolve()))
                exists = archive_path.exists()
                logger.info(get_log_text("debug_bmk_check_file_exists_archive", file_path=file_path, exists=exists, archive_path=archive_path))
                return exists
            else:
                logger.warning(get_log_text("debug_bmk_invalid_virtual_path", file_path=file_path))
                return False
        # 通常ファイル・フォルダ
        exists = os.path.exists(file_path)
        logger.info(get_log_text("debug_bmk_check_file_exists", file_path=file_path, exists=exists))
        return exists

    def show_bookmark_dialog(self):
        """ブックマークダイアログを表示"""
        if not self.current_file:
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.no_current_file"))
            return
        dialog = BookmarkDialog(self, self.current_file, self.current_page, db_manager=self.db_manager)
        dialog.bookmark_selected.connect(self.on_bookmark_selected)
        dialog.exec()
        self.refresh_bookmarks()

    def eventFilter(self, obj, event):
        """一覧上の中ボタンで、そのブックマークを新しいタブで開く。

        Args:
            obj: イベントの対象。
            event: 受け取ったイベント。

        Returns:
            中ボタンが項目に当たったとき True。それ以外は親の結果。
        """
        if obj is self.bookmark_list.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                item = self.bookmark_list.itemAt(event.position().toPoint())
                if item is not None:
                    self._open_bookmark_item(item, new_tab=True)
                    return True
        return super().eventFilter(obj, event)

    def _open_bookmark_item(self, item, new_tab: bool):
        """ブックマーク項目を開く。フォルダや、ファイルが無いときは開かない。

        Args:
            item: 一覧項目。
            new_tab: 新しいタブで開くとき True。
        """
        data = item.data(Qt.UserRole)
        logger.info(get_log_text("debug_bmk_item_clicked", data=data))
        if data['type'] != 'bookmark':
            return
        bookmark = data['data']
        file_path = bookmark['file_path']
        page_number = bookmark['page_number']
        logger.info(get_log_text("debug_bmk_bookmark_clicked", file_path=file_path, page_number=page_number))
        exists = self._check_file_exists(file_path)
        logger.info(get_log_text("debug_bmk_check_file_exists", file_path=file_path, exists=exists))
        if not exists:
            logger.warning(get_log_text("debug_bmk_file_not_found", file_path=file_path))
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("dialogs.file_not_found") + "\n" + file_path)
            return
        logger.info(get_log_text("debug_bmk_emitting_bookmark_selected", file_path=file_path, page_number=page_number))
        self.bookmark_selected.emit(file_path, page_number, new_tab)

    def on_item_clicked(self, item):
        """アイテムをクリックした時の処理

        Args:
            item: クリックされた項目。Ctrl のときは新しいタブで開く。
        """
        new_tab = bool(QApplication.keyboardModifiers() & Qt.KeyboardModifier.ControlModifier)
        self._open_bookmark_item(item, new_tab)

    def on_item_double_clicked(self, item):
        """アイテムをダブルクリックした時の処理

        Args:
            item: ダブルクリックされた項目。フォルダならその中へ入る。
        """
        data = item.data(Qt.UserRole)
        logger.info(get_log_text("debug_bmk_item_double_clicked", data=data))
        if data['type'] == 'folder':
            folder = data['data']
            logger.info(get_log_text("debug_bmk_folder_double_clicked", folder_id=folder['id'], folder_name=folder['name']))
            self.enter_folder(folder['id'])
        elif data['type'] == 'bookmark':
            self.on_item_clicked(item)

    def on_bookmark_selected(self, file_path: str, page_number: int):
        """ブックマークが選択された時の処理

        Args:
            file_path: 開くパス。
            page_number: 開くページ。現在のタブで開く。
        """
        self.bookmark_selected.emit(file_path, page_number, False)

    def show_context_menu(self, position):
        """右クリックメニューを表示

        Args:
            position: 一覧上の位置。
        """
        item = self.bookmark_list.itemAt(position)
        logger.info(get_log_text("debug_bmk_show_context_menu_item", item=item))
        if not item:
            return
        data = item.data(Qt.UserRole)
        logger.info(get_log_text("debug_bmk_show_context_menu_data", data=data))
        menu = QMenu()
        if data['type'] == 'folder':
            delete_action = menu.addAction(get_text("ui.delete_folder"))
            delete_action.triggered.connect(lambda: self.delete_folder(data['data']))
            rename_action = menu.addAction(get_text("ui.rename_folder"))
            rename_action.triggered.connect(lambda: self.rename_folder(data['data']))
        elif data['type'] == 'bookmark':
            bookmark = data['data']
            open_current = menu.addAction(get_text("ui.open_in_current_tab"))
            open_current.triggered.connect(
                lambda: self.bookmark_selected.emit(bookmark['file_path'], bookmark['page_number'], False)
            )
            open_new = menu.addAction(get_text("ui.open_in_new_tab"))
            open_new.triggered.connect(
                lambda: self.bookmark_selected.emit(bookmark['file_path'], bookmark['page_number'], True)
            )
            menu.addSeparator()
            delete_action = menu.addAction(get_text("ui.delete"))
            delete_action.triggered.connect(lambda: self.delete_bookmark(data['data']))
            move_action = menu.addAction(get_text("ui.move_to_folder"))
            move_action.triggered.connect(lambda: self.move_bookmark_to_folder(data['data']))
        menu.exec_(self.bookmark_list.mapToGlobal(position))

    def delete_folder(self, folder):
        """フォルダを削除

        Args:
            folder: 消すフォルダ。中身があるときは消さない。
        """
        folder_id = folder['id']
        folder_name = folder['name']
        # フォルダ内のブックマーク数を確認
        bookmarks = self.db_manager.get_bookmarks(folder_id)
        subfolders = self.db_manager.get_bookmark_folders(folder_id)
        if bookmarks or subfolders:
            QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.folder_contains_items_warning").format(folder_name=folder_name))
            return
        reply = QMessageBox.question(
            self, get_text("ui.confirmation"),
            get_text("ui.delete_folder_confirm").format(folder_name=folder_name),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            # フォルダ削除の実装をデータベースマネージャーに追加する必要があります
            success = self.db_manager.delete_bookmark_folder(folder_id)
            if success:
                self.refresh_bookmarks()
                QMessageBox.information(self, get_text("ui.success"), get_text("ui.folder_deleted_success").format(folder_name=folder_name))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.folder_delete_failed"))

    def rename_folder(self, folder):
        """フォルダ名を変更

        Args:
            folder: 名前を変えるフォルダ。
        """
        folder_id = folder['id']
        old_name = folder['name']
        new_name, ok = QInputDialog.getText(
            self, get_text("ui.rename_folder_title"),
            get_text("ui.rename_folder_dialog"),
            text=old_name
        )
        if ok and new_name.strip() and new_name.strip() != old_name:
            success = self.db_manager.rename_bookmark_folder(folder_id, new_name.strip())
            if success:
                self.refresh_bookmarks()
                QMessageBox.information(self, get_text("ui.success"), get_text("ui.folder_renamed_success").format(new_name=new_name))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.folder_rename_failed"))

    def create_new_folder(self):
        """新しいフォルダを作成"""
        name, ok = QInputDialog.getText(self, get_text("ui.new_folder"), get_text("ui.new_folder_dialog"))
        if ok and name.strip():
            folder_id = self.db_manager.add_bookmark_folder(name.strip(), self.current_folder_id)
            if folder_id > 0:
                self.refresh_bookmarks()
                QMessageBox.information(self, get_text("ui.success"), get_text("ui.folder_created_success").format(name=name))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.folder_create_failed"))

    def add_bookmark(self):
        """ブックマークを追加"""
        file_path = self.current_file or ""
        page_number = self.current_page if self.current_file else 1
        # ファイルパスが空の場合は入力ダイアログを表示
        if not file_path:
            file_path, ok = QInputDialog.getText(self, get_text("ui.bookmark_add_title"), get_text("ui.add_bookmark_file_dialog"))
            if not ok or not file_path.strip():
                return
            file_path = file_path.strip()
        # ページ番号の入力
        page_text, ok = QInputDialog.getText(self, get_text("ui.bookmark_add_title"), get_text("ui.add_bookmark_page_dialog"), text=str(page_number))
        if not ok:
            return
        try:
            page_number = int(page_text)
        except ValueError:
            # ページ番号が整数でないときは警告して、追加を中断する。
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.page_number_invalid"))
            return
        # タイトルの入力
        title = Path(file_path).name if file_path else ""
        title, ok = QInputDialog.getText(self, get_text("ui.bookmark_add_title"), get_text("ui.add_bookmark_title_dialog"), text=title)
        if not ok:
            return
        # パス変換は行わず、そのまま保存
        logger.info(get_log_text("debug_bmk_adding_bookmark", file_path=file_path, page_number=page_number))
        # ブックマークを追加
        success = self.db_manager.add_bookmark(file_path, page_number, title, self.current_folder_id)
        if success:
            self.refresh_bookmarks()
            QMessageBox.information(self, get_text("ui.success"), get_text("ui.bookmark_add_success"))
        else:
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_add_failed"))

    def delete_bookmark(self, bookmark):
        """ブックマークを削除

        Args:
            bookmark: 消すブックマーク。
        """
        file_path = bookmark['file_path']
        page_number = bookmark['page_number']
        reply = QMessageBox.question(
            self, get_text("ui.confirmation"),
            get_text("ui.delete_bookmark_confirm").format(file_name=Path(file_path).name, page_number=page_number),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            success = self.db_manager.remove_bookmark(file_path, page_number)
            if success:
                self.refresh_bookmarks()
                QMessageBox.information(self, get_text("ui.success"), get_text("ui.bookmark_delete_success"))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_delete_failed"))

    def move_bookmark_to_folder(self, bookmark):
        """ブックマークを別のフォルダに移動

        Args:
            bookmark: 移動するブックマーク。
        """
        file_path = bookmark['file_path']
        page_number = bookmark['page_number']
        # フォルダ選択ダイアログ
        folders = self.db_manager.get_bookmark_folders()
        folder_names = [get_text("ui.root_folder")]
        folder_ids = [0]
        for folder in folders:
            folder_names.append(folder['name'])
            folder_ids.append(folder['id'])
        folder_name, ok = QInputDialog.getItem(
            self, get_text("ui.move_to_folder"),
            get_text("ui.select_destination_folder"),
            folder_names, 0, False
        )
        if ok and folder_name:
            folder_index = folder_names.index(folder_name)
            target_folder_id = folder_ids[folder_index]
            success = self.db_manager.move_bookmark_to_folder(file_path, page_number, target_folder_id)
            if success:
                self.refresh_bookmarks()
                QMessageBox.information(self, get_text("ui.success"), get_text("ui.bookmark_move_success"))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_move_failed"))

    def on_items_moved(self, parent, start, end, destination, row):
        """アイテムが移動された時の処理

        Args:
            parent: 移動シグナルの親。処理しない。
            start: 移動範囲の開始。処理しない。
            end: 移動範囲の終わり。処理しない。
            destination: 移動先の親。処理しない。
            row: 移動先の行。処理しない。
        """
        # 順序を更新する処理をここに追加

    def set_current_file(self, file_path: str, page_number: int):
        """現在のファイルとページを設定

        Args:
            file_path: 現在のパス。
            page_number: 現在のページ。
        """
        self.current_file = file_path
        self.current_page = page_number
