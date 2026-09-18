from PySide6.QtWidgets import QDialog, QVBoxLayout, QScrollArea, QWidget, QGridLayout, QLabel, QSizePolicy, QCheckBox, QHBoxLayout
from PySide6.QtCore import Qt, QSize, QThread, Signal, QObject, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QColor, QFont
from PIL import Image, ImageQt
import os
import logging
from ez_co.utils.language_manager import get_log_text, get_text
from ez_co.handlers.virtual_path_handler import VirtualPathHandler
logger = logging.getLogger(__name__)
class ThumbnailLoader(QThread):
    thumbnail_loaded = Signal(int, QPixmap)
    def __init__(self, image_paths, thumb_size, file_handler=None):
        super().__init__()
        self.setObjectName("ImageListThumbnailLoader")
        self.image_paths = image_paths
        self.thumb_size = thumb_size
        self.file_handler = file_handler
    def run(self):
        for idx, path in enumerate(self.image_paths):
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
            except Exception:
                pixmap = None
            self.thumbnail_loaded.emit(idx, pixmap)
class LoadingWidget(QWidget):
    def __init__(self, size=(120, 120), parent=None):
        super().__init__(parent)
        # サムネイルサイズを設定
        self.setFixedSize(*size)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(128, 128, 128))
        painter.setPen(Qt.white)
        rect = self.rect()
        painter.drawText(rect, Qt.AlignCenter, "Image\nLoading")
