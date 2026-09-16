import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem,
    QFrame, QLabel, QMessageBox, QScrollArea, QSizePolicy, QMenu
)
from PySide6.QtCore import Qt, Signal, QTimer, QSize, QThread, QRect
from PySide6.QtGui import QFont, QIcon, QPixmap, QColor, QPainter
from PIL import Image, ImageQt
from ez_co.utils.language_manager import get_text, get_log_text
from ez_co.handlers.virtual_path_handler import VirtualPathHandler

logger = logging.getLogger(__name__)

class ThumbnailLoaderThread(QThread):
    """サムネイル読み込み用スレッド（可視範囲のみ）"""
    thumbnail_loaded = Signal(int, QPixmap)
    
    def __init__(self, image_paths, thumb_size, file_handler=None, start_index=0, end_index=None):
        super().__init__()
        self.setObjectName("ThumbnailLoaderThread")
        self.image_paths = image_paths
        self.thumb_size = thumb_size
        self.file_handler = file_handler
        self.start_index = start_index
        self.end_index = end_index if end_index is not None else len(image_paths)
        self.should_stop = False
    
    def stop(self):
        self.should_stop = True
    
    def run(self):
        for idx in range(self.start_index, min(self.end_index, len(self.image_paths))):
            if self.should_stop:
                break
            
            path = self.image_paths[idx]
            try:
                # 仮想パスかどうかで判定（current_archiveではなく）
                if VirtualPathHandler.is_virtual_path(path):
                    # アーカイブ内の画像の場合
                    img = self.file_handler._get_image_from_archive(str(path)) if self.file_handler else None
                else:
                    # ローカルファイルの場合
                    img = Image.open(path)
                
                if img:
                    img.thumbnail(self.thumb_size, Image.Resampling.LANCZOS)
                    qimg = ImageQt.ImageQt(img.convert("RGBA"))
                    pixmap = QPixmap.fromImage(qimg)
                else:
                    pixmap = None
            except Exception as e:
                logger.warning(get_log_text("image_slide_sidebar_thumbnail_failed", path=path, error=str(e)))
                pixmap = None
            
            if not self.should_stop:
                self.thumbnail_loaded.emit(idx, pixmap)

