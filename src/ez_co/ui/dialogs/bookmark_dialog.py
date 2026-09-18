import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QSpinBox, QLineEdit, QMessageBox, QFrame,
    QSplitter, QWidget, QFormLayout, QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from ez_co.utils.database import DatabaseManager
from ez_co.utils.language_manager import get_text, get_log_text
from ez_co.enums.entry_types import EntryType
logger = logging.getLogger(__name__)
class BookmarkDialog(QDialog):
    """ブックマーク管理ダイアログ"""
    bookmark_selected = Signal(str, int)  # file_path, page_number
    def __init__(self, parent=None, current_file: str = None, current_page: int = 1, config=None, db_manager=None):
        super().__init__(parent)
        self.db_manager = db_manager or DatabaseManager(config)
        self.current_file = current_file
        self.current_page = current_page
        logger.info(get_log_text("bookmark_dialog_opened", current_file=current_file or "None", current_page=current_page))
        self.setup_ui()
        self.load_bookmarks()
    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.bookmarks"))
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout()
        self.setLayout(layout)
        # スプリッターで左右に分割
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        # 左側：ブックマーク一覧
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        # ブックマーク一覧ラベル
        list_label = QLabel(get_text("ui.bookmarks"))
        left_layout.addWidget(list_label)
        # ブックマークリスト
        self.bookmark_list = QListWidget()
        self.bookmark_list.itemDoubleClicked.connect(self.on_bookmark_double_clicked)
        left_layout.addWidget(self.bookmark_list)
        # 左側のボタン
        left_buttons_layout = QHBoxLayout()
        self.delete_button = QPushButton(get_text("ui.delete"))
        self.delete_button.clicked.connect(self.delete_selected_bookmark)
        left_buttons_layout.addWidget(self.delete_button)
        left_buttons_layout.addStretch()
        left_layout.addLayout(left_buttons_layout)
        splitter.addWidget(left_widget)
        # 右側：ブックマーク追加
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_widget.setLayout(right_layout)
        # 追加ラベル
        add_label = QLabel(get_text("ui.bookmark_add_title"))
        right_layout.addWidget(add_label)
        # 区切り線
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        right_layout.addWidget(line)
        # フォーム
        form_layout = QFormLayout()
        # ファイルパス
        self.file_path_edit = QLineEdit()
        if self.current_file:
            self.file_path_edit.setText(self.current_file)
        form_layout.addRow(get_text("ui.file_path") + ":", self.file_path_edit)
        # ページ番号
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(9999)
        self.page_spinbox.setValue(self.current_page)
        form_layout.addRow(get_text("ui.page_number") + ":", self.page_spinbox)
        # タイトル
        self.title_edit = QLineEdit()
        if self.current_file:
            # virtual pathの場合（archive:〜形式）はアーカイブファイル名を使用
            if self.current_file.startswith("archive:"):
                try:
                    from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                    archive_path, internal_path = VirtualPathHandler.parse_virtual_path(self.current_file)
                    title = archive_path.name
                except Exception as e:
                    logger.error(f"virtual pathの解析に失敗: {self.current_file}, エラー: {e}")
                    title = Path(self.current_file).name
            else:
                title = Path(self.current_file).name
            self.title_edit.setText(title)
        form_layout.addRow(get_text("ui.title") + ":", self.title_edit)
        right_layout.addLayout(form_layout)
        # 追加ボタン
        self.add_button = QPushButton(get_text("ui.bookmark_add_title"))
        self.add_button.clicked.connect(self.add_bookmark)
        right_layout.addWidget(self.add_button)
        right_layout.addStretch()
        splitter.addWidget(right_widget)
        # スプリッターの比率を設定
        splitter.setSizes([400, 200])
        # ダイアログボタン
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    def load_bookmarks(self):
        """ブックマーク一覧を読み込み"""
        self.bookmark_list.clear()
        bookmarks = self.db_manager.get_bookmarks()
        logger.info(get_log_text("bookmark_loaded", count=len(bookmarks)))
        for bookmark in bookmarks:
            file_path = bookmark['file_path']
            page_number = bookmark['page_number']
            title = bookmark['title'] or Path(file_path).name
            entry_type = bookmark.get('entry_type', EntryType.FILE.value)
            
            # 表示用のテキストを作成
            display_text = f"{title} (ページ {page_number})"
            if len(file_path) > 50:
                display_text += f"\n{file_path[:47]}..."
            else:
                display_text += f"\n{file_path}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, bookmark)
            self.bookmark_list.addItem(item)
    def add_bookmark(self):
        """ブックマークを追加"""
        file_path = self.file_path_edit.text().strip()
        page_number = self.page_spinbox.value()
        title = self.title_edit.text().strip()
        if not file_path:
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.input_file_path"))
            return
        if not title:
            # virtual pathの場合（archive:〜形式）はアーカイブファイル名を使用
            if file_path.startswith("archive:"):
                try:
                    from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                    archive_path, internal_path = VirtualPathHandler.parse_virtual_path(file_path)
                    title = archive_path.name
                except Exception as e:
                    logger.error(f"virtual pathの解析に失敗: {file_path}, エラー: {e}")
                    title = Path(file_path).name
            else:
                title = Path(file_path).name
        
        # フォルダかどうかを判定してentry_typeを設定
        entry_type = EntryType.FOLDER.value if Path(file_path).is_dir() else EntryType.FILE.value
        logger.info(get_log_text("bookmark_add_attempt", file_path=file_path, page=page_number, title=title))
        success = self.db_manager.add_bookmark(file_path, page_number, title, 0, entry_type)
        if success:
            logger.info(get_log_text("bookmark_add_success_log", file_path=file_path, page=page_number))
            QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.bookmark_add_success"))
            self.load_bookmarks()
        else:
            logger.error(get_log_text("bookmark_add_failed_log", file_path=file_path, page=page_number))
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_add_failed"))
    def delete_selected_bookmark(self):
        """選択されたブックマークを削除"""
        current_item = self.bookmark_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.select_bookmark_to_delete"))
            return
        bookmark = current_item.data(Qt.UserRole)
        reply = QMessageBox.question(
            self, get_text("dialogs.question"), 
            get_text("ui.bookmark_delete_confirm").format(title=bookmark['title'], page=bookmark['page_number']),
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            logger.info(get_log_text("bookmark_delete_attempt", file_path=bookmark['file_path'], page=bookmark['page_number']))
            success = self.db_manager.remove_bookmark(
                bookmark['file_path'], 
                bookmark['page_number']
            )
            if success:
                logger.info(get_log_text("bookmark_delete_success_log", file_path=bookmark['file_path'], page=bookmark['page_number']))
                self.load_bookmarks()
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.bookmark_delete_success"))
            else:
                logger.error(get_log_text("bookmark_delete_failed_log", file_path=bookmark['file_path'], page=bookmark['page_number']))
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_delete_failed"))
    def on_bookmark_double_clicked(self, item):
        """ブックマークをダブルクリックした時の処理"""
        bookmark = item.data(Qt.UserRole)
        self.bookmark_selected.emit(bookmark['file_path'], bookmark['page_number'])
        self.accept() 