class ImageListDialog(QDialog):
    def __init__(self, image_paths, parent=None, on_select=None, file_handler=None, config=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.image_list"))
        self.resize(800, 600)
        self.image_paths = image_paths
        self.on_select = on_select
        self.file_handler = file_handler
        self.config = config
        
        # 動的レイアウト用の変数
        self.base_thumb_size = 180  # 基本サムネイルサイズ
        self.min_cols = 1  # 最小列数
        self.max_cols = 4  # 最大列数
        self.thumb_size = (self.base_thumb_size, self.base_thumb_size)
        self.grid_cols = 4
        self.widgets = []
        self._loading_timer = None
        
        self.setup_ui()
        # 初期レイアウト計算（サイズが確定していない場合があるため、showEventでも実行）
        self._update_grid_layout()
        self.start_loading()
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # チェックボックス
        checkbox_layout = QHBoxLayout()
        self.close_after_select_checkbox = QCheckBox(get_text("ui.close_after_select"))
        
        # 設定から初期値を取得
        default_checked = True
        if self.config and hasattr(self.config, 'image_list'):
            default_checked = self.config.image_list.get("close_after_select", True)
        
        self.close_after_select_checkbox.setChecked(default_checked)
        
        # チェックボックスの状態変更時に設定を保存
        self.close_after_select_checkbox.stateChanged.connect(self._save_checkbox_state)
        
        checkbox_layout.addWidget(self.close_after_select_checkbox)
        checkbox_layout.addStretch()
        layout.addLayout(checkbox_layout)
        
        # スクロールエリア
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setSpacing(8)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll)
        
        # プレースホルダーは後で_update_grid_layoutで作成
    
    def showEvent(self, event):
        """ダイアログ表示時の処理"""
        super().showEvent(event)
        # 表示時に正しいレイアウトを適用
        QTimer.singleShot(10, self._calculate_and_update_layout)
    
    def resizeEvent(self, event):
        """ダイアログサイズ変更時の処理"""
        super().resizeEvent(event)
        # 少し遅延させてレイアウト更新（連続したリサイズを避ける）
        if hasattr(self, '_resize_timer'):
            self._resize_timer.stop()
        else:
            self._resize_timer = QTimer(self)
            self._resize_timer.timeout.connect(self._on_resize_finished)
            self._resize_timer.setSingleShot(True)
        self._resize_timer.start(100)  # 100ms後にレイアウト更新
    
    def _on_resize_finished(self):
        """リサイズ完了時の処理"""
        self._calculate_and_update_layout()
    
    def _calculate_optimal_layout(self):
        """現在のダイアログサイズに基づいて最適なレイアウトを計算"""
        if not hasattr(self, 'scroll'):
            return self.grid_cols, self.thumb_size
        
        # スクロールエリアの有効幅を取得（スクロールバー分を除外）
        available_width = self.scroll.viewport().width() - 20  # マージン考慮
        
        # 基本的なスペーシング
        spacing = 8
        
        # 最適な列数を計算（1〜6の範囲）
        optimal_cols = self.max_cols
        
        # 6列で基本サイズが入るかチェック
        required_width = (self.base_thumb_size * self.max_cols) + (spacing * (self.max_cols - 1))
        
        if required_width <= available_width:
            # 基本サイズ以上にできる場合は、サムネイルを拡大
            extra_space = available_width - required_width
            extra_per_thumb = extra_space // self.max_cols
            new_thumb_size = min(self.base_thumb_size + extra_per_thumb, 200)  # 最大200px
            optimal_cols = self.max_cols
        else:
            # 基本サイズで収まらない場合は列数を減らす
            new_thumb_size = self.base_thumb_size
            for cols in range(self.max_cols, self.min_cols - 1, -1):
                required_width = (new_thumb_size * cols) + (spacing * (cols - 1))
                if required_width <= available_width:
                    optimal_cols = cols
                    break
            else:
                optimal_cols = self.min_cols
        
        return optimal_cols, (new_thumb_size, new_thumb_size)
    
    def _calculate_and_update_layout(self):
        """レイアウト計算と更新"""
        new_cols, new_thumb_size = self._calculate_optimal_layout()
        
        # レイアウトが変更された場合のみ更新
        if new_cols != self.grid_cols or new_thumb_size != self.thumb_size:
            old_thumb_size = self.thumb_size
            old_cols = self.grid_cols
            self.grid_cols = new_cols
            self.thumb_size = new_thumb_size
            
            # レイアウトが変更された場合は完全に再読み込み
            # （既存画像を保持するより、確実な動作を優先）
            self._update_grid_layout()
            self._reload_thumbnails()
    

    
    def _update_grid_layout(self):
        """グリッドレイアウトを更新"""
        # 既存のウィジェットをクリア
        for widget in self.widgets:
            self.grid.removeWidget(widget)
            widget.deleteLater()
        self.widgets.clear()
        
        # 新しいプレースホルダーを追加
        for idx, path in enumerate(self.image_paths):
            widget = LoadingWidget(self.thumb_size)
            widget.mousePressEvent = lambda e, i=idx: self.thumbnail_clicked(e, i)
            row = idx // self.grid_cols
            col = idx % self.grid_cols
            self.grid.addWidget(widget, row, col)
            self.widgets.append(widget)
    
    def _reload_thumbnails(self):
        """サムネイルを再読み込み"""
        # 既存のタイマーを確実に停止・削除
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()
            self._loading_timer.deleteLater()
            self._loading_timer = None
        
        # 少し遅延させて新しい読み込みを開始
        QTimer.singleShot(50, self.start_loading)
    
    def start_loading(self):
        logger.info(get_log_text("image_list_start_loading", count=len(self.image_paths)))
        
        # 既存のタイマーがある場合は停止
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()
            self._loading_timer.deleteLater()
        
        # 新しいタイマーを作成
        self._thumb_idx = 0
        self._loading_timer = QTimer(self)
        self._loading_timer.timeout.connect(self._load_next_thumb)
        self._loading_timer.start(10)
    def _load_next_thumb(self):
        if self._thumb_idx >= len(self.image_paths):
            logger.info(get_log_text("image_list_all_thumbnails_loaded"))
            self._loading_timer.stop()
            return
        idx = self._thumb_idx
        path = self.image_paths[idx]
        logger.info(get_log_text("image_list_loading_thumbnail", index=idx, path=path))
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
                logger.info(get_log_text("image_list_thumbnail_loaded", path=path))
            else:
                logger.error(get_log_text("image_list_thumbnail_failed_no_data", path=path))
                pixmap = None
        except Exception as e:
            logger.error(get_log_text("image_list_thumbnail_failed_error", path=path, error=str(e)))
            pixmap = None
        self.set_thumbnail(idx, pixmap)
        self._thumb_idx += 1
    def set_thumbnail(self, idx, pixmap):
        logger.info(get_log_text("image_list_set_thumbnail", index=idx, pixmap_status='OK' if pixmap else 'None'))
        if pixmap:
            label = QLabel(self)
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(*self.thumb_size)
            label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            label.mousePressEvent = lambda e, i=idx: self.thumbnail_clicked(e, i)
            row = idx // self.grid_cols
            col = idx % self.grid_cols
            old_widget = self.widgets[idx]
            self.grid.removeWidget(old_widget)
            old_widget.deleteLater()
            self.grid.addWidget(label, row, col)
            self.widgets[idx] = label
            label.update()
    def thumbnail_clicked(self, event, idx):
        if event.button() != Qt.LeftButton:
            return
        if self.on_select:
            self.on_select(idx)
        
        # チェックボックスの状態に応じてダイアログを閉じる
        if self.close_after_select_checkbox.isChecked():
            self.accept()

    def refresh_file_list(self, new_image_paths, new_file_handler=None):
        """ファイルリストを更新"""
        self.image_paths = new_image_paths
        if new_file_handler:
            self.file_handler = new_file_handler
        
        # 既存のタイマーを確実に停止・削除
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()
            self._loading_timer.deleteLater()
            self._loading_timer = None
        
        # レイアウトを更新
        self._update_grid_layout()
        
        # 少し遅延させてサムネイル読み込みを再開
        QTimer.singleShot(50, self.start_loading)

    def _save_checkbox_state(self):
        """チェックボックスの状態を設定に保存"""
        if self.config and hasattr(self.config, 'image_list'):
            self.config.image_list["close_after_select"] = self.close_after_select_checkbox.isChecked()
            # メインウィンドウの設定保存を呼び出し
            if hasattr(self.parent(), 'save_config'):
                self.parent().save_config()