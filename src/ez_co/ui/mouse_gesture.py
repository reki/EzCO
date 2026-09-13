import logging
from PySide6.QtCore import QObject, QTimer, QPoint, Signal
from PySide6.QtGui import QMouseEvent
from ez_co.enums.arrows import Arrow
import math
from enum import Enum
from ez_co.enums.actions import get_action_display_name
from ez_co.utils.language_manager import get_text, get_log_text

logger = logging.getLogger(__name__)

class MouseGesture:
    def __init__(self, config=None):
        self.points = []
        self.directions = []  # 方向履歴
        self.active = False
        # 設定から判定距離を取得、デフォルトは30ピクセル
        if config and hasattr(config, 'viewer') and isinstance(config.viewer, dict):
            self.threshold = config.viewer.get("gesture_threshold", 50)
        else:
            self.threshold = 50  # ジェスチャー認識の閾値
        self._last_direction = None
        self._last_point = None  # 方向判定の起点
        self._reference_x = None  # 基準X座標
        self._reference_y = None  # 基準Y座標
        self._target_widget = None
        
        logger.debug(get_log_text("mouse_gesture_initialized", threshold=self.threshold))
    def start(self, pos: QPoint):
        """ジェスチャー開始"""
        self.points = [pos]
        self.directions = []
        self.active = True
        self._last_direction = None
        self._last_point = pos
        self._reference_x = None
        self._reference_y = None
        logger.debug(get_log_text("mouse_gesture_start_called", pos_x=pos.x(), pos_y=pos.y(), last_point_x=self._last_point.x(), last_point_y=self._last_point.y()))
    def update(self, pos: QPoint):
        """ジェスチャー更新"""
        if self.active:
            self.points.append(pos)
            if self._last_point is not None:
                # 起点から現在位置までの移動量を計算
                dx = pos.x() - self._last_point.x()
                dy = pos.y() - self._last_point.y()
                distance = math.sqrt(dx * dx + dy * dy)
                
                logger.debug(get_log_text("mouse_gesture_movement_info", last_point_x=self._last_point.x(), last_point_y=self._last_point.y(), pos_x=pos.x(), pos_y=pos.y(), dx=dx, dy=dy, distance=distance, threshold=self.threshold))
                logger.debug(get_log_text("mouse_gesture_current_directions", directions=self.directions, last_direction=self._last_direction))
                
                direction = None
                
                # 1回目：起点からの距離で判定
                if len(self.directions) == 0:
                    if distance >= self.threshold:
                        abs_dx = abs(dx)
                        abs_dy = abs(dy)
                        if abs_dx > abs_dy:
                            direction = Arrow.RIGHT.value if dx > 0 else Arrow.LEFT.value
                        else:
                            direction = Arrow.DOWN.value if dy > 0 else Arrow.UP.value
                        logger.debug(get_log_text("mouse_gesture_first_direction_detected", direction=direction, distance=distance, threshold=self.threshold))
                    else:
                        logger.debug(get_log_text("mouse_gesture_distance_insufficient", distance=distance, threshold=self.threshold))
                
                # 2回目以降：基準座標からの各軸距離で判定
                else:
                    last_direction = self.directions[-1]
                    
                    if last_direction == Arrow.DOWN.value:
                        # 下判定後：上向きはY軸、左右はX軸で判定
                        up_distance = self._reference_y - pos.y()
                        left_distance = self._reference_x - pos.x()
                        right_distance = pos.x() - self._reference_x
                        
                        logger.debug(get_log_text("mouse_gesture_check_from_down", reference_x=self._reference_x, reference_y=self._reference_y, up_distance=up_distance, left_distance=left_distance, right_distance=right_distance, threshold=self.threshold))
                        
                        if up_distance >= self.threshold:
                            direction = Arrow.UP.value
                        elif left_distance >= self.threshold:
                            direction = Arrow.LEFT.value
                        elif right_distance >= self.threshold:
                            direction = Arrow.RIGHT.value
                            
                    elif last_direction == Arrow.UP.value:
                        # 上判定後：下向きはY軸、左右はX軸で判定
                        down_distance = pos.y() - self._reference_y
                        left_distance = self._reference_x - pos.x()
                        right_distance = pos.x() - self._reference_x
                        
                        logger.debug(get_log_text("mouse_gesture_check_from_up", reference_x=self._reference_x, reference_y=self._reference_y, down_distance=down_distance, left_distance=left_distance, right_distance=right_distance, threshold=self.threshold))
                        
                        if down_distance >= self.threshold:
                            direction = Arrow.DOWN.value
                        elif left_distance >= self.threshold:
                            direction = Arrow.LEFT.value
                        elif right_distance >= self.threshold:
                            direction = Arrow.RIGHT.value
                            
                    elif last_direction == Arrow.LEFT.value:
                        # 左判定後：右向きはX軸、上下はY軸で判定
                        right_distance = pos.x() - self._reference_x
                        up_distance = self._reference_y - pos.y()
                        down_distance = pos.y() - self._reference_y
                        
                        logger.debug(get_log_text("mouse_gesture_check_from_left", reference_x=self._reference_x, reference_y=self._reference_y, right_distance=right_distance, up_distance=up_distance, down_distance=down_distance, threshold=self.threshold))
                        
                        if right_distance >= self.threshold:
                            direction = Arrow.RIGHT.value
                        elif up_distance >= self.threshold:
                            direction = Arrow.UP.value
                        elif down_distance >= self.threshold:
                            direction = Arrow.DOWN.value
                            
                    elif last_direction == Arrow.RIGHT.value:
                        # 右判定後：左向きはX軸、上下はY軸で判定
                        left_distance = self._reference_x - pos.x()
                        up_distance = self._reference_y - pos.y()
                        down_distance = pos.y() - self._reference_y
                        
                        logger.debug(get_log_text("mouse_gesture_check_from_right", reference_x=self._reference_x, reference_y=self._reference_y, left_distance=left_distance, up_distance=up_distance, down_distance=down_distance, threshold=self.threshold))
                        
                        if left_distance >= self.threshold:
                            direction = Arrow.LEFT.value
                        elif up_distance >= self.threshold:
                            direction = Arrow.UP.value
                        elif down_distance >= self.threshold:
                            direction = Arrow.DOWN.value
                
                # 新しい方向が検出された場合
                if direction and (not self.directions or self.directions[-1] != direction):
                    self.directions.append(direction)
                    self._last_direction = direction
                    
                    # 基準座標を更新
                    self._reference_x = pos.x()
                    self._reference_y = pos.y()
                    
                    logger.debug(get_log_text("mouse_gesture_direction_added", direction=direction, directions=self.directions))
                    logger.debug(get_log_text("mouse_gesture_reference_updated", reference_x=self._reference_x, reference_y=self._reference_y))
                    
                    # 判定位置を新しい起点にする
                    self._last_point = pos
                    self._update_gesture(direction)
                elif direction:
                    logger.debug(get_log_text("mouse_gesture_direction_unchanged", direction=direction, last_direction=self._last_direction))
    def end(self) -> str:
        """ジェスチャー終了"""
        if self.active:
            self.active = False
            logger.debug(get_log_text("mouse_gesture_end_called", directions=self.directions, points_count=len(self.points)))
            if self.points:
                logger.debug(get_log_text("mouse_gesture_first_last_points", first_x=self.points[0].x(), first_y=self.points[0].y(), last_x=self.points[-1].x(), last_y=self.points[-1].y()))
                logger.debug(get_log_text("mouse_gesture_total_movement", total_dx=self.points[-1].x()-self.points[0].x(), total_dy=self.points[-1].y()-self.points[0].y()))
            if self.directions:
                result = "".join(self.directions)
                logger.debug(get_log_text("mouse_gesture_final_result", result=result))
                self._end_gesture()
                return result
            else:
                logger.debug(get_log_text("mouse_gesture_no_directions_recorded"))
                return None
        return None
    def is_active(self) -> bool:
        """ジェスチャーがアクティブかどうか"""
        return self.active
    def _update_gesture(self, direction):
        logger.debug(get_log_text("mouse_gesture_update_gesture", direction=direction, target_widget=self._target_widget))
        if hasattr(self._target_widget, 'on_gesture_update'):
            gesture_action = self._get_gesture_action()
            logger.debug(get_log_text("mouse_gesture_call_on_gesture_update", gesture_action=gesture_action))
            self._target_widget.on_gesture_update(gesture_action)
    def _end_gesture(self):
        logger.debug(get_log_text("mouse_gesture_end_gesture", target_widget=self._target_widget))
        if hasattr(self._target_widget, 'on_gesture_end'):
            logger.debug(get_log_text("mouse_gesture_call_on_gesture_end"))
            self._target_widget.on_gesture_end()
    def _get_gesture_action(self):
        # directionsはArrow Enumの値（←→↑↓）のみで構成
        MAX_LEN = 8
        if self._target_widget and hasattr(self._target_widget, 'config') and hasattr(self._target_widget, 'gesture_map'):
            gesture_str = ''.join(self.directions)
            action = self._target_widget.config.gesture_map.get(gesture_str)
            if len(self.directions) > MAX_LEN:
                omit = len(self.directions) - MAX_LEN
                display_gesture = '…' + ''.join(self.directions[omit:])
            else:
                display_gesture = gesture_str
            if action:
                return f"{get_action_display_name(action)}：{display_gesture}"
            else:
                return f"{get_text('ui.unassigned')}：{display_gesture}"
        # fallback: 方向列挙
        if len(self.directions) > MAX_LEN:
            omit = len(self.directions) - MAX_LEN
            display_gesture = '…' + ''.join(self.directions[omit:])
        else:
            display_gesture = ''.join(self.directions)
        return display_gesture
    def set_target_widget(self, widget):
        logger.debug(get_log_text("mouse_gesture_set_target_widget", widget=widget))
        self._target_widget = widget 
    
    def set_threshold(self, threshold):
        """判定距離を動的に変更"""
        old_threshold = self.threshold
        self.threshold = threshold
        logger.debug(get_log_text("mouse_gesture_threshold_changed", old_threshold=old_threshold, new_threshold=threshold)) 