"""キーボードとマウスのショートカットを割り当てるダイアログ。"""
from typing import Dict, List, Optional
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QComboBox, QLineEdit, QMessageBox, QHeaderView,
    QGroupBox, QFormLayout, QCheckBox, QSpinBox, QCompleter
)
from PySide6.QtCore import Qt, Signal, QStringListModel
from PySide6.QtGui import QKeySequence, QKeyEvent
from ez_co.enums.actions import (
    find_action_by_display_name,
    get_action_display_name,
    list_assignable_actions,
    list_bound_actions,
)
from ez_co.enums.mouse_buttons import MouseButtons
from ez_co.enums.keyboard_keys import key_to_string
from ez_co.config import Config
from ez_co.utils.language_manager import get_text
logger = logging.getLogger(__name__)
class ShortcutInputWidget(QLineEdit):
    """ショートカット入力用ウィジェット"""
    shortcut_changed = Signal(str)
    def __init__(self, parent=None):
        """プレースホルダと読み取り専用で、空のショートカットにする。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setPlaceholderText(get_text("ui.press_key"))
        self.setReadOnly(True)
        self.current_shortcut = ""

    def keyPressEvent(self, event: QKeyEvent):
        """キー入力イベント

        Args:
            event: キーイベント。文字列にできるときだけ表示と通知を更新する。
        """
        shortcut = key_to_string(event)
        if not shortcut:
            return

        self.current_shortcut = shortcut
        self.setText(shortcut)
        self.shortcut_changed.emit(shortcut)
        event.accept()


class ShortcutDialog(QDialog):
    """ショートカット設定ダイアログ"""
    def __init__(self, config, parent=None):
        """設定のショートカットをコピーして一覧を出す。

        Args:
            config: ショートカットを持つ設定。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.config = config
        self.shortcuts = config.shortcuts.copy() if hasattr(config, 'shortcuts') else {}
        self.setup_ui()
        self.load_shortcuts()

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.shortcut_settings"))
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout()
        self.setLayout(layout)
        # 説明ラベル
        info_label = QLabel(get_text("ui.shortcut_description"))
        layout.addWidget(info_label)
        # テーブル
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([get_text("ui.action"), get_text("ui.shortcut")])
        # アクション列の幅を設定
        self.table.setColumnWidth(0, 250)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.table)
        # ボタン
        button_layout = QHBoxLayout()
        add_btn = QPushButton(get_text("ui.add"))
        add_btn.clicked.connect(self.add_shortcut)
        button_layout.addWidget(add_btn)
        remove_btn = QPushButton(get_text("ui.delete"))
        remove_btn.clicked.connect(self.remove_shortcut)
        button_layout.addWidget(remove_btn)
        button_layout.addStretch()
        export_btn = QPushButton(get_text("ui.export"))
        export_btn.clicked.connect(self.export_shortcuts)
        button_layout.addWidget(export_btn)
        import_btn = QPushButton(get_text("ui.import"))
        import_btn.clicked.connect(self.import_shortcuts)
        button_layout.addWidget(import_btn)
        layout.addLayout(button_layout)
        # OK/キャンセルボタン
        ok_cancel_layout = QHBoxLayout()
        ok_btn = QPushButton(get_text("ui.ok"))
        ok_btn.clicked.connect(self.accept)
        ok_cancel_layout.addWidget(ok_btn)
        cancel_btn = QPushButton(get_text("ui.cancel"))
        cancel_btn.clicked.connect(self.reject)
        ok_cancel_layout.addWidget(cancel_btn)
        layout.addLayout(ok_cancel_layout)

    def update_table(self):
        """テーブルを更新"""
        self.table.clearContents()
        # 1ショートカット1行で展開
        rows = []
        for action in list_bound_actions(self.shortcuts):
            if action in self.shortcuts:
                for shortcut in self.shortcuts[action]:
                    rows.append((action, shortcut))
        self.table.setRowCount(len(rows))
        for row, (action, shortcut) in enumerate(rows):
            # アクション名（編集不可）
            action_name = get_action_display_name(action)
            item = QTableWidgetItem(action_name)
            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            item.setData(Qt.ItemDataRole.UserRole, action)
            self.table.setItem(row, 0, item)
            # ショートカット表示（編集不可）
            shortcut_item = QTableWidgetItem(shortcut)
            shortcut_item.setFlags(shortcut_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, shortcut_item)

    def add_shortcut(self):
        """ショートカットを追加"""
        dialog = AddShortcutDialog(self.shortcuts, self)
        if dialog.exec():
            # アクションの検証 - currentData()がNoneの場合は現在のテキストから検索
            action = dialog.action_combo.currentData()
            if action is None:
                action = find_action_by_display_name(dialog.action_combo.currentText())
                if action is None:
                    QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.invalid_action"))
                    return
            shortcut = dialog.shortcut_input.current_shortcut
            if not shortcut:
                QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.shortcut_input_required"))
                return
            owner = self._find_shortcut_owner(shortcut)
            if owner is not None:
                QMessageBox.warning(
                    self, get_text("dialogs.warning"),
                    get_text("ui.shortcut_already_assigned").format(
                        shortcut=shortcut,
                        action=get_action_display_name(owner),
                    ),
                )
                return
            # 新しいショートカットを追加
            if action not in self.shortcuts:
                self.shortcuts[action] = []
            self.shortcuts[action].append(shortcut)
            self.update_table()

    def _find_shortcut_owner(self, shortcut: str):
        """そのショートカットを持つアクションを返す。

        Args:
            shortcut: 探すショートカット文字列。

        Returns:
            アクション。無ければ None。
        """
        for existing_action, existing_shortcuts in self.shortcuts.items():
            if shortcut in (existing_shortcuts or []):
                return existing_action
        return None

    def remove_shortcut(self):
        """ショートカットを削除"""
        current_row = self.table.currentRow()
        if current_row >= 0:
            col_action = self.table.item(current_row, 0)
            col_shortcut = self.table.item(current_row, 1)
            if col_action and col_shortcut:
                action = col_action.data(Qt.ItemDataRole.UserRole) or find_action_by_display_name(col_action.text())
                shortcut = col_shortcut.text()
                if action and shortcut and shortcut in self.shortcuts[action]:
                    self.shortcuts[action].remove(shortcut)
                    if not self.shortcuts[action]:
                        del self.shortcuts[action]
            self.update_table()

    def load_shortcuts(self):
        """設定からショートカットを読み込み"""
        if hasattr(self.config, 'shortcuts'):
            self.shortcuts = self.config.shortcuts.copy()
        self.update_table()

    def get_shortcuts(self):
        """ショートカット設定を取得

        Returns:
            アクションからショートカット一覧への辞書。
        """
        return self.shortcuts

    def export_shortcuts(self):
        """ショートカットを YAML ファイルへ書く。"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import yaml
        path, _ = QFileDialog.getSaveFileName(self, get_text("ui.export_shortcuts"), "shortcuts.yaml", "YAML files (*.yaml *.yml)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump({"shortcuts": self.shortcuts}, f, allow_unicode=True)
            QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.shortcuts_saved").format(path=path))

    def import_shortcuts(self):
        """YAML からショートカットを読む。既定に無い項目は足し、上書きの確認のあと表を更新する。"""
        from PySide6.QtWidgets import QFileDialog, QMessageBox
        import yaml
        path, _ = QFileDialog.getOpenFileName(self, get_text("ui.import_shortcuts"), "", "YAML files (*.yaml *.yml)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if "shortcuts" in data:
                # デフォルト設定と比較して不足項目をチェック
                default_config = Config.get_default_config()
                original_shortcuts = data["shortcuts"].copy()
                # 不足項目を追加
                merged_shortcuts = default_config["shortcuts"].copy()
                merged_shortcuts.update(data["shortcuts"])
                # 追加された項目があるかチェック
                added_items = []
                for key, value in default_config["shortcuts"].items():
                    if key not in original_shortcuts:
                        added_items.append(key)
                # 不足項目がある場合はユーザーに通知
                if added_items:
                    message = get_text("ui.missing_shortcut_items_added").format(items=", ".join(added_items))
                    QMessageBox.information(self, get_text("ui.settings_items_added"), message)
                reply = QMessageBox.question(self, get_text("ui.overwrite_confirm"), get_text("ui.overwrite_current_shortcuts"), QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.shortcuts = merged_shortcuts
                    self.update_table()
                    QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.shortcuts_imported"))

    def on_item_double_clicked(self, item):
        """アイテムがダブルクリックされた時の処理

        Args:
            item: ダブルクリックされたセル。アクション列以外は何もしない。
        """
        if item.column() != 0:  # アクション列以外はスキップ
            return

        row = item.row()
        # 現在のアクションとショートカットを取得
        current_action_name = item.text()
        shortcut_item = self.table.item(row, 1)
        if not shortcut_item:
            return
        shortcut = shortcut_item.text()

        # 現在のアクションを特定
        current_action = item.data(Qt.ItemDataRole.UserRole) or find_action_by_display_name(current_action_name)
        if not current_action:
            return

        # コンボボックスを作成
        combo = QComboBox()
        combo.setEditable(True)
        combo.setInsertPolicy(QComboBox.NoInsert)

        # 全アクションを追加
        action_names = []
        for action in list_assignable_actions():
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
            """コンボボックスの選択へショートカットを移し、表を更新する。"""
            new_action = combo.currentData()
            if new_action is None:
                new_action = find_action_by_display_name(combo.currentText())

            if new_action and new_action != current_action:
                # 古いアクションからショートカットを削除
                if current_action in self.shortcuts and shortcut in self.shortcuts[current_action]:
                    self.shortcuts[current_action].remove(shortcut)
                    if not self.shortcuts[current_action]:
                        del self.shortcuts[current_action]

                # 新しいアクションにショートカットを追加
                if new_action not in self.shortcuts:
                    self.shortcuts[new_action] = []
                self.shortcuts[new_action].append(shortcut)

                # テーブルを更新
                self.update_table()

        # フォーカスが外れた時やEnterキーが押された時に変更を適用
        combo.editTextChanged.connect(on_action_changed)
        combo.currentTextChanged.connect(on_action_changed)
        combo.focusOutEvent = lambda event: (on_action_changed(), super(QComboBox, combo).focusOutEvent(event))


class AddShortcutDialog(QDialog):
    """ショートカット追加ダイアログ"""
    def __init__(self, shortcuts, parent=None):
        """既存のショートカットを受け取り、追加画面を出す。

        Args:
            shortcuts: 既存の割り当て。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.shortcuts = shortcuts
        self.setup_ui()

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.add_shortcut"))
        self.setModal(True)
        layout = QFormLayout()
        self.setLayout(layout)
        # アクション選択
        self.action_combo = QComboBox()
        self.action_combo.setEditable(True)
        self.action_combo.setInsertPolicy(QComboBox.NoInsert)
        # 全てのアクションを順序通りに表示
        action_names = []
        actions = list_assignable_actions()
        for action in actions:
            display_name = get_action_display_name(action)
            self.action_combo.addItem(display_name, action)
            action_names.append(display_name)
        # 入力サジェスト（フィルター）機能を追加
        completer = QCompleter(action_names)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.setFilterMode(Qt.MatchContains)
        self.action_combo.setCompleter(completer)
        # 最初のアクションを選択
        if actions:
            self.action_combo.setCurrentIndex(0)
        layout.addRow(get_text("ui.action_colon"), self.action_combo)
        # ショートカットタイプ選択
        self.shortcut_type_combo = QComboBox()
        self.shortcut_type_combo.addItem(get_text("ui.keyboard_colon"), "keyboard")
        self.shortcut_type_combo.addItem(get_text("ui.mouse_colon"), "mouse")
        self.shortcut_type_combo.currentTextChanged.connect(self.on_shortcut_type_changed)
        layout.addRow(get_text("ui.type_colon"), self.shortcut_type_combo)
        # キーボードショートカット入力
        self.keyboard_input = ShortcutInputWidget()
        layout.addRow(get_text("ui.keyboard_colon"), self.keyboard_input)
        # マウスショートカット選択
        self.mouse_combo = QComboBox()
        self.mouse_combo.addItem(get_text("ui.left_click"), MouseButtons.LEFT.value)
        self.mouse_combo.addItem(get_text("ui.right_click"), MouseButtons.RIGHT.value)
        self.mouse_combo.addItem(get_text("ui.middle_click"), MouseButtons.MIDDLE.value)
        # self.mouse_combo.addItem(get_text("ui.double_click"), MouseButtons.DOUBLE.value)
        self.mouse_combo.addItem(get_text("ui.wheel_up"), MouseButtons.WHEEL_UP.value)
        self.mouse_combo.addItem(get_text("ui.wheel_down"), MouseButtons.WHEEL_DOWN.value)
        self.mouse_combo.addItem(get_text("ui.x1_button_back"), MouseButtons.X1.value)
        self.mouse_combo.addItem(get_text("ui.x2_button_forward"), MouseButtons.X2.value)
        self.mouse_combo.setVisible(False)
        layout.addRow(get_text("ui.mouse_colon"), self.mouse_combo)
        # ボタン
        button_layout = QHBoxLayout()
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addRow(button_layout)

    def on_shortcut_type_changed(self, text):
        """ショートカットタイプが変更された時の処理

        Args:
            text: 選ばれた種類の表示文。キーボードの文言のときだけキー入力を出す。
        """
        if text == get_text("ui.keyboard_colon"):
            self.keyboard_input.setVisible(True)
            self.mouse_combo.setVisible(False)
        else:
            self.keyboard_input.setVisible(False)
            self.mouse_combo.setVisible(True)

    @property
    def shortcut_input(self):
        """現在選択されているショートカット入力ウィジェット

        Returns:
            キーボードなら入力欄。マウスなら current_shortcut だけを持つオブジェクト。
        """
        if self.shortcut_type_combo.currentData() == "keyboard":
            return self.keyboard_input
        else:
            # マウスの場合はComboBoxの値を返す
            return type('obj', (object,), {
                'current_shortcut': self.mouse_combo.currentData()
            })()


