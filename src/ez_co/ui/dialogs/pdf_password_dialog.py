"""パスワード付きアーカイブの入力ダイアログ。PdfPasswordDialog は同じクラスの別名。"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from ez_co.utils.language_manager import get_text

# パスワード入力をやめてアプリを閉じるときのダイアログ結果。
CLOSE_APP_RESULT = 2


class ArchivePasswordDialog(QDialog):
    """パスワード付きファイル用の入力ダイアログ。"""

    def __init__(self, parent=None, mismatch: bool = False):
        """パスワード入力ダイアログを組み立てる。

        Args:
            parent: 親ウィジェット。
            mismatch: 不一致のメッセージを最初から出すとき True。
        """
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.archive_password_title"))
        self.setModal(True)
        self.setMinimumWidth(360)
        self._password = ""
        self._setup_ui(mismatch)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

    def _setup_ui(self, mismatch: bool):
        """入力欄とボタンを配置する。

        Args:
            mismatch: 不一致のメッセージを表示するとき True。
        """
        layout = QVBoxLayout()

        layout.addWidget(QLabel(get_text("ui.archive_password_label")))
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.returnPressed.connect(self._accept)
        layout.addWidget(self.password_edit)

        self.error_label = QLabel(get_text("ui.archive_password_mismatch"))
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color: #c62828;")
        self.error_label.setVisible(mismatch)
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch()
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.setDefault(True)
        ok_button.clicked.connect(self._accept)
        close_button = QPushButton(get_text("ui.exit"))
        close_button.clicked.connect(self._close_app)
        buttons.addWidget(ok_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

        self.setLayout(layout)
        self.password_edit.setFocus()

    def _accept(self):
        """入力中の文字列をパスワードとして確定し、ダイアログを閉じる。"""
        self._password = self.password_edit.text()
        self.accept()

    def _close_app(self):
        """アプリ終了用の結果でダイアログを閉じる。"""
        self.done(CLOSE_APP_RESULT)

    def reject(self):
        """閉じる操作もアプリ終了用の結果にする。"""
        self.done(CLOSE_APP_RESULT)

    def password(self) -> str:
        """確定したパスワードを返す。

        Returns:
            確定した文字列。未確定のときは空文字列。
        """
        return self._password


PdfPasswordDialog = ArchivePasswordDialog
