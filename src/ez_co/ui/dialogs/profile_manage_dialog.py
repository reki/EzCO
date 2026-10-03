"""プロファイルの削除と名前変更を行うダイアログ。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton,
    QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt
from ez_co.utils.language_manager import get_text, get_log_text
import logging

logger = logging.getLogger(__name__)


class ProfileManageDialog(QDialog):
    """プロファイルの削除・名前変更"""

    def __init__(self, db_manager, parent=None):
        """データベースと一覧を用意する。

        Args:
            db_manager: プロファイルを操作するデータベース。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.db_manager = db_manager
        self.deleted_current = False
        self.renamed_pairs = []
        self.setWindowTitle(get_text("ui.manage_profiles"))
        self.setup_ui()
        self.refresh_list()

    def setup_ui(self):
        """一覧と、名前変更・削除・閉じるボタンを配置する。"""
        layout = QVBoxLayout()
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        self.rename_button = QPushButton(get_text("ui.rename_profile"))
        self.rename_button.clicked.connect(self.rename_selected)
        self.delete_button = QPushButton(get_text("ui.delete_profile"))
        self.delete_button.clicked.connect(self.delete_selected)
        close_button = QPushButton(get_text("ui.close"))
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.rename_button)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout.addLayout(buttons)
        self.setLayout(layout)
        self.resize(360, 280)

    def refresh_list(self):
        """プロファイル一覧を読み直す。現在のプロファイルにはその旨を付ける。"""
        self.list_widget.clear()
        current = self.db_manager.current_profile
        for name in self.db_manager.get_profiles():
            label = name
            if name == current:
                label = f"{name} ({get_text('ui.current_profile')})"
            self.list_widget.addItem(label)
            self.list_widget.item(self.list_widget.count() - 1).setData(Qt.UserRole, name)

    def _selected_name(self):
        """選択中のプロファイル名を返す。

        Returns:
            選択中の名前。未選択なら None。
        """
        item = self.list_widget.currentItem()
        if not item:
            return None
        return item.data(Qt.UserRole)

    def rename_selected(self):
        """選択中のプロファイル名を変える。空、同じ名前、既存名は警告して変えない。"""
        old_name = self._selected_name()
        if not old_name:
            return
        new_name, ok = QInputDialog.getText(
            self,
            get_text("ui.rename_profile"),
            get_text("ui.enter_new_profile_name"),
            text=old_name,
        )
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.profile_name_required"))
            return
        if new_name == old_name:
            return
        if self.db_manager.profile_exists(new_name):
            QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.profile_name_exists"))
            return
        if self.db_manager.rename_profile(old_name, new_name):
            self.renamed_pairs.append((old_name, new_name))
            QMessageBox.information(
                self,
                get_text("ui.success"),
                get_text("ui.profile_rename_success").format(old_name=old_name, new_name=new_name),
            )
            self.refresh_list()
        else:
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.profile_rename_failed"))

    def delete_selected(self):
        """選択中のプロファイルを消す。保護された名前は消さない。現在のプロファイルを消したときはその旨を残す。"""
        name = self._selected_name()
        if not name:
            return
        if self.db_manager.is_protected_profile(name):
            QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.default_profile_cannot_delete"))
            return
        reply = QMessageBox.question(
            self,
            get_text("ui.confirmation"),
            get_text("ui.profile_delete_confirm").format(profile_name=name),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        was_current = name == self.db_manager.current_profile
        if self.db_manager.delete_profile(name):
            if was_current:
                self.deleted_current = True
            QMessageBox.information(
                self,
                get_text("ui.success"),
                get_text("ui.profile_delete_success").format(profile_name=name),
            )
            logger.info(get_log_text("profile_deleted", profile_name=name))
            self.refresh_list()
        else:
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.profile_delete_failed_msg"))
