import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QSpinBox, QPushButton,
    QStyleFactory,
)
from PySide6.QtCore import Qt, Signal
from ez_co.utils.language_manager import get_text, get_log_text

logger = logging.getLogger(__name__)

class PageSliderDialog(QDialog):
    """ページスライダーダイアログ（モードレスダイアログ）"""
    
    page_changed = Signal(int)  # ページ変更シグナル
    
    def __init__(self, parent=None, file_handler=None):
        super().__init__(parent)
        self.file_handler = file_handler
        self.parent_window = parent
        self._updating = False  # 内部更新中フラグ
        
        self.setup_ui()
        self.setup_connections()
        self.update_from_handler()
        
        # モードレスダイアログの設定
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        
        logger.info(get_log_text("page_slider_dialog_initialized"))
    
    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.page_slider_dialog_title"))
        self.setFixedSize(300, 110)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # 現在のページ表示
        info_layout = QHBoxLayout()
        self.page_info_label = QLabel()
        info_layout.addWidget(self.page_info_label)
        layout.addLayout(info_layout)
        
        # スライダーとスピンボックス
        slider_layout = QHBoxLayout()
        
        # ページ番号スピンボックス
        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.setMaximum(1)
        self.page_spinbox.setFixedWidth(60)
        slider_layout.addWidget(self.page_spinbox)
        
        # スライダー
        self.page_slider = QSlider(Qt.Horizontal)
        self.page_slider.setMinimum(1)
        self.page_slider.setMaximum(1)
        self.page_slider.setMinimumHeight(24)
        # Windows ネイティブスタイルは invertedAppearance でも左から塗るため Fusion で塗りを制御する
        fusion = QStyleFactory.create("Fusion")
        if fusion:
            self.page_slider.setStyle(fusion)
        slider_layout.addWidget(self.page_slider)
        
        layout.addLayout(slider_layout)
        
        # ボタン
        self.button_layout = QHBoxLayout()
        
        self.first_button = QPushButton(get_text("ui.first_page_button"))
        self.last_button = QPushButton(get_text("ui.last_page_button"))
        
        self.button_layout.addWidget(self.first_button)
        self.button_layout.addWidget(self.last_button)
        
        layout.addLayout(self.button_layout)
        self._rtl_slider = None
    
    def setup_connections(self):
        """シグナルとスロットの接続"""
        self.page_slider.valueChanged.connect(self.on_slider_changed)
        self.page_spinbox.valueChanged.connect(self.on_spinbox_changed)
        
        self.first_button.clicked.connect(self.go_to_first_page)
        self.last_button.clicked.connect(self.go_to_last_page)
    
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
            
            # スライダーとスピンボックスの範囲を設定
            self.page_slider.setMaximum(total_pages)
            self.page_spinbox.setMaximum(total_pages)
            
            # 現在のページを設定
            self.page_slider.setValue(current_page)
            self.page_spinbox.setValue(current_page)
            
            # 情報ラベルを更新
            self.page_info_label.setText(self._format_page_info(current_page, total_pages))
            
            # ボタンの有効/無効を設定
            self.first_button.setEnabled(current_page > 1)
            self.last_button.setEnabled(not self._is_at_last_position(current_page, total_pages))
            
            self.setEnabled(True)
        finally:
            self._updating = False
    
    def on_slider_changed(self, value):
        """スライダー値変更時の処理"""
        if self._updating:
            return
        
        self._updating = True
        try:
            self.page_spinbox.setValue(value)
            self.change_page(value)
        finally:
            self._updating = False
    
    def on_spinbox_changed(self, value):
        """スピンボックス値変更時の処理"""
        if self._updating:
            return
        
        self._updating = True
        try:
            self.page_slider.setValue(value)
            self.change_page(value)
        finally:
            self._updating = False
    
    def change_page(self, page_number):
        """ページを変更"""
        if not self.file_handler or not self.file_handler.current_files:
            return
        
        # ページ番号を0ベースのインデックスに変換
        target_index = page_number - 1
        
        # インデックスの範囲チェック
        if 0 <= target_index < len(self.file_handler.current_files):
            if hasattr(self.parent_window, '_clear_spread_force_single'):
                self.parent_window._clear_spread_force_single()
            self.file_handler.current_index = target_index
            aligned_page = target_index + 1
            
            # 親ウィンドウの現在ページを更新
            if hasattr(self.parent_window, 'current_page'):
                self.parent_window.current_page = aligned_page
            
            # 親ウィンドウの画像を更新
            if hasattr(self.parent_window, 'update_image'):
                self.parent_window.update_image()
            
            # 選択ページは維持（1でも2でも 1-2 を表示）
            self.page_slider.setValue(aligned_page)
            self.page_spinbox.setValue(aligned_page)
            
            # 情報表示を更新
            self.update_info_display(aligned_page)
            
            logger.info(get_log_text("page_slider_dialog_page_changed", page=aligned_page))
    
    def update_info_display(self, current_page):
        """情報表示のみを更新（循環参照を避けるため）"""
        if not self.file_handler or not self.file_handler.current_files:
            return
        
        total_pages = len(self.file_handler.current_files)
        self.page_info_label.setText(self._format_page_info(current_page, total_pages))
        
        # ボタンの有効/無効を設定
        self.first_button.setEnabled(current_page > 1)
        self.last_button.setEnabled(not self._is_at_last_position(current_page, total_pages))
    
    def _format_page_info(self, current_page, total_pages):
        """ページ情報テキストを生成"""
        if hasattr(self.parent_window, '_has_spread_pair') and self.parent_window._has_spread_pair():
            start = current_page
            if hasattr(self.parent_window, '_spread_display_start'):
                start = self.parent_window._spread_display_start(current_page - 1) + 1
            return f"{start}-{start + 1} / {total_pages}"
        return f"{current_page} / {total_pages}"
    
    def _is_at_last_position(self, current_page, total_pages):
        """最後の表示位置にいるか"""
        return current_page >= total_pages
    
    def _use_rtl_slider(self) -> bool:
        """右が先頭のスライダーにするか。両開き（左）以外は右始まり。"""
        if hasattr(self.parent_window, '_use_rtl_page_slider'):
            return self.parent_window._use_rtl_page_slider()
        return True

    def _apply_slider_direction(self):
        """スライダーの左右方向を表示モードに合わせて更新"""
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
            # 左が末尾、右が先頭
            self.button_layout.addWidget(self.last_button)
            self.button_layout.addWidget(self.first_button)
        else:
            self.button_layout.addWidget(self.first_button)
            self.button_layout.addWidget(self.last_button)

    def _apply_slider_fill_style(self, rtl: bool):
        """RTL時は青いバーを右起点にし、先頭が全選択に見えないようにする。

        QSlider の sub-page は常にハンドルより左、add-page は右。
        invertedAppearance はハンドル位置だけを反転するため、塗り色を入れ替える。
        """
        if rtl:
            # 右が先頭: ハンドルより右が進行(青)、左が残り(灰)
            sub_page = "palette(mid)"
            add_page = "palette(highlight)"
        else:
            sub_page = "palette(highlight)"
            add_page = "palette(mid)"
        self.page_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                height: 4px;
                margin: 10px 0;
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
                width: 16px;
                height: 16px;
                margin: -8px 0;
                border-radius: 10px;
            }}
        """)

    def go_to_first_page(self):
        """最初のページに移動"""
        if self.file_handler and self.file_handler.current_files:
            self._go_to_page(1)
    
    def go_to_last_page(self):
        """最後のページに移動"""
        if self.file_handler and self.file_handler.current_files:
            total_pages = len(self.file_handler.current_files)
            self._go_to_page(total_pages)

    def _go_to_page(self, page_number):
        """スライダーとスピンボックスを同期してページを変更"""
        self._updating = True
        try:
            self.page_slider.setValue(page_number)
            self.page_spinbox.setValue(page_number)
            self.change_page(page_number)
        finally:
            self._updating = False
    
    def refresh(self):
        """外部からの更新要求"""
        self.update_from_handler()
    
    def closeEvent(self, event):
        """ダイアログクローズ時の処理"""
        logger.info(get_log_text("page_slider_dialog_closed"))
        
        # 親ウィンドウのダイアログ参照をクリア
        if hasattr(self.parent_window, 'page_slider_dialog'):
            self.parent_window.page_slider_dialog = None
            
        super().closeEvent(event) 