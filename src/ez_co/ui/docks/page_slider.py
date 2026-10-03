"""ページ送りのスライダー。ドック結合時は1行、解除時は浮き窓。"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QSpinBox, QPushButton,
    QSizePolicy, QStyleFactory,
)
from PySide6.QtCore import Qt, Signal
from ez_co.utils.language_manager import get_text, get_log_text

logger = logging.getLogger(__name__)

# ドックを外したときの浮き窓の幅と高さ。
_FLOATING_SIZE = (300, 110)
# ドックに収めたときの1行の高さ。
_COMPACT_HEIGHT = 32
# ページ番号入力の幅。
_SPIN_WIDTH = 60


class PageSlider(QWidget):
    """ページスライダー。ドック結合時は1行、解除時は浮き窓の3段。"""

    page_changed = Signal(int)

    def __init__(self, parent=None, file_handler=None, host=None):
        """スライダーとページ番号を用意し、ファイルの状態を反映する。

        Args:
            parent: 親ウィジェット。
            file_handler: ページ一覧を持つハンドラ。
            host: ページ移動の通知先。無ければ parent。
        """
        super().__init__(parent)
        self.file_handler = file_handler
        self.parent_window = host if host is not None else parent
        self._updating = False
        self._compact = False
        self._rtl_slider = None

        self.setup_ui()
        self.setup_connections()
        self.set_compact(False)
        self.update_from_handler()

        logger.info(get_log_text("page_slider_dialog_initialized"))

    def setup_ui(self):
        """ページ表示、番号、スライダー、先頭と末尾のボタンを作る。"""
        self._root = QVBoxLayout()
        self._root.setContentsMargins(4, 2, 4, 2)
        self._root.setSpacing(2)
        self.setLayout(self._root)

        self.page_info_label = QLabel()

        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(1)
        self.page_spinbox.setFixedWidth(_SPIN_WIDTH)

        self.page_slider = QSlider(Qt.Horizontal)
        self.page_slider.setMinimum(1)
        self.page_slider.setMaximum(1)
        self.page_slider.setMinimumHeight(24)
        fusion = QStyleFactory.create("Fusion")
        if fusion:
            self.page_slider.setStyle(fusion)
        self.page_slider.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.button_layout = QHBoxLayout()
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(4)
        self.first_button = QPushButton(get_text("ui.first_page_button"))
        self.last_button = QPushButton(get_text("ui.last_page_button"))
        self.first_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.last_button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.button_layout.addWidget(self.first_button)
        self.button_layout.addWidget(self.last_button)

        self._row = QHBoxLayout()
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(6)

    def setup_connections(self):
        """スライダー、番号、先頭、末尾をページ移動へつなぐ。"""
        self.page_slider.valueChanged.connect(self.on_slider_changed)
        self.page_spinbox.valueChanged.connect(self.on_spinbox_changed)
        self.first_button.clicked.connect(self.go_to_first_page)
        self.last_button.clicked.connect(self.go_to_last_page)

    def set_compact(self, compact: bool):
        """結合時は1行、浮き窓は3段。

        Args:
            compact: 1行にするとき True。
        """
        self._compact = bool(compact)
        self._rebuild_layout()
        if self._compact:
            self.setMinimumSize(0, 0)
            self.setMaximumWidth(16777215)
            self.setFixedHeight(_COMPACT_HEIGHT)
            self.page_slider.setMinimumHeight(16)
            self.page_info_label.hide()
        else:
            self.setFixedSize(*_FLOATING_SIZE)
            self.page_slider.setMinimumHeight(24)
            self.page_info_label.show()
        rtl = self._rtl_slider
        self._rtl_slider = None
        self._apply_slider_direction()
        if rtl is not None:
            self._rtl_slider = rtl

    def _rebuild_layout(self):
        """結合時はスライダー、番号、ボタンの1行にする。浮き窓は表示、番号とスライダー、ボタンの3段にする。"""
        while self._root.count():
            self._root.takeAt(0)
        while self._row.count():
            self._row.takeAt(0)
        if self._compact:
            self._row.addWidget(self.page_slider, 1)
            self._row.addWidget(self.page_spinbox, 0)
            self._row.addLayout(self.button_layout, 0)
            self._root.addLayout(self._row)
        else:
            self._root.addWidget(self.page_info_label)
            self._row.addWidget(self.page_spinbox, 0)
            self._row.addWidget(self.page_slider, 1)
            self._root.addLayout(self._row)
            self._root.addLayout(self.button_layout)

    def _clear_empty_state(self):
        """本がないときの表示。操作は不可、閉じた本の数字は残さない。"""
        self._updating = True
        try:
            self.page_slider.setMaximum(1)
            self.page_spinbox.setMaximum(1)
            self.page_slider.setValue(1)
            self.page_spinbox.setValue(1)
            self.page_info_label.setText("")
            self.setEnabled(False)
        finally:
            self._updating = False

    def update_from_handler(self):
        """ファイルハンドラーから現在の状態を更新"""
        if not self.file_handler or not self.file_handler.current_files:
            self._clear_empty_state()
            return

        self._updating = True
        try:
            self._apply_slider_direction()
            total_pages = len(self.file_handler.current_files)
            current_page = self.file_handler.current_index + 1

            self.page_slider.setMaximum(total_pages)
            self.page_spinbox.setMaximum(total_pages)

            self.page_slider.setValue(current_page)
            self.page_spinbox.setValue(current_page)

            self.page_info_label.setText(self._format_page_info(current_page, total_pages))

            self.first_button.setEnabled(current_page > 1)
            self.last_button.setEnabled(not self._is_at_last_position(current_page, total_pages))

            self.setEnabled(True)
        finally:
            self._updating = False

    def on_slider_changed(self, value):
        """更新中でなければ番号を合わせてページを変える。

        Args:
            value: スライダーのページ。
        """
        if self._updating:
            return
        self._updating = True
        try:
            self.page_spinbox.setValue(value)
            self.change_page(value)
        finally:
            self._updating = False

    def on_spinbox_changed(self, value):
        """更新中でなければスライダーを合わせてページを変える。

        Args:
            value: 番号入力のページ。
        """
        if self._updating:
            return
        self._updating = True
        try:
            self.page_slider.setValue(value)
            self.change_page(value)
        finally:
            self._updating = False

    def change_page(self, page_number):
        """ファイルがあるとき、そのページへ移して画像を更新する。

        Args:
            page_number: 1始まりのページ。
        """
        if not self.file_handler or not self.file_handler.current_files:
            return

        target_index = page_number - 1
        if 0 <= target_index < len(self.file_handler.current_files):
            if hasattr(self.parent_window, "_clear_spread_force_single"):
                self.parent_window._clear_spread_force_single()
            self.file_handler.current_index = target_index
            aligned_page = target_index + 1

            if hasattr(self.parent_window, "current_page"):
                self.parent_window.current_page = aligned_page

            if hasattr(self.parent_window, "update_image"):
                self.parent_window.update_image()

            self.page_slider.setValue(aligned_page)
            self.page_spinbox.setValue(aligned_page)
            self.update_info_display(aligned_page)
            self.page_changed.emit(aligned_page)

            logger.info(get_log_text("page_slider_dialog_page_changed", page=aligned_page))

    def update_info_display(self, current_page):
        """ページ表示と、先頭・末尾ボタンの有効を更新する。

        Args:
            current_page: 表示中のページ。
        """
        if not self.file_handler or not self.file_handler.current_files:
            return

        total_pages = len(self.file_handler.current_files)
        self.page_info_label.setText(self._format_page_info(current_page, total_pages))
        self.first_button.setEnabled(current_page > 1)
        self.last_button.setEnabled(not self._is_at_last_position(current_page, total_pages))

    def _format_page_info(self, current_page, total_pages):
        """見開きなら開始と次のページ、そうでなければ現在ページを総数つきで返す。

        Args:
            current_page: 表示中のページ。
            total_pages: 総ページ。

        Returns:
            ページ表示の文字列。
        """
        if hasattr(self.parent_window, "_has_spread_pair") and self.parent_window._has_spread_pair():
            start = current_page
            if hasattr(self.parent_window, "_spread_display_start"):
                start = self.parent_window._spread_display_start(current_page - 1) + 1
            return f"{start}-{start + 1} / {total_pages}"
        return f"{current_page} / {total_pages}"

    def _is_at_last_position(self, current_page, total_pages):
        """現在ページが総数以上かを返す。

        Args:
            current_page: 表示中のページ。
            total_pages: 総ページ。

        Returns:
            末尾のとき True。
        """
        return current_page >= total_pages

    def _use_rtl_slider(self) -> bool:
        """親が右から左のスライダーを使うかを返す。親に無ければ True。

        Returns:
            右から左のとき True。
        """
        if hasattr(self.parent_window, "_use_rtl_page_slider"):
            return self.parent_window._use_rtl_page_slider()
        return True

    def _apply_slider_direction(self):
        """スライダーの向きと、先頭・末尾ボタンの並びを更新する。向きが同じならボタンは動かさない。"""
        rtl = self._use_rtl_slider()
        self.page_slider.setInvertedAppearance(rtl)
        self.page_slider.setInvertedControls(rtl)
        self._apply_slider_fill_style(rtl)
        if self._rtl_slider == rtl:
            return
        self._rtl_slider = rtl
        self.button_layout.removeWidget(self.first_button)
        self.button_layout.removeWidget(self.last_button)
        if rtl:
            self.button_layout.addWidget(self.last_button)
            self.button_layout.addWidget(self.first_button)
        else:
            self.button_layout.addWidget(self.first_button)
            self.button_layout.addWidget(self.last_button)

    def _apply_slider_fill_style(self, rtl: bool):
        """右から左かどうかで、進む側と戻る側の色をスタイルシートにする。

        Args:
            rtl: 右から左のとき True。
        """
        if rtl:
            sub_page = "palette(mid)"
            add_page = "palette(highlight)"
        else:
            sub_page = "palette(highlight)"
            add_page = "palette(mid)"
        groove_margin = "4px 0" if self._compact else "10px 0"
        handle = 12 if self._compact else 16
        margin = -6 if self._compact else -8
        self.page_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                margin: {groove_margin};
                border-radius: 2px;
            }}
            QSlider::sub-page:horizontal {{
                background: {sub_page};
                border-radius: 2px;
            }}
            QSlider::add-page:horizontal {{
                background: {add_page};
                border-radius: 2px;
            }}
            QSlider::handle:horizontal {{
                background: palette(light);
                border: 2px solid palette(highlight);
                width: {handle}px;
                height: {handle}px;
                margin: {margin}px 0;
                border-radius: {handle // 2 + 2}px;
            }}
        """)

    def go_to_first_page(self):
        """ファイルがあれば1ページへ移る。"""
        if self.file_handler and self.file_handler.current_files:
            self._go_to_page(1)

    def go_to_last_page(self):
        """ファイルがあれば最終ページへ移る。"""
        if self.file_handler and self.file_handler.current_files:
            total_pages = len(self.file_handler.current_files)
            self._go_to_page(total_pages)

    def _go_to_page(self, page_number):
        """更新中フラグを立ててスライダーと番号を合わせ、ページを変える。

        Args:
            page_number: 移るページ。
        """
        self._updating = True
        try:
            self.page_slider.setValue(page_number)
            self.page_spinbox.setValue(page_number)
            self.change_page(page_number)
        finally:
            self._updating = False

    def refresh(self):
        """ファイルの状態から表示を読み直す。"""
        self.update_from_handler()
