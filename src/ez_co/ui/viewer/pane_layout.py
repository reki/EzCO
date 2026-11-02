"""タブを最大4面まで左右または上下に並べる。"""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

# 同時に出せる面の上限。
_MAX_PANES = 4
# タブのドラッグを表す MIME。
TAB_DRAG_MIME = "application/x-ezco-tab-index"


def zone_for_point(width, height, x, y):
    """面の中央を基準に、座標を左・右・上・下のどれかに分ける。

    Args:
        width: 面の幅。
        height: 面の高さ。
        x: 面の左からの位置。
        y: 面の上からの位置。

    Returns:
        left、right、up、down のいずれか。境界上は right、または down。
    """
    if width <= 0 or height <= 0:
        return "right"
    dx = x - (width / 2)
    dy = y - (height / 2)
    if abs(dx) >= abs(dy):
        return "left" if x < width / 2 else "right"
    return "up" if y < height / 2 else "down"



class _Leaf(QWidget):
    """1面分の枠。中にタブのウィジェットを1つ置く。"""

    def __init__(self, pane):
        """枠を作り、タブを中へ入れる。

        Args:
            pane: この面に出すタブ。
        """
        super().__init__()
        self.pane = pane
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(pane)

    def replace_pane(self, pane):
        """枠の中のタブを入れ替える。

        Args:
            pane: 新しく出すタブ。
        """
        current = self.pane
        if current is not None:
            current.setParent(None)
        self.pane = pane
        self.layout().addWidget(pane)


