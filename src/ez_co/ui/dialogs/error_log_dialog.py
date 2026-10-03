"""エラーログの場所と本文を表示するダイアログ。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QApplication,
)
from ez_co.utils.language_manager import get_text


class ErrorLogDialog(QDialog):
    """エラーログの場所と本文を表示し、本文をコピーできる。"""

    def __init__(self, where: str, text: str, parent=None):
        """場所と本文を載せてダイアログを組み立てる。

        Args:
            where: ログの場所として出す文字列。
            text: 表示するログ本文。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._text = text or ""
        self.setWindowTitle(get_text("ui.error_log_title"))
        self.resize(720, 420)
        layout = QVBoxLayout(self)
        where_label = QLabel(str(where or ""))
        where_label.setWordWrap(True)
        layout.addWidget(where_label)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setPlainText(self._text)
        layout.addWidget(view)
        buttons = QHBoxLayout()
        buttons.addStretch()
        copy_button = QPushButton(get_text("ui.error_log_copy"))
        copy_button.clicked.connect(self._copy)
        close_button = QPushButton(get_text("ui.close"))
        close_button.clicked.connect(self.accept)
        buttons.addWidget(copy_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _copy(self):
        """ログ本文をクリップボードへコピーする。"""
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._text)
