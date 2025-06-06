from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QMessageBox, QHeaderView, QFileDialog, QCompleter
)
from PySide6.QtCore import Qt
import json
import logging
from ez_co.enums.actions import ACTION_LIST, get_action_display_name
from ez_co.ui.mouse_gesture import MouseGesture
from PySide6.QtGui import QColor
from ez_co.utils.path_utils import get_project_root
from ez_co.enums.arrows import Arrow
from ez_co.utils.language_manager import get_text, get_log_text

logger = logging.getLogger(__name__)
class AddGestureDialog(QDialog):
    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.gesture_register"))
        self.setMinimumSize(600, 400)
        self.gesture = None
        self.action = None
        self._gesture_str = ""
        self.mouse_gesture = MouseGesture()
        self.config = config
        logger.info(get_log_text("add_gesture_dialog_opened"))
        self.setup_ui()
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.info_label = QLabel(get_text("ui.gesture_draw_instruction"))
        layout.addWidget(self.info_label)
        self.gesture_label = QLabel("")
        # 設定反映
        ui_font = getattr(self.config, 'ui_font', {}) if self.config else {}
        font_family = ui_font.get('font_family', 'Meiryo')
        font_size = ui_font.get('font_size', 18)
        font_color = ui_font.get('font_color', '#0000ff')
        bg_color = ui_font.get('bg_color', '#ffffff')
        alpha = ui_font.get('alpha', 170)
        style = f"background-color: rgba({QColor(bg_color).red()},{QColor(bg_color).green()},{QColor(bg_color).blue()},{alpha/255:.3f}); color: rgba({QColor(font_color).red()},{QColor(font_color).green()},{QColor(font_color).blue()},{alpha/255:.3f}); font-size: {font_size}px; font-family: {font_family}; padding: 8px; border-radius: 8px;"
        self.gesture_label.setStyleSheet(style)
        layout.addWidget(self.gesture_label)
        self.action_combo = QComboBox()
        self.action_combo.setEditable(True)
        self.action_combo.setInsertPolicy(QComboBox.NoInsert)
        # 全てのアクションを順序通りに表示
        action_names = []
        for key in ACTION_LIST:
            display_name = get_action_display_name(key)
            self.action_combo.addItem(display_name, key)
            action_names.append(display_name)
        # 入力サジェスト（フィルター）機能を追加
        completer = QCompleter(action_names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.action_combo.setCompleter(completer)
        # 最初のアクションを選択
        if ACTION_LIST:
            self.action_combo.setCurrentIndex(0)
        layout.addWidget(self.action_combo)
        btns = QHBoxLayout()
        ok_btn = QPushButton(get_text("ui.ok"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(get_text("ui.cancel"))
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)
    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.mouse_gesture.start(event.pos())
            self._gesture_str = ""
            self.gesture_label.setText("")
    def mouseMoveEvent(self, event):
        if self.mouse_gesture.is_active():
            self.mouse_gesture.update(event.pos())
            gesture = self.mouse_gesture.end()  # 一時的に認識
            if gesture:
                self._gesture_str = gesture
                self.gesture_label.setText(gesture)
            self.mouse_gesture.active = True  # 継続
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.RightButton:
            gesture = self.mouse_gesture.end()
            if gesture:
                self._gesture_str = gesture
                self.gesture_label.setText(gesture)
    def accept(self):
        if not self._gesture_str:
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.gesture_input_required"))
            return
        # アクションの検証 - currentData()がNoneの場合は現在のテキストから検索
        action = self.action_combo.currentData()
        if action is None:
            # テキストが入力されている場合、対応するアクションを検索
            current_text = self.action_combo.currentText()
            action = None
            for act in ACTION_LIST:
                if get_action_display_name(act) == current_text:
                    action = act
                    break
            if action is None:
                QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.invalid_action"))
                return
        self.gesture = self._gesture_str
        self.action = action
        super().accept()
class GestureDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.gesture_settings"))
        self.setMinimumSize(600, 400)
        self.config = config
        self.gesture_map = config.gesture_map.copy() if hasattr(config, 'gesture_map') else {}
        logger.info(get_log_text("gesture_dialog_opened"))
        self.setup_ui()
        self.load_gestures()
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([get_text("ui.action"), get_text("ui.gesture")])
        # アクション列の幅を設定
        self.table.setColumnWidth(0, 250)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table)
        btns = QHBoxLayout()
        add_btn = QPushButton(get_text("ui.add"))
        add_btn.clicked.connect(self.add_gesture)
        del_btn = QPushButton(get_text("ui.delete"))
        del_btn.clicked.connect(self.remove_gesture)
        export_btn = QPushButton(get_text("ui.export"))
        export_btn.clicked.connect(self.export_gestures)
        import_btn = QPushButton(get_text("ui.import"))
        import_btn.clicked.connect(self.import_gestures)
        btns.addWidget(add_btn)
        btns.addWidget(del_btn)
        btns.addWidget(export_btn)
        btns.addWidget(import_btn)
        layout.addLayout(btns)
        # OK/キャンセルボタン
        ok_cancel = QHBoxLayout()
        ok_btn = QPushButton(get_text("ui.ok"))
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton(get_text("ui.cancel"))
        cancel_btn.clicked.connect(self.reject)
        ok_cancel.addWidget(ok_btn)
        ok_cancel.addWidget(cancel_btn)
        layout.addLayout(ok_cancel)
    def load_gestures(self):
        self.table.setRowCount(0)
        # ACTION_LISTの順序でアクションをソートして表示
        sorted_gestures = []
        for action in ACTION_LIST:
            for gesture, gesture_action in self.gesture_map.items():
                if gesture_action == action:
                    sorted_gestures.append((gesture, gesture_action))
        
        for gesture, action in sorted_gestures:
            row = self.table.rowCount()
            self.table.insertRow(row)
            item_action = QTableWidgetItem(get_action_display_name(action))
            item_action.setFlags(item_action.flags() & ~Qt.ItemIsEditable)
            item_gesture = QTableWidgetItem(gesture)
            item_gesture.setFlags(item_gesture.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, item_action)
            self.table.setItem(row, 1, item_gesture)
    def add_gesture(self):
        # configをAddGestureDialogに渡す
        dlg = AddGestureDialog(self, self.config)
        if dlg.exec() == QDialog.Accepted:
            gesture = dlg.gesture
            action = dlg.action
            if not gesture or not action:
                return
            if action not in ACTION_LIST:
                QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.invalid_action"))
                return
            if gesture in self.gesture_map:
                QMessageBox.warning(
                    self, get_text("dialogs.warning"),
                    get_text("ui.gesture_already_assigned").format(
                        gesture=gesture,
                        action=get_action_display_name(self.gesture_map[gesture]),
                    ),
                )
                return
            self.gesture_map[gesture] = action
            logger.info(get_log_text("gesture_added", gesture=gesture, action=action))
            self.load_gestures()
    def remove_gesture(self):
        row = self.table.currentRow()
        if row < 0:
            return
        gesture_item = self.table.item(row, 1)
        if gesture_item is None:
            return
        gesture = gesture_item.text()
        if gesture in self.gesture_map:
            del self.gesture_map[gesture]
            logger.info(get_log_text("gesture_removed", gesture=gesture))
            self.load_gestures()
    def export_gestures(self):
        path, _ = QFileDialog.getSaveFileName(self, get_text("ui.export"), "", "JSON Files (*.json)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.gesture_map, f, ensure_ascii=False, indent=2)
        logger.info(get_log_text("gestures_exported", path=path))
        QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.export_completed"))
    def import_gestures(self):
        path, _ = QFileDialog.getOpenFileName(self, get_text("ui.import"), "", "JSON Files (*.json)")
        if not path:
            return
        logger.info(get_log_text("gestures_import_attempt", path=path))
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError
            # バリデーション: アクションが存在するもののみ
            valid = {g: a for g, a in data.items() if a in ACTION_LIST and isinstance(g, str)}
            if not valid:
                logger.warning(get_log_text("gesture_validation_failed"))
                QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.no_valid_gestures"))
                return
            self.gesture_map = valid
            logger.info(get_log_text("gestures_imported", count=len(valid)))
            self.load_gestures()
            QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.import_completed"))
        except Exception as e:
            logger.error(get_log_text("gestures_import_failed", error=str(e)))
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.import_failed"))
    def get_gesture_map(self):
        return self.gesture_map.copy()

    def on_item_double_clicked(self, item):
        """アイテムがダブルクリックされた時の処理"""
        if item.column() != 0:  # アクション列以外はスキップ
            return
        
        row = item.row()
        # 現在のアクションとジェスチャーを取得
        current_action_name = item.text()
        gesture_item = self.table.item(row, 1)
        if not gesture_item:
            return
        gesture = gesture_item.text()
        
        # 現在のアクションを特定
        current_action = None
        for act in ACTION_LIST:
            if get_action_display_name(act) == current_action_name:
                current_action = act
                break
        
        if not current_action:
            return
        
        # コンボボックスを作成
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)
        
        # 全アクションを追加
        action_names = []
        for action in ACTION_LIST:
            display_name = get_action_display_name(action)
            combo.addItem(display_name, action)
            action_names.append(display_name)
        
        # 入力サジェスト機能を追加
        completer = QCompleter(action_names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        combo.setCompleter(completer)
        
        # 現在のアクションを選択
        for i in range(combo.count()):
            if combo.itemData(i) == current_action:
                combo.setCurrentIndex(i)
                break
        
        # コンボボックスをテーブルに設定
        self.table.setCellWidget(row, 0, combo)
        combo.setFocus()
        
        # 変更時の処理
        def on_action_changed():
            new_action = combo.currentData()
            if new_action is None:
                # テキストが入力されている場合、対応するアクションを検索
                current_text = combo.currentText()
                new_action = None
                for act in ACTION_LIST:
                    if get_action_display_name(act) == current_text:
                        new_action = act
                        break
            
            if new_action and new_action != current_action:
                # 古いジェスチャーを削除
                if gesture in self.gesture_map and self.gesture_map[gesture] == current_action:
                    del self.gesture_map[gesture]
                
                # 新しいアクションにジェスチャーを設定
                self.gesture_map[gesture] = new_action
                
                # テーブルを更新
                self.load_gestures()
        
        # フォーカスが外れた時やEnterキーが押された時に変更を適用
        combo.editTextChanged.connect(on_action_changed)
        combo.currentTextChanged.connect(on_action_changed)
        combo.focusOutEvent = lambda event: (on_action_changed(), super(QComboBox, combo).focusOutEvent(event)) 