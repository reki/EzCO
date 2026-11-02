"""1面のタブバーと、その面で選ばれているタブ。"""
from PySide6.QtCore import QPoint, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ez_co.ui.viewer.viewer_tab_bar import ViewerTabBar


class PaneGroup(QWidget):
    """面の上に、その面のタブだけを並べる。"""

    tabCloseRequested = Signal(int)
    currentChanged = Signal(int)
    tabMoved = Signal(int, int)
    gestureRecognized = Signal(int, str)
    contextMenuRequested = Signal(QPoint)
    tabDropped = Signal(str, int)
    tabClicked = Signal(int)

    def __init__(self, parent=None):
        """空のタブバーと、画像を置く領域を作る。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._panes = []
        self._shown = None
        self._guard = False
        self._bar = ViewerTabBar(self)
        self._bar.setMovable(True)
        self._bar.setTabsClosable(True)
        self._bar.setAcceptDrops(True)
        self._content = QWidget(self)
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        self._content_layout = content_layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._bar)
        layout.addWidget(self._content, 1)
        self._bar.tabCloseRequested.connect(self.tabCloseRequested)
        self._bar.currentChanged.connect(self._on_bar_current)
        self._bar.tabMoved.connect(self._on_bar_moved)
        self._bar.gestureRecognized.connect(self.gestureRecognized)
        self._bar.customContextMenuRequested.connect(self.contextMenuRequested)
        self._bar.tabDropped.connect(self.tabDropped)
        self._bar.tabBarClicked.connect(self._on_bar_clicked)

    def tab_bar(self):
        """この面のタブバーを返す。

        Returns:
            タブバー。
        """
        return self._bar

    def widget(self, index):
        """この面の位置にあるタブを返す。

        Args:
            index: この面の中の位置。

        Returns:
            そのタブ。範囲外なら None。
        """
        if 0 <= index < len(self._panes):
            return self._panes[index]
        return None

    def panes(self):
        """この面のタブを左から返す。

        Returns:
            タブの列。
        """
        return list(self._panes)

    def count(self):
        """この面のタブ数を返す。

        Returns:
            タブ数。
        """
        return len(self._panes)

    def selected(self):
        """この面で見えているタブを返す。

        Returns:
            選ばれているタブ。無ければ None。
        """
        return self.widget(self._bar.currentIndex())

    def tab_text(self, index):
        """この面のタブの表示名を返す。

        Args:
            index: この面の中の位置。

        Returns:
            表示名。
        """
        return self._bar.tabText(index)

    def set_tab_text(self, index, text):
        """この面のタブの表示名とツールチップを変える。

        Args:
            index: この面の中の位置。
            text: 表示名。
        """
        self._bar.setTabText(index, text)
        self._bar.setTabToolTip(index, text)

    def set_bar_visible(self, visible):
        """この面のタブバーを出すか隠す。

        Args:
            visible: 出すとき True。
        """
        self._bar.setVisible(visible)

    def set_movable(self, enabled):
        """この面のタブの並べ替えを許可する。

        Args:
            enabled: 並べ替えるとき True。
        """
        self._bar.setMovable(enabled)

    def set_tabs_closable(self, enabled):
        """この面のタブを閉じられるようにする。

        Args:
            enabled: 閉じるボタンを出すとき True。
        """
        self._bar.setTabsClosable(enabled)

    def set_gesture_recognizer(self, gesture):
        """この面の右ドラッグをジェスチャーとして記録させる。

        Args:
            gesture: 方向を記録する認識器。
        """
        self._bar.set_gesture_recognizer(gesture)

    def set_current_mark(self, color, gradient=False):
        """この面で選ばれているタブの色を置く。

        Args:
            color: 塗る色。塗らないときは None。
            gradient: 左から右へ薄くするとき True。
        """
        self._bar.set_current_mark(color, gradient)

    def add_pane(self, pane, title):
        """タブを末尾へ足す。最初の1枚は選ぶ。

        Args:
            pane: 足すタブ。
            title: 表示名。

        Returns:
            この面の中の位置。
        """
        self._panes.append(pane)
        self._guard = True
        try:
            index = self._bar.addTab(title)
            self._bar.setTabToolTip(index, title)
            if len(self._panes) == 1:
                self._bar.setCurrentIndex(0)
        finally:
            self._guard = False
        self._show_selected()
        return index

    def insert_pane(self, index, pane, title, select):
        """タブを指定位置へ入れる。

        Args:
            index: 入れる位置。
            pane: 入れるタブ。
            title: 表示名。
            select: 入れたタブを選ぶとき True。
        """
        index = max(0, min(index, len(self._panes)))
        self._panes.insert(index, pane)
        self._guard = True
        try:
            self._bar.insertTab(index, title)
            self._bar.setTabToolTip(index, title)
            if select:
                self._bar.setCurrentIndex(index)
        finally:
            self._guard = False
        self._show_selected()

    def remove_at(self, index):
        """この面からタブを外す。

        Args:
            index: 外す位置。

        Returns:
            外したタブ。範囲外なら None。
        """
        if not 0 <= index < len(self._panes):
            return None
        pane = self._panes.pop(index)
        self._guard = True
        try:
            self._bar.removeTab(index)
        finally:
            self._guard = False
        if pane is self._shown:
            pane.setParent(None)
            self._shown = None
        self._show_selected()
        return pane

    def select(self, pane):
        """この面のタブを選んで画像を出す。

        Args:
            pane: 選ぶタブ。
        """
        if pane not in self._panes:
            return
        self._guard = True
        try:
            self._bar.setCurrentIndex(self._panes.index(pane))
        finally:
            self._guard = False
        self._show_selected()

    def move_local(self, from_index, to_index):
        """この面の中でタブを動かす。

        Args:
            from_index: 移動前の位置。
            to_index: 移動後の位置。
        """
        if not 0 <= from_index < len(self._panes):
            return
        if not 0 <= to_index < len(self._panes):
            return
        self._guard = True
        try:
            self._bar.moveTab(from_index, to_index)
        finally:
            self._guard = False
        pane = self._panes.pop(from_index)
        self._panes.insert(to_index, pane)

    def reorder(self, order):
        """この面のタブを、元の位置の並びに組み直す。

        Args:
            order: 新しい順の、元の位置。
        """
        if order == list(range(len(self._panes))):
            return
        current = list(range(len(order)))
        self._guard = True
        try:
            for new_index, old_index in enumerate(order):
                now = current.index(old_index)
                if now == new_index:
                    continue
                self._bar.moveTab(now, new_index)
                item = current.pop(now)
                current.insert(new_index, item)
            self._panes = [self._panes[index] for index in order]
        finally:
            self._guard = False
        self._show_selected()

    def _show_selected(self):
        """選ばれているタブだけを画像領域へ出す。"""
        pane = self.selected()
        if pane is self._shown:
            return
        if self._shown is not None:
            self._shown.setParent(None)
        self._shown = pane
        if pane is not None:
            self._content_layout.addWidget(pane)

    def _on_bar_clicked(self, index):
        """タブのクリックを、選択が変わらなくても知らせる。

        Args:
            index: クリックした位置。
        """
        if self._guard or index < 0:
            return
        self.tabClicked.emit(index)

    def _on_bar_current(self, index):
        """タブバーの選択に、見えている画像を合わせる。

        Args:
            index: 選ばれた位置。
        """
        if self._guard or index < 0:
            return
        self._show_selected()
        self.currentChanged.emit(index)

    def _on_bar_moved(self, from_index, to_index):
        """タブバーの並べ替えに、この面の順を合わせる。

        Args:
            from_index: 移動前の位置。
            to_index: 移動後の位置。
        """
        if self._guard or not 0 <= from_index < len(self._panes):
            return
        pane = self._panes.pop(from_index)
        self._panes.insert(to_index, pane)
        self.tabMoved.emit(from_index, to_index)
