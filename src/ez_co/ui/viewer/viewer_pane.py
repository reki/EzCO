"""1 タブ分のビュワー状態（ImageView と FileHandler）。"""
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ez_co.ui.viewer.image_view import ImageView
from ez_co.utils.language_manager import get_text


class ViewerPane(QWidget):
    """1タブ分の ImageView と、開いているファイルの状態を持つ。"""

    def __init__(self, config, parent=None):
        """ImageView を置き、ファイルとページの状態を初期化する。

        Args:
            config: 表示に使う設定。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.config = config
        self.file_handler = None
        self.current_file_path = None
        self.base_dir_path = None
        self.current_rotation_angle = 0
        self.current_page = 1
        self.total_pages = 0
        self._spread_force_single = False
        self._center_message_label = None
        self.pinned = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.image_view = ImageView(self, config=config)
        layout.addWidget(self.image_view)

    def is_empty(self) -> bool:
        """ファイルもフォルダも開いていないかを返す。

        Returns:
            開いているファイル一覧もパスも無いとき True。
        """
        if self.file_handler and self.file_handler.current_files:
            return False
        return not self.current_file_path and not self.base_dir_path

    def tab_title(self) -> str:
        """タブに出す名前を返す。

        Returns:
            開いているファイルまたはフォルダの名前。無ければ新規タブの文言。
        """
        path = self.current_file_path or self.base_dir_path
        if path:
            return Path(path).name
        return get_text("ui.new_tab")

    def closed_state(self) -> dict:
        """閉じたタブを戻すためのパスとページを返す。

        Returns:
            file_path と page を持つ辞書。
        """
        return {
            "file_path": self.current_file_path or self.base_dir_path,
            "page": self.current_page or 1,
        }

    def dispose(self):
        """タブが所有するbackground workerとfile handleを終了する。"""
        if self.file_handler is not None:
            self.file_handler.close()
            self.file_handler = None

    def show_center_message(self, message: str):
        """中央にメッセージを出す。

        Args:
            message: 表示する文字列。
        """
        if self._center_message_label is None:
            self._center_message_label = QLabel(self)
            self._center_message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._center_message_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            self._center_message_label.setWordWrap(True)
        gesture_display = getattr(self.config, "gesture_display", {}) if self.config else {}
        font_family = gesture_display.get("font_family", "Meiryo")
        font_size = gesture_display.get("font_size", 18)
        font_color = gesture_display.get("font_color", "#0000ff")
        self._center_message_label.setText(message)
        self._center_message_label.setStyleSheet(
            f"color: {font_color}; font-size: {font_size}px; font-family: {font_family}; "
            "background: transparent; border: none;"
        )
        self._center_message_label.show()
        self._center_message_label.raise_()
        self._update_center_message_position()
        QTimer.singleShot(10, self._update_center_message_position)
        QTimer.singleShot(50, self._update_center_message_position)

    def hide_center_message(self):
        """中央のメッセージを隠して文を消す。"""
        if self._center_message_label is not None:
            self._center_message_label.hide()
            self._center_message_label.setText("")

    def _update_center_message_position(self):
        """中央メッセージをペインの中央へ置く。"""
        label = self._center_message_label
        if label is None or not label.isVisible():
            return
        width = self.width()
        height = self.height()
        if width <= 0 or height <= 0:
            return
        label.setFixedWidth(int(width * 0.8))
        label.adjustSize()
        label.move((width - label.width()) // 2, (height - label.height()) // 2)

    def resizeEvent(self, event):
        """サイズ変更に合わせて中央メッセージの位置を更新する。

        Args:
            event: リサイズイベント。
        """
        super().resizeEvent(event)
        self._update_center_message_position()
