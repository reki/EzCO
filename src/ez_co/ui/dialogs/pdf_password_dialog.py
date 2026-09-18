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

CLOSE_APP_RESULT = 2


class ArchivePasswordDialog(QDialog):
    """パスワード付きファイル用の入力ダイアログ。"""

    def __init__(self, parent=None, mismatch: bool = False):
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.archive_password_title"))
        self.setModal(True)
        self.setMinimumWidth(360)
        self._password = ""
        self._setup_ui(mismatch)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, True)

    def _setup_ui(self, mismatch: bool):
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
        self._password = self.password_edit.text()
        self.accept()

    def _close_app(self):
        self.done(CLOSE_APP_RESULT)

    def reject(self):
        self.done(CLOSE_APP_RESULT)

    def password(self) -> str:
        return self._password


PdfPasswordDialog = ArchivePasswordDialog
