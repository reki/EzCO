"""開いているタブの一覧サイドバー。"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QEvent
from ez_co.utils.language_manager import get_text


class TabListToolbar(QWidget):
    """開いているタブの一覧サイドバー"""
    tab_activated = Signal(int)
    tab_close_requested = Signal(int)
    tab_menu_requested = Signal(int)

    def __init__(self, parent=None):
        """親を受け取り、一覧の画面を組み立てる。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        """タイトルとタブ一覧を配置する。"""
        self.setWindowTitle(get_text("ui.tab_list"))
        self.setMinimumWidth(250)
        self.setMaximumWidth(350)
        self.setFocusPolicy(Qt.NoFocus)
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        title_label = QLabel(get_text("ui.tab_list"))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        self.tab_list = QListWidget()
        self.tab_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_list.customContextMenuRequested.connect(self.show_context_menu)
        self.tab_list.itemClicked.connect(self.on_item_clicked)
        self.tab_list.viewport().installEventFilter(self)
        layout.addWidget(self.tab_list)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

    def refresh_tabs(self, titles, current_index: int):
        """一覧を差し替え、現在のタブを選ぶ。

        Args:
            titles: 表示するタブ名。
            current_index: 選択するタブの番号。範囲外なら選択しない。
        """
        self.tab_list.blockSignals(True)
        self.tab_list.clear()
        for title in titles:
            item = QListWidgetItem(title)
            item.setToolTip(title)
            self.tab_list.addItem(item)
        if 0 <= current_index < self.tab_list.count():
            self.tab_list.setCurrentRow(current_index)
        self.tab_list.blockSignals(False)

    def eventFilter(self, obj, event):
        """一覧上の中ボタンで、当たったタブを閉じる。

        Args:
            obj: イベントの対象。
            event: 受け取ったイベント。

        Returns:
            ビューポート上の中ボタンが項目に当たったとき True。それ以外は親の結果。
        """
        if obj is self.tab_list.viewport() and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                item = self.tab_list.itemAt(event.position().toPoint())
                if item is not None:
                    index = self.tab_list.row(item)
                    if index >= 0:
                        self.tab_close_requested.emit(index)
                    return True
        return super().eventFilter(obj, event)

    def on_item_clicked(self, item):
        """クリックされた項目のタブを開く要求を出す。

        Args:
            item: クリックされた一覧項目。
        """
        index = self.tab_list.row(item)
        if index >= 0:
            self.tab_activated.emit(index)

    def show_context_menu(self, pos):
        """項目上なら、そのタブのメニュー要求を出す。

        Args:
            pos: 一覧上の位置。
        """
        item = self.tab_list.itemAt(pos)
        if item is None:
            return
        index = self.tab_list.row(item)
        if index >= 0:
            self.tab_menu_requested.emit(index)