class _ZoneOverlay(QWidget):
    """ドロップ中に、落とす側の半分を塗る。"""

    def __init__(self, parent=None):
        """マウスを通す透明な重ねを作る。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._rect = None
        self.hide()

    def show_zone(self, rect):
        """塗る範囲を出して描き直す。

        Args:
            rect: 親の中での範囲。無ければ隠す。
        """
        self._rect = rect
        if rect is None:
            self.hide()
            return
        self.setGeometry(self.parentWidget().rect())
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event):
        """受け入れ位置を半透明で塗る。

        Args:
            event: 描画イベント。
        """
        if self._rect is None:
            return
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(58, 123, 213, 70))
        painter.drawRect(self._rect)


class PaneLayout(QWidget):
    """見えているタブを、分割木で最大4面まで並べる。"""

    def __init__(self, parent=None):
        """空の分割領域を作る。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._root = None
        self._drop_handler = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self._overlay = _ZoneOverlay(self)

    def set_drop_handler(self, handler):
        """タブをドロップしたときの処理を覚える。

        Args:
            handler: タブの識別子、方向、対象の面を受け取る呼び出し。
        """
        self._drop_handler = handler

    def visible_panes(self):
        """左上から横へ、見えているタブを返す。

        Returns:
            見えているタブの列。
        """
        return [leaf.pane for leaf in self._leaves()]

    def visible_count(self):
        """見えている面の数を返す。

        Returns:
            面の数。
        """
        return len(self.visible_panes())

    def set_single(self, pane):
        """そのタブだけを出し、ほかの面は畳む。

        Args:
            pane: 残すタブ。
        """
        for shown in list(self.visible_panes()):
            if shown is not pane:
                shown.setParent(None)
        self._discard_root()
        self._set_root(_Leaf(pane))

    def split(self, target, direction, incoming):
        """対象の面の指定側へタブを出す。5面にはしない。

        Args:
            target: 分割する面のタブ。
            direction: left、right、up、down。
            incoming: 新しい面に出すタブ。

        Returns:
            面を増やした、または移動したとき True。
        """
        if incoming is target or direction not in ("left", "right", "up", "down"):
            return False
        if not self._is_visible(target):
            return False
        incoming_visible = self._is_visible(incoming)
        if not incoming_visible and self.visible_count() >= _MAX_PANES:
            return False
        if incoming_visible:
            self.detach(incoming)
            if not self._is_visible(target):
                return False
        leaf = self._find_leaf(target)
        if leaf is None:
            return False
        horizontal = direction in ("left", "right")
        splitter = QSplitter(Qt.Orientation.Horizontal if horizontal else Qt.Orientation.Vertical)
        splitter.setChildrenCollapsible(False)
        new_leaf = _Leaf(incoming)
        before = direction in ("left", "up")
        first, second = (new_leaf, leaf) if before else (leaf, new_leaf)
        self._swap(leaf, splitter)
        splitter.addWidget(first)
        splitter.addWidget(second)
        splitter.setSizes([1, 1])
        return True

    def replace(self, target, incoming):
        """対象の面のタブを入れ替える。元の面にあればそこから外す。

        Args:
            target: 入れ替える面のタブ。
            incoming: 新しく出すタブ。

        Returns:
            入れ替えたとき True。
        """
        if incoming is target or not self._is_visible(target):
            return False
        if self._is_visible(incoming):
            self.detach(incoming)
            if not self._is_visible(target):
                self.set_single(incoming)
                return True
        leaf = self._find_leaf(target)
        if leaf is None:
            return False
        leaf.replace_pane(incoming)
        return True

    def arrange(self, panes):
        """タブを左上から横へ、2列の並びに置き直す。

        Args:
            panes: 並べるタブ。同じタブは1面だけ、5つ目以降は捨てる。
        """
        unique = []
        for pane in panes:
            if pane not in unique:
                unique.append(pane)
        unique = unique[:_MAX_PANES]
        for shown in list(self.visible_panes()):
            shown.setParent(None)
        self._discard_root()
        if not unique:
            return
        if len(unique) == 1:
            self.set_single(unique[0])
            return
        rows = [unique[index:index + 2] for index in range(0, len(unique), 2)]
        if len(rows) == 1:
            self._set_root(self._row(rows[0]))
            return
        vertical = QSplitter(Qt.Orientation.Vertical)
        vertical.setChildrenCollapsible(False)
        for row in rows:
            if len(row) == 1:
                vertical.addWidget(_Leaf(row[0]))
            else:
                vertical.addWidget(self._row(row))
        vertical.setSizes([1, 1])
        self._set_root(vertical)

    def detach(self, pane):
        """見えている面からタブを外し、空になった分割は畳む。

        Args:
            pane: 外すタブ。
        """
        leaf = self._find_leaf(pane)
        if leaf is None:
            return
        pane.setParent(None)
        parent = leaf.parentWidget()
        if parent is self or leaf is self._root:
            self._discard_root()
            return
        leaf.setParent(None)
        if isinstance(parent, QSplitter) and parent.count() == 1:
            only = parent.widget(0)
            self._swap(parent, only)
            parent.setParent(None)

    def pane_at(self, pos):
        """この領域の座標にあるタブを返す。

        Args:
            pos: このウィジェット上の位置。

        Returns:
            その位置のタブ。無ければ None。
        """
        for leaf in self._leaves():
            top_left = leaf.mapTo(self, QPoint(0, 0))
            if leaf.rect().translated(top_left).contains(pos):
                return leaf.pane
        return None

    def drop_zone(self, pos):
        """座標のタブと、その中のドロップ位置を返す。

        Args:
            pos: このウィジェット上の位置。

        Returns:
            (方向, タブ)。面が無ければ None。
        """
        for leaf in self._leaves():
            top_left = leaf.mapTo(self, QPoint(0, 0))
            rect = leaf.rect().translated(top_left)
            if not rect.contains(pos):
                continue
            direction = zone_for_point(rect.width(), rect.height(), pos.x() - rect.x(), pos.y() - rect.y())
            return (direction, leaf.pane)
        return None

    def neighbor(self, pane, direction):
        """指定方向で接している面を返す。その方向の端なら無い。

        Args:
            pane: 基準の面。
            direction: left、right、up、down。

        Returns:
            隣の面。無ければ None。
        """
        leaf = self._find_leaf(pane)
        if leaf is None or direction not in ("left", "right", "up", "down"):
            return None
        widget = leaf
        while True:
            parent = widget.parentWidget()
            if not isinstance(parent, QSplitter):
                return None
            horizontal = parent.orientation() == Qt.Orientation.Horizontal
            same_axis = horizontal if direction in ("left", "right") else not horizontal
            index = parent.indexOf(widget)
            toward = 0 if direction in ("left", "up") else 1
            if same_axis and index != toward and 0 <= toward < parent.count():
                near = self._near_leaf(parent.widget(toward), direction)
                return near.pane if near is not None else None
            widget = parent

    def dragEnterEvent(self, event):
        """タブのドラッグを面の中へ入れる。

        Args:
            event: ドラッグ進入。
        """
        if event.mimeData().hasFormat(TAB_DRAG_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        """落とす側の半分を塗り、タブのドラッグを受け入れる。

        Args:
            event: ドラッグ移動。
        """
        zone = self._edge_zone(event)
        if zone is None:
            self._overlay.show_zone(None)
            event.ignore()
            return
        direction, pane = zone
        leaf = self._find_leaf(pane)
        if leaf is not None:
            top_left = leaf.mapTo(self, QPoint(0, 0))
            rect = leaf.rect().translated(top_left)
            self._overlay.show_zone(self._zone_rect(rect, direction))
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        """受け入れ位置の塗りを消す。

        Args:
            event: ドラッグ離脱。
        """
        self._overlay.show_zone(None)
        event.accept()

    def dropEvent(self, event):
        """面の中へのドロップを処理へ渡す。

        Args:
            event: ドロップ。
        """
        self._overlay.show_zone(None)
        zone = self._edge_zone(event)
        if zone is None or self._drop_handler is None:
            event.ignore()
            return
        token = bytes(event.mimeData().data(TAB_DRAG_MIME)).decode("utf-8")
        if not token:
            event.ignore()
            return
        direction, pane = zone
        self._drop_handler(token, direction, pane)
        event.acceptProposedAction()

    def _edge_zone(self, event):
        """面の中のドロップ位置を返す。外は None。

        Args:
            event: ドラッグイベント。

        Returns:
            (方向, タブ)。面の外なら None。
        """
        if not event.mimeData().hasFormat(TAB_DRAG_MIME):
            return None
        return self.drop_zone(event.position().toPoint())

    def _zone_rect(self, rect, direction):
        """面の中で、方向に対応する半分を返す。

        Args:
            rect: 面の範囲。
            direction: left、right、up、down。

        Returns:
            塗る範囲。
        """
        mid_x = rect.width() // 2
        mid_y = rect.height() // 2
        if direction == "left":
            return rect.adjusted(0, 0, -(rect.width() - mid_x), 0)
        if direction == "right":
            return rect.adjusted(mid_x, 0, 0, 0)
        if direction == "up":
            return rect.adjusted(0, 0, 0, -(rect.height() - mid_y))
        if direction == "down":
            return rect.adjusted(0, mid_y, 0, 0)
        return rect

    def _near_leaf(self, widget, direction):
        """隣の部分で、接している枠を返す。

        Args:
            widget: 隣の分割または枠。
            direction: left、right、up、down。

        Returns:
            接している枠。無ければ None。
        """
        found = []

        def walk(item):
            """枠を左上から集める。

            Args:
                item: 今見ているウィジェット。
            """
            if isinstance(item, _Leaf):
                found.append(item)
                return
            if isinstance(item, QSplitter):
                for index in range(item.count()):
                    walk(item.widget(index))

        walk(widget)
        if not found:
            return None
        if direction in ("right", "down"):
            return found[0]
        return found[-1]

    def _row(self, panes):
        """タブを横一列の分割にする。

        Args:
            panes: 左から並べるタブ。

        Returns:
            横方向の分割。
        """
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        for pane in panes:
            splitter.addWidget(_Leaf(pane))
        splitter.setSizes([1] * len(panes))
        return splitter

    def _set_root(self, widget):
        """分割木の根を差し替える。

        Args:
            widget: 新しい根。
        """
        self._discard_root()
        self._root = widget
        self.layout().addWidget(widget)

    def _discard_root(self):
        """今の分割木を外す。タブ自体は消さない。"""
        if self._root is None:
            return
        self._root.setParent(None)
        self._root = None

    def _swap(self, old, new):
        """分割木の中のウィジェットを入れ替える。

        Args:
            old: 外すウィジェット。
            new: 代わりに置くウィジェット。
        """
        parent = old.parentWidget()
        if parent is self or old is self._root:
            self._set_root(new)
            return
        if isinstance(parent, QSplitter):
            index = parent.indexOf(old)
            parent.insertWidget(index, new)
            old.setParent(None)

    def _is_visible(self, pane):
        """タブが見えているかを返す。

        Args:
            pane: 調べるタブ。

        Returns:
            見えていれば True。
        """
        return self._find_leaf(pane) is not None

    def _find_leaf(self, pane):
        """タブを出している枠を返す。

        Args:
            pane: 探すタブ。

        Returns:
            枠。見えていなければ None。
        """
        for leaf in self._leaves():
            if leaf.pane is pane:
                return leaf
        return None

    def _leaves(self):
        """分割木の枠を、左上から順に返す。

        Returns:
            枠の列。
        """
        found = []

        def walk(widget):
            """子を左から、または上からたどる。

            Args:
                widget: 今見ているウィジェット。
            """
            if isinstance(widget, _Leaf):
                found.append(widget)
                return
            if isinstance(widget, QSplitter):
                for index in range(widget.count()):
                    walk(widget.widget(index))

        if self._root is not None:
            walk(self._root)
        return found