class EditShortcutDialog(QDialog):
    """ショートカット編集ダイアログ"""
    def __init__(self, action, shortcuts_list, shortcuts, parent=None):
        """対象アクションのショートカット一覧を編集する画面を出す。

        Args:
            action: 編集するアクション。
            shortcuts_list: そのアクションのショートカット。
            shortcuts: 全体の割り当て。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.action = action
        self.shortcuts = shortcuts_list.copy()
        self.shortcuts_dict = shortcuts
        self.setup_ui()

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("ui.shortcut_edit_title").format(action=get_action_display_name(self.action)))
        self.setModal(True)
        layout = QVBoxLayout()
        self.setLayout(layout)
        # ショートカットリスト
        shortcuts_group = QGroupBox(get_text("ui.shortcut_list"))
        shortcuts_layout = QVBoxLayout()
        shortcuts_group.setLayout(shortcuts_layout)
        self.shortcuts_list = []
        for i, shortcut in enumerate(self.shortcuts):
            shortcut_layout = QHBoxLayout()
            # ショートカットタイプ判定
            if shortcut.startswith("Mouse"):
                # マウスショートカット
                shortcut_combo = QComboBox()
                shortcut_combo.addItem(get_text("ui.left_click"), MouseButtons.LEFT.value)
                shortcut_combo.addItem(get_text("ui.right_click"), MouseButtons.RIGHT.value)
                shortcut_combo.addItem(get_text("ui.middle_click"), MouseButtons.MIDDLE.value)
                # shortcut_combo.addItem(get_text("ui.double_click"), MouseButtons.DOUBLE.value)
                shortcut_combo.addItem(get_text("ui.wheel_up"), MouseButtons.WHEEL_UP.value)
                shortcut_combo.addItem(get_text("ui.wheel_down"), MouseButtons.WHEEL_DOWN.value)
                shortcut_combo.addItem(get_text("ui.x1_button_back"), MouseButtons.X1.value)
                shortcut_combo.addItem(get_text("ui.x2_button_forward"), MouseButtons.X2.value)
                # 現在の値を設定
                for j in range(shortcut_combo.count()):
                    if shortcut_combo.itemData(j) == shortcut:
                        shortcut_combo.setCurrentIndex(j)
                        break
                shortcut_combo.currentTextChanged.connect(lambda text, idx=i: self.update_shortcut(idx, shortcut_combo.currentData()))
                shortcut_layout.addWidget(shortcut_combo)
            else:
                # キーボードショートカット
                shortcut_input = ShortcutInputWidget()
                shortcut_input.setText(shortcut)
                shortcut_input.current_shortcut = shortcut
                shortcut_input.shortcut_changed.connect(lambda text, idx=i: self.update_shortcut(idx, text))
                shortcut_layout.addWidget(shortcut_input)
            remove_button = QPushButton(get_text("ui.delete"))
            remove_button.clicked.connect(lambda checked, idx=i: self.remove_shortcut(idx))
            shortcut_layout.addWidget(remove_button)
            shortcuts_layout.addLayout(shortcut_layout)
            self.shortcuts_list.append(shortcut_layout)
        # 追加ボタン
        add_button = QPushButton(get_text("ui.add_shortcut"))
        add_button.clicked.connect(self.add_shortcut)
        shortcuts_layout.addWidget(add_button)
        layout.addWidget(shortcuts_group)
        # ボタン
        button_layout = QHBoxLayout()
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def update_shortcut(self, index, text):
        """ショートカットを更新

        Args:
            index: 更新する位置。
            text: 新しいショートカット。
        """
        if index < len(self.shortcuts):
            self.shortcuts[index] = text

    def remove_shortcut(self, index):
        """ショートカットを削除

        Args:
            index: 削除する位置。
        """
        if index < len(self.shortcuts):
            del self.shortcuts[index]
            self.setup_ui()  # UIを再構築

    def add_shortcut(self):
        """ショートカットを追加"""
        self.shortcuts.append("")
        self.setup_ui()  # UIを再構築