class ThumbnailWidget(QWidget):
    """サムネイル表示用ウィジェット"""
    clicked = Signal(int)
    
    def __init__(self, index, page_number, size=(200, 280), parent=None):
        super().__init__(parent)
        self.index = index
        self.page_number = page_number
        self.thumbnail_size = size
        self.pixmap = None
        self.is_current = False
        self.is_loaded = False  # サムネイルが読み込まれたかどうか
        
        self.setFixedSize(*size)
        self.setup_ui()
    
    def setup_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.setLayout(layout)
        
        # 画像表示用ラベル
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.image_label.setFixedSize(self.thumbnail_size[0] - 8, self.thumbnail_size[1] - 28)
        layout.addWidget(self.image_label)
        
        # 初期状態では読み込み中の表示
        self.image_label.setText("読み込み中...")
        self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f9f9f9; color: #999; font-size: 12px;")
        
        # ページ番号表示用ラベル
        self.page_label = QLabel(f"P.{self.page_number}")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setFixedHeight(24)
        self.page_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(self.page_label)
    
    def set_thumbnail(self, pixmap):
        """サムネイルを設定"""
        self.pixmap = pixmap
        self.is_loaded = True
        
        if pixmap:
            # サムネイルサイズに合わせてスケール
            scaled_pixmap = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled_pixmap)
            self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        else:
            # 読み込み失敗時の表示
            self.image_label.setText("画像\n読み込み\n失敗")
            self.image_label.setStyleSheet("border: 1px solid #ccc; background-color: #ffcccc; color: #666; font-size: 12px;")
    
    def set_current(self, is_current):
        """現在のページかどうかを設定"""
        self.is_current = is_current
        if is_current:
            self.setStyleSheet("background-color: #e0f0ff; border: 2px solid #4080ff; border-radius: 4px;")
            self.page_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #4080ff;")
        else:
            self.setStyleSheet("background-color: transparent; border: none;")
            self.page_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
    
    def mousePressEvent(self, event):
        """マウスクリック処理"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)
            event.accept()  # イベントを消費してメインウィンドウに伝播しないようにする
        else:
            super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        """マウスリリース処理"""
        if event.button() == Qt.LeftButton:
            event.accept()  # イベントを消費してダブルクリック等を防ぐ
        else:
            super().mouseReleaseEvent(event)

class ImageSlideSidebar(QWidget):
    """画像スライドサイドバー"""
    page_selected = Signal(int)  # page_index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.file_handler = None
        self.image_paths = []
        self.current_page = 0
        self.thumbnail_widgets = []
        self.thumbnail_loader = None
        self.loaded_thumbnails = set()  # ロード済みのサムネイルインデックス
        self.loading_queue = set()  # ロード中のサムネイルインデックス
        
        # サムネイルサイズ
        self.thumbnail_size = (200, 280)
        
        # 可視範囲の余裕（前後何個まで先読みするか）
        self.preload_buffer = 3
        
        logger.info(get_log_text("image_slide_sidebar_initialized"))
        self.setup_ui()
    
    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.image_slide"))
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        
        # フォーカスポリシーを設定（フォーカスを奪わないように）
        self.setFocusPolicy(Qt.NoFocus)
        
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # タイトル
        title_label = QLabel(get_text("ui.image_slide"))
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)
        
        # 区切り線
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # スクロールエリア
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # スクロールイベントを監視
        self.scroll_area.verticalScrollBar().valueChanged.connect(self.on_scroll_changed)
        self.scroll_area.verticalScrollBar().rangeChanged.connect(self.on_scroll_range_changed)
        
        # サムネイル表示用のコンテナ
        self.thumbnail_container = QWidget()
        self.thumbnail_layout = QVBoxLayout(self.thumbnail_container)
        self.thumbnail_layout.setContentsMargins(10, 10, 10, 10)
        self.thumbnail_layout.setSpacing(12)
        self.thumbnail_layout.setAlignment(Qt.AlignTop)
        
        self.scroll_area.setWidget(self.thumbnail_container)
        layout.addWidget(self.scroll_area)
        
        # ステータス表示
        self.status_label = QLabel(get_text("ui.no_images"))
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # サイズポリシーを設定
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
    
    def set_file_handler(self, file_handler):
        """ファイルハンドラーを設定"""
        self.file_handler = file_handler
        self.refresh_images()
    
    def refresh_images(self):
        """画像リストを更新"""
        # サイドバーが表示されていない場合は処理をスキップ
        if not self.isVisible():
            logger.info(get_log_text("image_slide_sidebar_refresh_skipped_not_visible"))
            return
        
        # 既存のサムネイルローダーを停止
        if self.thumbnail_loader and self.thumbnail_loader.isRunning():
            self.thumbnail_loader.stop()
            self.thumbnail_loader.wait()
        
        # 既存のサムネイルウィジェットをクリア
        self.clear_thumbnails()
        
        # ロード状態をリセット
        self.loaded_thumbnails.clear()
        self.loading_queue.clear()
        
        if not self.file_handler or not self.file_handler.current_files:
            self.status_label.setText(get_text("ui.no_images"))
            self.status_label.show()
            return
        
        self.image_paths = self.file_handler.current_files
        self.current_page = self.file_handler.current_index
        self.status_label.hide()
        
        # サムネイルウィジェットを作成（実際の画像はまだロードしない）
        self.create_thumbnail_widgets()
        
        # 先に現在ページへ寄せてから、そこを中心に遅延ロードする
        QTimer.singleShot(0, self._reveal_current_page)
        
        logger.info(get_log_text("image_slide_sidebar_refreshed", count=len(self.image_paths)))
    
    def clear_thumbnails(self):
        """サムネイルウィジェットをクリア"""
        for widget in self.thumbnail_widgets:
            self.thumbnail_layout.removeWidget(widget)
            widget.deleteLater()
        self.thumbnail_widgets.clear()
    
    def create_thumbnail_widgets(self):
        """サムネイルウィジェットを作成（画像はまだロードしない）"""
        for i, path in enumerate(self.image_paths):
            page_number = i + 1
            widget = ThumbnailWidget(i, page_number, self.thumbnail_size)
            widget.clicked.connect(self.on_thumbnail_clicked)
            self.thumbnail_layout.addWidget(widget)
            self.thumbnail_widgets.append(widget)
    
    def get_visible_range(self):
        """可視範囲のサムネイルインデックスを取得"""
        if not self.thumbnail_widgets:
            return 0, 0
        
        # スクロールエリアの可視領域を取得
        viewport = self.scroll_area.viewport()
        viewport_rect = QRect(0, 0, viewport.width(), viewport.height())
        
        visible_indices = []
        
        for i, widget in enumerate(self.thumbnail_widgets):
            # ウィジェットの位置をビューポート座標系に変換
            widget_pos = widget.mapTo(self.scroll_area.widget(), widget.rect().topLeft())
            widget_rect = QRect(widget_pos.x(), widget_pos.y(), widget.width(), widget.height())
            
            # スクロール位置を考慮
            scroll_y = self.scroll_area.verticalScrollBar().value()
            widget_rect.translate(0, -scroll_y)
            
            # 可視領域と交差するかチェック
            if viewport_rect.intersects(widget_rect):
                visible_indices.append(i)
        
        if not visible_indices:
            return 0, 0
        
        # プリロードバッファを追加
        start_index = max(0, min(visible_indices) - self.preload_buffer)
        end_index = min(len(self.thumbnail_widgets), max(visible_indices) + self.preload_buffer + 1)
        
        return start_index, end_index
    
    def load_visible_thumbnails(self):
        """可視範囲のサムネイルをロード"""
        # サイドバーが表示されていない場合は処理をスキップ
        if not self.isVisible():
            logger.info(get_log_text("image_slide_sidebar_load_skipped_not_visible"))
            return
            
        if not self.image_paths or not self.thumbnail_widgets:
            return
        
        start_index, end_index = self.get_visible_range()
        
        # ロードが必要なインデックスを特定
        indices_to_load = []
        for i in range(start_index, end_index):
            if i not in self.loaded_thumbnails and i not in self.loading_queue:
                indices_to_load.append(i)
        
        if not indices_to_load:
            return
        
        # ロード中としてマーク
        for i in indices_to_load:
            self.loading_queue.add(i)
        
        # サムネイル読み込みを開始
        self.start_thumbnail_loading(min(indices_to_load), max(indices_to_load) + 1)
    
    def start_thumbnail_loading(self, start_index, end_index):
        """指定範囲のサムネイル読み込みを開始"""
        if not self.image_paths:
            return
        
        if self.thumbnail_loader is not None:
            self.thumbnail_loader.stop()
            self.thumbnail_loader.wait()
            self.thumbnail_loader = None
        self.thumbnail_loader = ThumbnailLoaderThread(
            self.image_paths, 
            self.thumbnail_size, 
            self.file_handler,
            start_index,
            end_index
        )
        self.thumbnail_loader.thumbnail_loaded.connect(self.on_thumbnail_loaded)
        self.thumbnail_loader.start()
    
    def on_thumbnail_loaded(self, index, pixmap):
        """サムネイル読み込み完了時の処理"""
        if index < len(self.thumbnail_widgets):
            self.thumbnail_widgets[index].set_thumbnail(pixmap)
            self.loaded_thumbnails.add(index)
            self.loading_queue.discard(index)
    
    def on_scroll_changed(self, value):
        """スクロール変更時の処理"""
        # 少し遅延させてスクロールが落ち着いてから処理
        if hasattr(self, '_scroll_timer'):
            self._scroll_timer.stop()
        else:
            self._scroll_timer = QTimer()
            self._scroll_timer.setSingleShot(True)
            self._scroll_timer.timeout.connect(self.load_visible_thumbnails)
        
        self._scroll_timer.start(150)  # 150ms後に実行
    
    def on_scroll_range_changed(self, min_val, max_val):
        """スクロール範囲変更時の処理"""
        # レイアウトが完了した後に可視範囲のサムネイルをロード
        QTimer.singleShot(50, self.load_visible_thumbnails)
    
    def on_thumbnail_clicked(self, index):
        """サムネイルクリック時の処理"""
        logger.info(get_log_text("image_slide_sidebar_page_selected", page=index + 1))
        self.page_selected.emit(index)
    
    def set_current_page(self, page_index):
        """現在のページを設定"""
        self.current_page = page_index
        if not self.isVisible() or not self.thumbnail_widgets:
            return
        self._reveal_current_page()

    def _reveal_current_page(self):
        """現在ページをハイライトし、見える位置へスクロールしてから遅延ロードする。"""
        if not self.thumbnail_widgets:
            return
        for index, widget in enumerate(self.thumbnail_widgets):
            widget.set_current(index == self.current_page)
        if 0 <= self.current_page < len(self.thumbnail_widgets):
            self.scroll_to_page(self.current_page)
        else:
            self.load_visible_thumbnails()
    
    def scroll_to_page(self, page_index):
        """指定ページまでスクロール"""
        if 0 <= page_index < len(self.thumbnail_widgets):
            widget = self.thumbnail_widgets[page_index]
            # ウィジェットをスクロールエリアの見える位置に移動
            # ensureWidgetVisibleを使用してより確実にスクロール
            self.scroll_area.ensureWidgetVisible(widget, 50, 50)  # 50pxのマージンを設定
            
            # スクロール後に可視範囲を再ロード
            QTimer.singleShot(100, self.load_visible_thumbnails)
    
    def update_file_list(self, file_handler):
        """ファイルリストを更新"""
        # サイドバーが表示されていない場合は処理をスキップ
        if not self.isVisible():
            logger.info(get_log_text("image_slide_sidebar_update_file_list_skipped_not_visible"))
            # ただし、ファイルハンドラーは保存しておく（表示時に使用）
            self.file_handler = file_handler
            return
            
        self.set_file_handler(file_handler)
    
    def showEvent(self, event):
        """サイドバーが表示された時の処理"""
        super().showEvent(event)
        if self.file_handler and self.file_handler.current_files and not self.thumbnail_widgets:
            logger.info(get_log_text("image_slide_sidebar_show_event_refresh_needed"))
            QTimer.singleShot(0, self.refresh_images)
        else:
            QTimer.singleShot(0, self._reveal_current_page)
    
    def closeEvent(self, event):
        """クローズ時の処理"""
        # サムネイルローダーを停止
        if self.thumbnail_loader and self.thumbnail_loader.isRunning():
            self.thumbnail_loader.stop()
            self.thumbnail_loader.wait()
        super().closeEvent(event) 