from typing import Optional, List
import logging
import time
from pathlib import Path
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSizePolicy, QApplication
)
from PySide6.QtCore import Qt, QPoint, QTimer, QEvent, Signal, QRect
from PySide6.QtGui import QPixmap, QImage, QMouseEvent, QWheelEvent, QPainter, QColor, QFont, QFontMetrics, QResizeEvent
from PIL import Image
from PIL.ImageQt import ImageQt as PILImageQt
from ez_co.config import Config
from ez_co.ui.mouse_gesture import MouseGesture
from ez_co.enums.actions import ACTIONS, Actions, get_action_display_name
from ez_co.enums.arrows import Arrow
from ez_co.enums.mouse_buttons import MouseButtons
from ez_co.utils.language_manager import get_text, get_log_text
logger = logging.getLogger(__name__)
class ImageView(QWidget):
    """画像表示ウィジェット"""
    # シグナル
    next_page_requested = Signal()
    prev_page_requested = Signal()
    zoom_changed = Signal(float)  # 拡大縮小率変更シグナル
    _paint_count = 0  # クラス変数でpaintEvent呼び出し回数をカウント
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.setup_ui()
        self.setup_connections()
        # 画像関連の変数
        self.current_image = None
        self.current_qimage = None  # QImageを保持
        self.zoom_factor = 1.0
        self.rotation_angle = 0  # 回転角度（0, 90, 180, 270度）
        self._is_updating = False
        self._display_cache = {}  # 表示用キャッシュ
        self._is_loading = False  # 画像読み込み中フラグ
        self._last_click_time = 0  # 最後のクリック時刻
        self._click_cooldown = 0.3  # クリック間のクールダウン時間（秒）
        self._mouse_repeat_timer = QTimer(self)
        self._mouse_repeat_timer.setSingleShot(False)
        self._mouse_repeat_timer.timeout.connect(self._on_mouse_repeat)
        self._mouse_repeat_action = None
        # マウスリピート設定をconfigから読み込む
        if config and hasattr(config, 'viewer'):
            self._mouse_repeat_initial_delay = config.viewer.get("mouse_repeat_initial_delay", 100)
            self._mouse_repeat_acceleration_start = config.viewer.get("mouse_repeat_acceleration_start", 100)
            self._mouse_repeat_min_interval = config.viewer.get("mouse_repeat_min_interval", 30)
        else:
            # デフォルト値（configがない場合）
            self._mouse_repeat_initial_delay = 100
            self._mouse_repeat_acceleration_start = 100
            self._mouse_repeat_min_interval = 30
        self._mouse_repeat_interval = self._mouse_repeat_initial_delay  # ms - 現在の間隔
        self._mouse_repeat_start_time = 0  # リピート開始時刻
        self._right_press_pos = None  # 右クリック押下位置
        self._gesture_direction = None
        self._gesture_action = None
        self._gesture_display_timer = QTimer(self)
        self._gesture_display_timer.setSingleShot(True)
        self._gesture_display_timer.timeout.connect(self._clear_gesture_display)
        # 画像移動関連の変数
        self.image_offset = QPoint(0, 0)  # 画像のオフセット位置
        self.last_mouse_pos = None  # 前回のマウス位置
        self.is_panning = False  # パンニング中かどうか
        try:
            self.mouse_gesture = MouseGesture(self.config)
        except Exception:
            self.mouse_gesture = None
        # 起動時に背景色を設定
        color = "#c0ffc0"
        if self.config:
            if hasattr(self.config, 'viewer') and isinstance(self.config.viewer, dict):
                color = self.config.viewer.get("background_color", "#c0ffc0")
            elif isinstance(self.config, dict):
                color = self.config.get("viewer", {}).get("background_color", "#c0ffc0")
        self.set_background_color(color)
    def setup_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)  # 画像を中央揃えにする
        # Configの背景色を使用（デフォルトは薄い緑）
        default_bg_color = "#c0ffc0"
        if self.config and "background_color" in self.config.viewer:
            default_bg_color = self.config.viewer["background_color"]
        self.image_label.setStyleSheet(f"background-color: {default_bg_color};")
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.image_label)
        # イベントフィルタをインストール
        self.image_label.installEventFilter(self)
        # マウストラッキングを有効にして、マウス移動イベントを受け取れるようにする
        self.setMouseTracking(True)
        self.image_label.setMouseTracking(True)
    def setup_connections(self):
        """シグナルとスロットの接続"""
        pass
    def set_image(self, image: Optional[Image.Image]):
        """画像を設定"""
        # キャッシュをクリア
        self._display_cache.clear()
        self.current_image = image
        if image:
            logger.info(get_log_text("image_view_setting_image", size=image.size))
            logger.info(get_log_text("debug_set_image_zoom_factor", zoom_factor=self.zoom_factor))
            # PIL.Image から QImage への変換（1回だけ）
            self.current_qimage = PILImageQt(image.convert("RGBA"))
            
            # 拡大時は画像の右上から表示を開始
            if self.zoom_factor > 1.0:
                logger.info(get_log_text("debug_set_image_new_page_start"))
                self._reset_image_position_to_top_right()
            
            self.update_image_display()
            self._is_loading = False  # 画像読み込み完了
            # 画像読み込み完了後、マウスボタンがまだ押されている場合はタイマーを再開
            self._resume_mouse_repeat_if_pressed()
        else:
            logger.info(get_log_text("image_view_clearing_image"))
            self.current_qimage = None
            self.image_label.clear()
            # 画像がない場合も背景色を反映
            color = "#000000"
            if self.config:
                if hasattr(self.config, 'viewer') and isinstance(self.config.viewer, dict):
                    color = self.config.viewer.get("background_color", "#000000")
                elif isinstance(self.config, dict):
                    color = self.config.get("viewer", {}).get("background_color", "#000000")
            self.image_label.setStyleSheet(f"background-color: {color};")
            self._is_loading = False  # 画像読み込み完了
            # 画像読み込み完了後、マウスボタンがまだ押されている場合はタイマーを再開
            self._resume_mouse_repeat_if_pressed()

    def combine_spread_images(self, left_image: Image.Image, right_image: Image.Image) -> Image.Image:
        """2枚の画像を横並びの1枚に合成する"""
        def to_rgba(img: Image.Image) -> Image.Image:
            if img.mode == "RGBA":
                return img
            return img.convert("RGBA")

        left = to_rgba(left_image)
        right = to_rgba(right_image)
        max_h = max(left.height, right.height)

        def fit_height(img: Image.Image, height: int) -> Image.Image:
            if img.height == height:
                return img
            width = max(1, int(img.width * height / img.height))
            return img.resize((width, height), Image.Resampling.LANCZOS)

        left = fit_height(left, max_h)
        right = fit_height(right, max_h)

        bg_color = "#c0ffc0"
        if self.config:
            if hasattr(self.config, 'viewer') and isinstance(self.config.viewer, dict):
                bg_color = self.config.viewer.get("background_color", "#c0ffc0")
            elif isinstance(self.config, dict):
                bg_color = self.config.get("viewer", {}).get("background_color", "#c0ffc0")
        bg = QColor(bg_color)
        combined = Image.new(
            "RGBA",
            (left.width + right.width, max_h),
            (bg.red(), bg.green(), bg.blue(), 255)
        )
        combined.paste(left, (0, 0), left)
        combined.paste(right, (left.width, 0), right)
        return combined

    def update_image_display(self):
        """画像の表示を更新"""
        if not self.current_qimage or self._is_updating:
            return
        if self.image_label.width() == 0 or self.image_label.height() == 0:
            return
        # fit_to_window_minimumが有効な場合は最小ズームを100%（全画面表示）に制限
        fit_min = True
        if self.config:
            if hasattr(self.config, 'viewer') and isinstance(self.config.viewer, dict):
                fit_min = self.config.viewer.get("fit_to_window_minimum", True)
            elif isinstance(self.config, dict):
                fit_min = self.config.get("viewer", {}).get("fit_to_window_minimum", True)
        # 画像の全画面表示時のズーム率を計算
        if fit_min:
            min_zoom = 1.0
        else:
            img_w, img_h = self.current_qimage.width(), self.current_qimage.height()
            lbl_w, lbl_h = self.image_label.width(), self.image_label.height()
            min_zoom = 1.0
            if img_w > 0 and img_h > 0:
                min_zoom = min(lbl_w / img_w, lbl_h / img_h, 1.0)
        logger.debug(get_log_text("debug_update_image_display_fit_min", fit_min=fit_min, min_zoom=min_zoom, zoom_factor=self.zoom_factor))
        if self.zoom_factor < min_zoom:
            logger.debug(get_log_text("debug_update_image_display_zoom_factor_lt_min", zoom_factor=self.zoom_factor, min_zoom=min_zoom))
            self.zoom_factor = min_zoom
            # ズームが最小値にリセットされた場合、オフセットもリセット
            self.image_offset = QPoint(0, 0)
        logger.debug(get_log_text("debug_update_image_display_zoom_factor_after", zoom_factor=self.zoom_factor))
        self._is_updating = True
        try:
            # キャッシュキーを生成（回転角度も含める）
            cache_key = f"{self.image_label.width()}x{self.image_label.height()}_{self.zoom_factor}_{self.rotation_angle}"
            # キャッシュをチェック
            if cache_key in self._display_cache:
                logger.debug(get_log_text("image_view_using_display_cache"))
                cached_pixmap = self._display_cache[cache_key]
            else:
                # 回転を適用
                rotated_qimage = self.current_qimage
                if self.rotation_angle != 0:
                    # QTransform を使用して回転
                    from PySide6.QtGui import QTransform
                    transform = QTransform()
                    transform.rotate(self.rotation_angle)
                    rotated_qimage = self.current_qimage.transformed(transform)
                
                # スケーリング
                scaled_size = self.image_label.size() * self.zoom_factor
                # QImage から直接 QPixmap を生成（メモリ効率が良い）
                cached_pixmap = QPixmap.fromImage(
                    rotated_qimage.scaled(
                        scaled_size,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                )
                # キャッシュに保存
                self._display_cache[cache_key] = cached_pixmap
                # キャッシュサイズを制限
                if len(self._display_cache) > 5:  # 最大5つまでキャッシュ
                    oldest_key = next(iter(self._display_cache))
                    del self._display_cache[oldest_key]
            # 画像移動機能：ズーム率が100%より大きい場合のみ移動を適用
            if self.zoom_factor > 1.0:
                logger.debug(get_log_text("debug_update_image_display_applying_movement", zoom_factor=self.zoom_factor))
                # 移動可能な範囲を計算
                label_size = self.image_label.size()
                pixmap_size = cached_pixmap.size()
                # 移動範囲の制限を計算
                max_offset_x = max(0, (pixmap_size.width() - label_size.width()) // 2)
                max_offset_y = max(0, (pixmap_size.height() - label_size.height()) // 2)
                logger.debug(get_log_text("debug_update_image_display_label_pixmap_size", label_size=label_size, pixmap_size=pixmap_size, max_offset_x=max_offset_x, max_offset_y=max_offset_y))
                # オフセットを制限範囲内に収める
                old_offset = self.image_offset
                self.image_offset.setX(max(-max_offset_x, min(max_offset_x, self.image_offset.x())))
                self.image_offset.setY(max(-max_offset_y, min(max_offset_y, self.image_offset.y())))
                if old_offset != self.image_offset:
                    logger.debug(get_log_text("debug_update_image_display_offset_clamped", old_offset=old_offset, new_offset=self.image_offset))
                # 画像の表示位置を調整するための新しいQPixmapを作成
                # 背景色で塗りつぶされたQPixmapを作成
                background_color = QColor(self.config.viewer["background_color"] if self.config else "#c0ffc0")
                display_pixmap = QPixmap(label_size)
                display_pixmap.fill(background_color)
                # 移動後の位置を計算
                display_x = (label_size.width() - pixmap_size.width()) // 2 + self.image_offset.x()
                display_y = (label_size.height() - pixmap_size.height()) // 2 + self.image_offset.y()
                logger.debug(get_log_text("debug_update_image_display_drawing_image", display_x=display_x, display_y=display_y))
                # 背景に画像を描画
                painter = QPainter(display_pixmap)
                painter.drawPixmap(display_x, display_y, cached_pixmap)
                painter.end()
                # 移動後の画像を表示
                self.image_label.setPixmap(display_pixmap)
                self.image_label.move(0, 0)  # QLabelは常に(0,0)に配置
            else:
                logger.debug(get_log_text("debug_update_image_display_no_movement", zoom_factor=self.zoom_factor))
                # ズーム率が100%以下の場合は中央表示
                self.image_label.setPixmap(cached_pixmap)
                self.image_label.move(0, 0)
                self.image_offset = QPoint(0, 0)
            logger.debug(get_log_text("image_view_displaying_image", size=cached_pixmap.size(), zoom_factor=self.zoom_factor, offset=self.image_offset))
        finally:
            self._is_updating = False
    def wheelEvent(self, event: QWheelEvent):
        # QLabelのイベントフィルタで処理するので何もしない
        pass
    def eventFilter(self, obj, event):
        if obj == self.image_label:
            if event.type() == QEvent.MouseButtonPress or event.type() == QEvent.MouseButtonDblClick:
                if event.button() == Qt.RightButton:
                    logger.info(get_log_text("image_view_gesture_right_pressed", pos=event.pos()))
                    self._right_press_pos = event.pos()
                    if self.mouse_gesture:
                        # マウスロック中でもジェスチャーを有効にする
                        main_window = self.window()
                        if hasattr(main_window, 'mouse_locked') and main_window.mouse_locked:
                            logger.info(get_log_text("image_view_gesture_mouse_lock_detected"))
                        if hasattr(main_window, 'set_gesture_active'):
                            main_window.set_gesture_active(True)
                        logger.info(get_log_text("image_view_gesture_start_called"))
                        self.mouse_gesture.start(event.pos())
                    self._gesture_direction = None
                    self._gesture_action = None
                    self.update()
                    return False
                # 左クリック等は従来通り
                logger.info(get_log_text("image_view_mouse_press_detected", x=event.x(), y=event.y(), button=event.button()))
                if not self.config:
                    logger.info(get_log_text("image_view_config_none_ignored"))
                    return False
                mouse_text = self.mouse_to_string(event)
                if mouse_text:
                    # 既存のタイマーを停止（重複を防ぐ）
                    self._stop_mouse_repeat()
                    # 画像読み込み中の場合はクリックを無視
                    if self._is_loading:
                        logger.info(get_log_text("image_view_click_ignored_loading"))
                        return False
                    # マウスリピートを開始（改ページアクションの場合も開始するが、読み込み中は停止される）
                    self._start_mouse_repeat(mouse_text)
                    # 最初のクリック処理（リピートとは別処理）
                    result = self._handle_mouse_shortcut(mouse_text, repeat=False)
                    return result
                # mouse_textが取得できない場合は従来の処理
                result = self._handle_action_event(event)
                return result
            elif event.type() == QEvent.MouseMove:
                # 右クリックジェスチャー処理のみ
                if self._right_press_pos is not None and self.mouse_gesture:
                    # マウスロック中でもジェスチャー処理を継続
                    main_window = self.window()
                    if hasattr(main_window, 'mouse_locked') and main_window.mouse_locked:
                        logger.info(get_log_text("image_view_gesture_mouse_lock_bypass"))
                    self.mouse_gesture.update(event.pos())
                    # 現在の方向を表示（リアルタイム）
                    if self.mouse_gesture.directions:
                        current_gesture = "".join(self.mouse_gesture.directions)
                        # 省略対応
                        MAX_LEN = 8
                        if len(current_gesture) > MAX_LEN:
                            display_gesture = '…' + current_gesture[-MAX_LEN:]
                        else:
                            display_gesture = current_gesture
                        # マッチ判定
                        action = None
                        if hasattr(self.config, 'gesture_map'):
                            action = self.config.gesture_map.get(current_gesture)
                        if action:
                            message = f"{get_action_display_name(action)}：{display_gesture}"
                        else:
                            message = f"{get_text('ui.unassigned')}：{display_gesture}"
                        self._gesture_direction = current_gesture
                        self._gesture_action = message
                        self._show_gesture_message(self._gesture_action)
                        self.update()
                    else:
                        logger.info(get_log_text("image_view_gesture_current_none"))
                    return False
                # 右クリックジェスチャー処理中以外では画像移動処理も実行
                if self.handle_mouse_move(event):
                    return True
                return False
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.RightButton:
                    logger.info(get_log_text("image_view_gesture_right_released", position=event.pos()))
                    if self._right_press_pos is not None:
                        dist = (event.pos() - self._right_press_pos).manhattanLength()
                        threshold = 10
                        logger.info(get_log_text("image_view_gesture_release_distance", distance=dist))
                        if dist < threshold:
                            mouse_text = self.mouse_to_string(event)
                            if mouse_text:
                                logger.info(get_log_text("image_view_gesture_treated_as_right_click"))
                                # ジェスチャー終了時にフラグをリセット
                                main_window = self.window()
                                if hasattr(main_window, 'set_gesture_active'):
                                    main_window.set_gesture_active(False)
                                self._right_press_pos = None
                                self._gesture_direction = None
                                self._gesture_action = None
                                self.update()
                                return self._handle_mouse_shortcut(mouse_text, repeat=False)
                            # ジェスチャー終了時にフラグをリセット
                            main_window = self.window()
                            if hasattr(main_window, 'set_gesture_active'):
                                main_window.set_gesture_active(False)
                            self._right_press_pos = None
                            self._gesture_direction = None
                            self._gesture_action = None
                            self.update()
                            return self._handle_action_event(event)
                        else:
                            if self.mouse_gesture:
                                gesture = self.mouse_gesture.end()
                                logger.info(get_log_text("image_view_gesture_final_release", gesture=gesture))
                                if gesture:
                                    self.handle_gesture(gesture)
                                    # handle_gestureでタイマーとメッセージ表示が処理されるので重複処理を削除
                                else:
                                    logger.info(get_log_text("image_view_gesture_no_recognized_release"))
                                    self._gesture_direction = None
                                    self._gesture_action = None
                                    self._hide_gesture_message()  # ジェスチャーが認識されなかった場合はメッセージを隠す
                                    self.update()
                            # ジェスチャー終了時にフラグをリセット
                            main_window = self.window()
                            if hasattr(main_window, 'set_gesture_active'):
                                main_window.set_gesture_active(False)
                            self._right_press_pos = None
                    return False
                else:
                    # 左クリックや他のボタンのリリース処理
                    self._stop_mouse_repeat()
                    # 注意: _is_loadingは画像読み込み完了時にのみリセット（ここではリセットしない）
                    # これにより、リリース後の誤動作を防ぐ
            elif event.type() == QEvent.Wheel:
                return self._handle_wheel_event(event)
        return super().eventFilter(obj, event)
    def mouse_to_string(self, event):
        if event.button() == Qt.LeftButton:
            return MouseButtons.LEFT.value
        elif event.button() == Qt.RightButton:
            return MouseButtons.RIGHT.value
        elif event.button() == Qt.MiddleButton:
            return MouseButtons.MIDDLE.value
        elif event.button() == Qt.XButton1:
            return MouseButtons.X1.value
        elif event.button() == Qt.XButton2:
            return MouseButtons.X2.value
        elif event.type() == QEvent.MouseButtonDblClick:
            # ダブルクリックを単クリックと同じ扱いにする
            if event.button() == Qt.LeftButton:
                return MouseButtons.LEFT.value
            elif event.button() == Qt.RightButton:
                return MouseButtons.RIGHT.value
            elif event.button() == Qt.MiddleButton:
                return MouseButtons.MIDDLE.value
            # その他のボタンの場合は従来通り
            return MouseButtons.DOUBLE.value
        return ""
    def _start_mouse_repeat(self, mouse_text):
        # 既存のタイマーを確実に停止
        self._stop_mouse_repeat()
        # 新しいリピートを開始
        self._mouse_repeat_action = mouse_text
        self._mouse_repeat_interval = self._mouse_repeat_initial_delay
        self._mouse_repeat_start_time = time.time() * 1000  # ms単位で開始時刻を記録
        self._mouse_repeat_timer.setInterval(self._mouse_repeat_initial_delay)
        self._mouse_repeat_timer.start()
        logger.info(get_log_text("image_view_mouse_repeat_started", mouse_text=mouse_text))
    def _stop_mouse_repeat(self):
        # タイマーを先に停止
        if self._mouse_repeat_timer.isActive():
            self._mouse_repeat_timer.stop()
        # アクションをクリアして、既にキューに入っているタイマーイベントを無効化
        self._mouse_repeat_action = None
        self._mouse_repeat_start_time = 0
        logger.info(get_log_text("image_view_mouse_repeat_stopped"))
    
    def _resume_mouse_repeat_if_pressed(self):
        """画像読み込み完了後、マウスボタンがまだ押されている場合はタイマーを再開"""
        if not self._mouse_repeat_action:
            return
        
        # マウスボタンがまだ押されているか確認
        mouse_buttons = QApplication.mouseButtons()
        is_left_pressed = mouse_buttons & Qt.LeftButton
        is_right_pressed = mouse_buttons & Qt.RightButton
        
        # 対応するボタンが押されている場合はタイマーを再開
        if self._mouse_repeat_action == MouseButtons.LEFT.value and is_left_pressed:
            logger.info(get_log_text("image_view_mouse_repeat_resumed_after_load"))
            self._mouse_repeat_start_time = time.time() * 1000  # 開始時刻をリセット
            self._mouse_repeat_interval = self._mouse_repeat_initial_delay
            self._mouse_repeat_timer.setInterval(self._mouse_repeat_initial_delay)
            self._mouse_repeat_timer.start()
        elif self._mouse_repeat_action == MouseButtons.RIGHT.value and is_right_pressed:
            logger.info(get_log_text("image_view_mouse_repeat_resumed_after_load"))
            self._mouse_repeat_start_time = time.time() * 1000  # 開始時刻をリセット
            self._mouse_repeat_interval = self._mouse_repeat_initial_delay
            self._mouse_repeat_timer.setInterval(self._mouse_repeat_initial_delay)
            self._mouse_repeat_timer.start()
        else:
            # ボタンが押されていない場合はタイマーを完全に停止
            self._stop_mouse_repeat()
    def _on_mouse_repeat(self):
        # 最初にアクションがクリアされていないか確認（最重要チェック）
        if not self._mouse_repeat_action:
            logger.info(get_log_text("image_view_mouse_repeat_cancelled_no_action"))
            # 念のためタイマーも停止
            if self._mouse_repeat_timer.isActive():
                self._mouse_repeat_timer.stop()
            return
        
        # 画像読み込み中の場合はアクションをスキップ（タイマーは継続）
        if self._is_loading:
            logger.info(get_log_text("image_view_mouse_repeat_skipped_loading"))
            return
        
        # マウスボタンがまだ押されているか確認
        mouse_buttons = QApplication.mouseButtons()
        is_left_pressed = mouse_buttons & Qt.LeftButton
        is_right_pressed = mouse_buttons & Qt.RightButton
        
        # 対応するボタンが押されていない場合はリピートを停止
        if self._mouse_repeat_action == MouseButtons.LEFT.value and not is_left_pressed:
            logger.info(get_log_text("image_view_mouse_repeat_stopped_button_released", button="LEFT"))
            self._stop_mouse_repeat()
            return
        elif self._mouse_repeat_action == MouseButtons.RIGHT.value and not is_right_pressed:
            logger.info(get_log_text("image_view_mouse_repeat_stopped_button_released", button="RIGHT"))
            self._stop_mouse_repeat()
            return
        
        # 経過時間を計算
        current_time = time.time() * 1000  # ms
        elapsed_time = current_time - self._mouse_repeat_start_time
        
        # 0.3秒（300ms）経過後から加速開始
        if elapsed_time > self._mouse_repeat_acceleration_start:
            # 加速度的に間隔を短くする（指数関数的減少）
            acceleration_time = elapsed_time - self._mouse_repeat_acceleration_start
            # 加速係数（時間経過と共に間隔が短くなる）
            acceleration_factor = max(0.3, 1.0 - (acceleration_time / 2000))  # 2秒で最小間隔まで加速
            new_interval = max(
                self._mouse_repeat_min_interval,
                int(self._mouse_repeat_initial_delay * acceleration_factor)
            )
            
            # 間隔が変更された場合のみタイマーを更新
            if new_interval != self._mouse_repeat_interval:
                self._mouse_repeat_interval = new_interval
                self._mouse_repeat_timer.setInterval(self._mouse_repeat_interval)
                logger.info(get_log_text("image_view_mouse_repeat_interval_updated", interval=self._mouse_repeat_interval, elapsed_time=elapsed_time))
        
        result = self._handle_mouse_shortcut(self._mouse_repeat_action, repeat=True)
        # リピート処理では改ページアクションが実行されてもリピートを継続する
    def _handle_mouse_shortcut(self, mouse_text, repeat=False):
        # 画像読み込み中の場合は無視（リピート処理でもチェック）
        if self._is_loading:
            logger.info(get_log_text("image_view_shortcut_ignored_loading"))
            return False
        
        shortcuts = None
        if self.config:
            if hasattr(self.config, 'shortcuts') and isinstance(self.config.shortcuts, dict):
                shortcuts = self.config.shortcuts
            elif isinstance(self.config, dict):
                shortcuts = self.config.get("shortcuts", {})
        
        if not shortcuts:
            return False
        
        for act, keys in shortcuts.items():
            if mouse_text in keys:
                if act == Actions.NEXT_PAGE.value:
                    logger.info(get_log_text("image_view_requesting_next_page_shortcut"))
                    # 改ページアクションの場合は読み込みフラグを設定
                    self._is_loading = True
                    # タイマーは停止しない（長押しの場合は継続）
                    self.next_page_requested.emit()
                    return True
                elif act == Actions.PREV_PAGE.value:
                    logger.info(get_log_text("image_view_requesting_prev_page_shortcut"))
                    # 改ページアクションの場合は読み込みフラグを設定
                    self._is_loading = True
                    # タイマーは停止しない（長押しの場合は継続）
                    self.prev_page_requested.emit()
                    return True
                elif act == Actions.ZOOM_IN.value:
                    # ズーム系のアクションは読み込みフラグを設定しない
                    self.zoom_in()
                    return True
                elif act == Actions.ZOOM_OUT.value:
                    # ズーム系のアクションは読み込みフラグを設定しない
                    self.zoom_out()
                    return True
                elif act in (
                    Actions.PAGE_MODE_SINGLE.value,
                    Actions.PAGE_MODE_SPREAD_RIGHT.value,
                    Actions.PAGE_MODE_SPREAD_LEFT.value,
                    Actions.TOGGLE_SPREAD.value,
                ):
                    if repeat:
                        return False
                    main_window = self.window()
                    if hasattr(main_window, 'handle_page_mode_action'):
                        main_window.handle_page_mode_action(act)
                    return True
                else:
                    if repeat:
                        return False
                    main_window = self.window()
                    if hasattr(main_window, "run_window_action") and main_window.run_window_action(act):
                        return True
        return False
    def _handle_action_event(self, event):
        if not self.current_image:
            logger.info(get_log_text("image_view_no_image_click_ignored"))
            return False
        
        # 画像読み込み中の場合は無視（最優先チェック）
        if self._is_loading:
            logger.info(get_log_text("image_view_click_ignored_loading"))
            return False
        
        # 連続クリックの制御
        current_time = time.time()
        if current_time - self._last_click_time < self._click_cooldown:
            logger.info(get_log_text("image_view_click_ignored_cooldown"))
            return False
        self._last_click_time = current_time
        
        action = None
        if self.config:
            shortcuts = None
            if hasattr(self.config, 'shortcuts') and isinstance(self.config.shortcuts, dict):
                shortcuts = self.config.shortcuts
            elif isinstance(self.config, dict):
                shortcuts = self.config.get("shortcuts", {})
            if shortcuts:
                # アクション→キー（リスト）形式から逆引き
                for act, keys in shortcuts.items():
                    if event.button() == Qt.LeftButton and MouseButtons.LEFT.value in keys:
                        action = act
                        break
                    elif event.button() == Qt.RightButton and MouseButtons.RIGHT.value in keys:
                        action = act
                        break
        logger.info(get_log_text("image_view_action_determined", action=action))
        if action == Actions.NEXT_PAGE.value:
            logger.info(get_log_text("image_view_requesting_next_page_action"))
            # 改ページアクションの場合は読み込みフラグを設定
            self._is_loading = True
            # タイマーは停止しない（長押しの場合は継続）
            self.next_page_requested.emit()
            return True
        elif action == Actions.PREV_PAGE.value:
            logger.info(get_log_text("image_view_requesting_prev_page_action"))
            # 改ページアクションの場合は読み込みフラグを設定
            self._is_loading = True
            # タイマーは停止しない（長押しの場合は継続）
            self.prev_page_requested.emit()
            return True
        elif action in (
            Actions.PAGE_MODE_SINGLE.value,
            Actions.PAGE_MODE_SPREAD_RIGHT.value,
            Actions.PAGE_MODE_SPREAD_LEFT.value,
            Actions.TOGGLE_SPREAD.value,
        ):
            main_window = self.window()
            if hasattr(main_window, 'handle_page_mode_action'):
                main_window.handle_page_mode_action(action)
            return True
        logger.info(get_log_text("image_view_click_no_page_action"))
        return False
    def _handle_wheel_event(self, event):
        if self._is_updating:
            return False
        delta = event.angleDelta().y()
        if delta > 0:
            wheel_text = MouseButtons.WHEEL_UP.value
        else:
            wheel_text = MouseButtons.WHEEL_DOWN.value
        shortcuts = None
        if self.config:
            if hasattr(self.config, 'shortcuts') and isinstance(self.config.shortcuts, dict):
                shortcuts = self.config.shortcuts
            elif isinstance(self.config, dict):
                shortcuts = self.config.get("shortcuts", {})
        if shortcuts:
            for act, keys in shortcuts.items():
                if wheel_text in keys:
                    if act == Actions.NEXT_PAGE.value:
                        logger.info(get_log_text("image_view_requesting_next_page_wheel"))
                        self._is_loading = True
                        self.next_page_requested.emit()
                        return True
                    elif act == Actions.PREV_PAGE.value:
                        logger.info(get_log_text("image_view_requesting_prev_page_wheel"))
                        self._is_loading = True
                        self.prev_page_requested.emit()
                        return True
                    elif act == Actions.ZOOM_IN.value:
                        self.zoom_in()
                        return True
                    elif act == Actions.ZOOM_OUT.value:
                        self.zoom_out()
                        return True
                    elif act in (
                        Actions.PAGE_MODE_SINGLE.value,
                        Actions.PAGE_MODE_SPREAD_RIGHT.value,
                        Actions.PAGE_MODE_SPREAD_LEFT.value,
                        Actions.TOGGLE_SPREAD.value,
                    ):
                        main_window = self.window()
                        if hasattr(main_window, 'handle_page_mode_action'):
                            main_window.handle_page_mode_action(act)
                        return True
        # デフォルトのズーム
        self.zoom_factor *= 1.1 if delta > 0 else 0.9
        logger.info(get_log_text("image_view_zoom_factor_changed", zoom_factor=self.zoom_factor))
        self.update_image_display()
        self.zoom_changed.emit(self.zoom_factor)
        return True
    def mousePressEvent(self, event: QMouseEvent):
        # 何もしない（QLabelのイベントフィルタで処理）
        pass
    def set_background_color(self, color: str):
        """背景色を設定"""
        if self.config:
            self.config.viewer["background_color"] = color
        self.image_label.setStyleSheet(f"background-color: {color};")
        # 画像移動中の場合、背景色の変更を反映
        if self.zoom_factor > 1.0:
            self.update_image_display()
    def set_images(self, images: list[Image.Image]):
        """複数画像を設定"""
        self.images = images
        self.current_index = 0
        self.scale = 1.0
        self.rotation = 0
        self.offset = QPoint(0, 0)
        self.update()
    def next_page(self):
        """Next page"""
        if self.current_index < len(self.images) - 1:
            self.current_index += 1
            self.rotation = 0
            self.update()
    def prev_page(self):
        """Previous page"""
        if self.current_index > 0:
            self.current_index -= 1
            self.rotation = 0
            self.update()
    def set_min_scale(self, scale: float):
        """最小スケールを設定"""
        self.min_scale = scale
        if self.scale < scale:
            self.scale = scale
            self.update()
    def reset_zoom(self):
        """ズームをリセット"""
        self.zoom_factor = 1.0
        self.reset_image_position()  # 画像位置もリセット
        self.update_image_display()
        self.zoom_changed.emit(self.zoom_factor)
    def reset_rotation(self):
        """回転をリセット"""
        self.rotation_angle = 0
        logger.info(get_log_text("image_view_rotation_reset"))
        # 表示キャッシュをクリア
        self._display_cache.clear()
        # 画像表示を更新
        self.update_image_display()
    def zoom_in(self):
        """Zoom in"""
        self.zoom_factor *= 1.1
        self.update_image_display()
        self.zoom_changed.emit(self.zoom_factor)
    def zoom_out(self):
        """Zoom out"""
        self.zoom_factor *= 0.9
        # ズームアウトで100%以下になった場合は位置をリセット
        if self.zoom_factor <= 1.0:
            self.reset_image_position()
        self.update_image_display()
        self.zoom_changed.emit(self.zoom_factor)
    def rotate(self, angle: int):
        """回転（90度単位）- 相対角度で回転"""
        self.rotation_angle = (self.rotation_angle + angle) % 360
        logger.info(get_log_text("image_view_rotate", angle=angle, new_rotation=self.rotation_angle))
        # 表示キャッシュをクリア（回転によって画像が変わるため）
        self._display_cache.clear()
        # 画像表示を更新
        self.update_image_display()

    def set_rotation(self, angle: int):
        """回転角度を直接設定"""
        self.rotation_angle = angle % 360
        logger.info(get_log_text("image_view_set_rotation", angle=angle, new_rotation=self.rotation_angle))
        # 表示キャッシュをクリア（回転によって画像が変わるため）
        self._display_cache.clear()
        # 画像表示を更新
        self.update_image_display()
    def set_page_mode(self, mode: str):
        """ページモード設定"""
        self.config.display.page_mode = mode
        self.update()
    def calculate_base_zoom_factor(self):
        """基本拡大率を計算（ウィンドウに対して画像が全表示できるのが100%）"""
        if self.original_pixmap is None:
            return
        window_ratio = self.width() / self.height()
        image_ratio = self.original_pixmap.width() / self.original_pixmap.height()
        if window_ratio > image_ratio:
            # ウィンドウが横長の場合
            self.base_zoom_factor = self.height() / self.original_pixmap.height()
        else:
            # ウィンドウが縦長の場合
            self.base_zoom_factor = self.width() / self.original_pixmap.width()
        logger.info(get_log_text("image_view_base_zoom_calculated", 
            base_zoom=f"{self.base_zoom_factor:.3f}", 
            window_size=f"{self.width()}x{self.height()}", 
            image_size=f"{self.original_pixmap.width()}x{self.original_pixmap.height()}"))
    def paintEvent(self, event):
        """徹底デバッグ: ウィジェット情報・描画範囲・親子関係など全てログ出力"""
        type_self = type(self)
        type_parent = type(self.parent()) if self.parent() else None
        type_window = type(self.window()) if self.window() else None
        self.__class__._paint_count += 1
        logger.debug(get_log_text("debug_gesture_paint_event_call_count", count=self._paint_count))
        logger.debug(get_log_text("debug_gesture_paint_event_self_info",
            widget_self=str(self),
            type_self=type_self,
            object_name=self.objectName(),
            pos=self.pos(),
            geometry=self.geometry(),
            size=self.size(),
            rect=self.rect(),
            is_visible=self.isVisible()
        ))
        logger.debug(get_log_text("debug_gesture_paint_event_parent_info", parent=self.parent(), type_parent=type_parent))
        logger.debug(get_log_text("debug_gesture_paint_event_window_info", window=self.window(), type_window=type_window))
        # 背景を黒で塗りつぶし
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), Qt.black)
        logger.debug(get_log_text("debug_gesture_fill_rect", rect=self.rect()))
        # 赤い四角を描画
        rect = QRect(10, 10, 50, 50)
        painter.fillRect(rect, Qt.red)
        logger.debug(get_log_text("debug_gesture_drew_red_rect", rect=rect))
        logger.debug(get_log_text("debug_gesture_paint_event_end"))
        super().paintEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        """マウス移動イベント"""
        # 右クリックジェスチャー処理中は画像移動を無効にする
        if self._right_press_pos is not None:
            return
        # 画像移動処理（ズーム率が100%より大きい場合）
        if self.handle_mouse_move(event):
            return
        super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event: QMouseEvent):
        """マウスリリースイベント"""
        if event.button() == Qt.LeftButton:
            self.dragging = False
    def resizeEvent(self, event: QResizeEvent):
        """リサイズイベントの処理"""
        super().resizeEvent(event)
        if self.current_qimage:
            self.update_image_display() 
    def set_config(self, config):
        self.config = config
        # MouseGestureの閾値を更新
        if self.mouse_gesture and config:
            if hasattr(config, 'viewer') and isinstance(config.viewer, dict):
                threshold = config.viewer.get("gesture_threshold", 50)
                self.mouse_gesture.set_threshold(threshold)
        # 背景色も反映
        if self.config:
            if hasattr(self.config, 'viewer') and isinstance(self.config.viewer, dict):
                self.set_background_color(self.config.viewer.get("background_color", "#000000"))
            elif isinstance(self.config, dict):
                self.set_background_color(self.config.get("viewer", {}).get("background_color", "#000000"))
        # マウスリピート設定を更新
        if config and hasattr(config, 'viewer'):
            self._mouse_repeat_initial_delay = config.viewer.get("mouse_repeat_initial_delay", 100)
            self._mouse_repeat_acceleration_start = config.viewer.get("mouse_repeat_acceleration_start", 100)
            self._mouse_repeat_min_interval = config.viewer.get("mouse_repeat_min_interval", 30)
    def keyPressEvent(self, event):
        action = None
        if self.config:
            shortcuts = None
            if hasattr(self.config, 'shortcuts') and isinstance(self.config.shortcuts, dict):
                shortcuts = self.config.shortcuts
            elif isinstance(self.config, dict):
                shortcuts = self.config.get("shortcuts", {})
            if shortcuts:
                key = event.text().upper() if event.text() else event.key()
                for act, keys in shortcuts.items():
                    if key in keys:
                        action = act
                        break
        logger.info(get_log_text("image_view_action_determined_key", action=action))
        if action == Actions.NEXT_PAGE.value:
            logger.info(get_log_text("image_view_requesting_next_page_key"))
            self.next_page_requested.emit()
        elif action == Actions.PREV_PAGE.value:
            logger.info(get_log_text("image_view_requesting_prev_page_key"))
            self.prev_page_requested.emit()
        elif action in (
            Actions.PAGE_MODE_SINGLE.value,
            Actions.PAGE_MODE_SPREAD_RIGHT.value,
            Actions.PAGE_MODE_SPREAD_LEFT.value,
            Actions.TOGGLE_SPREAD.value,
        ):
            main_window = self.window()
            if hasattr(main_window, 'handle_page_mode_action'):
                main_window.handle_page_mode_action(action)
        else:
            super().keyPressEvent(event)
    def handle_gesture(self, gesture):
        logger.info(get_log_text("image_view_gesture_handle_called", gesture=gesture))
        # ジェスチャーに応じたアクションをConfigから取得して発火
        if hasattr(self.config, 'gesture_map'):
            action = self.config.gesture_map.get(gesture)
            logger.info(get_log_text("image_view_gesture_lookup", gesture=gesture, action=action))
            if action:
                self._gesture_direction = gesture
                self._gesture_action = f"{get_action_display_name(action)}：{gesture}"
                logger.info(get_log_text("image_view_gesture_setting_display", direction=self._gesture_direction, action=self._gesture_action))
                self._gesture_display_timer.start(800)
                self.update()  # 強制的に再描画
                self._fire_action(action)
                return
        # 未割当の場合
        self._gesture_direction = gesture
        self._gesture_action = f"{get_text('ui.unassigned')}：{gesture}"
        logger.info(get_log_text("image_view_gesture_unassigned", direction=self._gesture_direction, action=self._gesture_action))
        self._gesture_display_timer.start(800)
        self.update()  # 強制的に再描画
        logger.info(get_log_text("image_view_gesture_no_action", gesture=gesture))
    def _fire_action(self, action):
        logger.info(get_log_text("image_view_gesture_fire_action", action=action))
        # アクション名に応じてシグナルやメソッドを呼ぶ
        if action == Actions.NEXT_PAGE.value:
            self.next_page_requested.emit()
        elif action == Actions.PREV_PAGE.value:
            self.prev_page_requested.emit()
        elif action == Actions.NEXT_COMIC.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'next_comic'):
                logger.info(get_log_text("image_view_gesture_main_window_next_comic"))
                main_window.next_comic()
            else:
                logger.info(get_log_text("image_view_gesture_no_next_comic"))
        elif action == Actions.PREV_COMIC.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'prev_comic'):
                logger.info(get_log_text("image_view_gesture_main_window_prev_comic"))
                main_window.prev_comic()
            else:
                logger.info(get_log_text("image_view_gesture_no_prev_comic"))
        elif action == Actions.FULLSCREEN.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'toggle_fullscreen'):
                logger.info(get_log_text("image_view_gesture_main_window_fullscreen"))
                main_window.toggle_fullscreen()
            else:
                logger.info(get_log_text("image_view_gesture_no_fullscreen"))
        elif action == Actions.CLOSE_APP.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'close_application'):
                logger.info(get_log_text("image_view_gesture_main_window_close"))
                main_window.close_application()
            else:
                logger.info(get_log_text("image_view_gesture_no_close"))
        elif action == Actions.FIRST_PAGE.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'first_page'):
                logger.info(get_log_text("image_view_gesture_main_window_first_page"))
                main_window.first_page()
            else:
                logger.info(get_log_text("image_view_gesture_no_first_page"))
        elif action == Actions.LAST_PAGE.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'last_page'):
                logger.info(get_log_text("image_view_gesture_main_window_last_page"))
                main_window.last_page()
            else:
                logger.info(get_log_text("image_view_gesture_no_last_page"))
        elif action == Actions.PAGE_SLIDER_DIALOG.value:
            # MainWindowのインスタンスを取得
            main_window = self.window()
            if hasattr(main_window, 'show_page_slider_dialog'):
                logger.info(get_log_text("image_view_gesture_main_window_page_slider_dialog"))
                main_window.show_page_slider_dialog()
            else:
                logger.info(get_log_text("image_view_gesture_no_page_slider_dialog"))
        elif action in (
            Actions.PAGE_MODE_SINGLE.value,
            Actions.PAGE_MODE_SPREAD_RIGHT.value,
            Actions.PAGE_MODE_SPREAD_LEFT.value,
            Actions.TOGGLE_SPREAD.value,
        ):
            main_window = self.window()
            if hasattr(main_window, 'handle_page_mode_action'):
                main_window.handle_page_mode_action(action)
        else:
            main_window = self.window()
            if hasattr(main_window, "run_window_action"):
                main_window.run_window_action(action)
        # 必要に応じて他のアクションも追加
    def _gesture_to_action_name(self, gesture):
        # ジェスチャー方向→アクション名（設定から動的に取得する想定）
        # ここでは仮でデフォルト割り当て
        mapping = {Arrow.LEFT.value: Actions.PREV_COMIC.value, Arrow.RIGHT.value: Actions.NEXT_COMIC.value, Arrow.DOWN.value: Actions.CLOSE_APP.value}
        if gesture in mapping:
            action_key = mapping[gesture]
            return f"{get_action_display_name(action_key)}：{gesture}"
        return f"?：{gesture}"
    def _clear_gesture_display(self):
        self._gesture_direction = None
        self._gesture_action = None
        self._hide_gesture_message()  # オーバーレイメッセージも隠す
        self.update()
    def _show_gesture_message(self, message):
        logger.info(get_log_text("image_view_show_gesture_message", message=message))
        main_window = self.window()
        if hasattr(main_window, 'show_overlay_message'):
            main_window.show_overlay_message(message)
    def _hide_gesture_message(self):
        logger.info(get_log_text("image_view_hide_gesture_message"))
        main_window = self.window()
        if hasattr(main_window, 'hide_overlay_message'):
            main_window.hide_overlay_message()
    def on_gesture_update(self, gesture_action):
        logger.info(get_log_text("image_view_gesture_update", gesture_action=gesture_action))
        self._show_gesture_message(gesture_action)
    def on_gesture_end(self):
        logger.info(get_log_text("image_view_gesture_end"))
        # ジェスチャー終了時はメッセージを隠さず、表示タイマーに任せる
        # self._hide_gesture_message()
    def handle_mouse_move(self, event):
        """マウス移動時の画像移動処理"""
        # マウスロックが有効な場合は画像移動を無効にする
        main_window = self.window()
        if hasattr(main_window, 'mouse_locked') and main_window.mouse_locked:
            return False
        # ズーム率が100%以下の場合は移動しない
        if self.zoom_factor <= 1.0:
            # logger.info(get_log_text("debug_handle_mouse_move_no_image"))
            return False
        # 画像が読み込まれていない場合は移動しない
        if not self.current_qimage:
            # logger.info(get_log_text("debug_handle_mouse_move_no_image"))
            return False
        # 初回のマウス移動時は位置を記録するだけ
        if self.last_mouse_pos is None:
            self.last_mouse_pos = event.pos()
            return False
        # マウスの移動量を計算
        delta = event.pos() - self.last_mouse_pos
        self.last_mouse_pos = event.pos()
        # 移動量が小さすぎる場合は無視（微細な振動を防ぐ）
        if abs(delta.x()) < 2 and abs(delta.y()) < 2:
            return False
        # 移動感度を調整（より滑らかな移動のため）
        sensitivity = self.config.viewer.get("image_move_sensitivity", 1.2) if self.config else 1.2
        adjusted_delta = delta * sensitivity
        logger.info(get_log_text("debug_handle_mouse_move_delta", delta=delta, adjusted_delta=adjusted_delta))
        # 画像のオフセットを更新（逆方向に移動）
        self.image_offset -= adjusted_delta
        # 画像表示を更新
        self.update_image_display()
        return True
    def reset_image_position(self):
        """画像位置をリセット"""
        self.image_offset = QPoint(0, 0)
        self.last_mouse_pos = None
        self.update_image_display() 
    
    def move_image_by_offset(self, offset_x: int, offset_y: int):
        """画像をオフセット分だけ移動"""
        if not self.current_qimage:
            return
        
        # 現在のオフセットに追加
        new_offset = self.image_offset + QPoint(offset_x, offset_y)
        
        # 移動範囲の制限を計算
        if self.zoom_factor > 1.0:
            # 拡大時のみ移動範囲を制限
            label_size = self.image_label.size()
            rotation_angle = self.rotation_angle % 360
            
            # 回転を考慮した画像サイズを計算
            original_size = self.current_qimage.size()
            if rotation_angle in [90, 270]:
                # 90度または270度回転時はサイズを入れ替え
                rotated_size = QSize(original_size.height(), original_size.width())
            else:
                rotated_size = original_size
            
            # スケール後のサイズを計算
            scaled_size = QSize(
                int(rotated_size.width() * self.zoom_factor),
                int(rotated_size.height() * self.zoom_factor)
            )
            
            # 移動可能な範囲を計算
            max_offset_x = max(0, (scaled_size.width() - label_size.width()) // 2)
            max_offset_y = max(0, (scaled_size.height() - label_size.height()) // 2)
            
            # 範囲内に制限
            new_offset.setX(max(-max_offset_x, min(max_offset_x, new_offset.x())))
            new_offset.setY(max(-max_offset_y, min(max_offset_y, new_offset.y())))
        
        self.image_offset = new_offset
        self.update_image_display()
    
    def _reset_image_position_to_top_right(self):
        """画像の表示位置を右上にリセット（拡大時のページ切り替え用）"""
        if not self.current_qimage or self.zoom_factor <= 1.0:
            logger.info(get_log_text("debug_image_position_not_reset_normal_zoom", zoom_factor=self.zoom_factor))
            return
        
        # 現在のラベルサイズを取得
        label_size = self.image_label.size()
        if label_size.width() == 0 or label_size.height() == 0:
            # ラベルサイズが未確定の場合は後で処理
            self.image_offset = QPoint(0, 0)
            return
        
        # 回転を考慮した画像サイズを取得
        img_size = self.current_qimage.size()
        if self.rotation_angle == 90 or self.rotation_angle == 270:
            # 90度または270度回転時はサイズを入れ替え
            img_size = img_size.transposed()
        
        # スケーリング後のサイズを計算
        scaled_size = img_size * self.zoom_factor
        
        # 移動可能な範囲を計算
        max_offset_x = max(0, (scaled_size.width() - label_size.width()) // 2)
        max_offset_y = max(0, (scaled_size.height() - label_size.height()) // 2)
        
        # 回転角度を考慮した右上表示のオフセットを計算
        # 回転後の画像での「右上」を表示する
        if self.rotation_angle == 0:
            # 0度：通常の右上
            offset_x = -max_offset_x  # 右端を表示
            offset_y = max_offset_y   # 上端を表示
        elif self.rotation_angle == 90:
            # 90度回転：時計回りに90度回転した状態での右上
            offset_x = -max_offset_x  # 右端を表示
            offset_y = -max_offset_y  # 上端を表示
        elif self.rotation_angle == 180:
            # 180度回転：上下左右が反転した状態での右上
            offset_x = max_offset_x   # 右端を表示
            offset_y = -max_offset_y  # 上端を表示
        elif self.rotation_angle == 270:
            # 270度回転：反時計回りに90度回転した状態での右上
            offset_x = max_offset_x   # 右端を表示
            offset_y = max_offset_y   # 上端を表示
        else:
            # 他の角度の場合は0度として扱う
            offset_x = -max_offset_x
            offset_y = max_offset_y
        
        self.image_offset = QPoint(offset_x, offset_y)
        logger.info(get_log_text("debug_image_position_reset_to_top_right", 
                                zoom_factor=self.zoom_factor,
                                rotation_angle=self.rotation_angle,
                                offset_x=offset_x, 
                                offset_y=offset_y)) 