"""幅固定タブバーと閉じるボタン。"""
from PySide6.QtCore import QEvent, QMimeData, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QDrag, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QApplication, QTabBar

from ez_co.enums.config_defaults import ViewerDefaults
from ez_co.ui.viewer.pane_layout import TAB_DRAG_MIME


def current_tab_mark_color(color, alpha):
    """カレントタブに塗る色を返す。

    Args:
        color: 16進の色。読めなければ初期色。
        alpha: 0 から 255。数値でなければ初期値。

    Returns:
        塗る色。
    """
    parsed = QColor(str(color or ""))
    if not parsed.isValid():
        parsed = QColor(ViewerDefaults.CURRENT_TAB_COLOR.default)
    try:
        value = int(alpha)
    except (TypeError, ValueError):
        # 透過度が数値でなければ初期値にする。
        value = ViewerDefaults.CURRENT_TAB_ALPHA.default
    parsed.setAlpha(max(0, min(255, value)))
    return parsed


def current_tab_mark_brush(rect, color, gradient):
    """カレントタブに塗るブラシを返す。グラデーションは左から右へ薄くなる。

    Args:
        rect: 塗る範囲。
        color: 塗る色。無ければ塗らない。
        gradient: 左の透過度から右の 0 へ薄くするとき True。

    Returns:
        塗るブラシ。色が無ければ None。
    """
    if color is None:
        return None
    if not gradient:
        return QBrush(color)
    fade = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
    fade.setColorAt(0, color)
    end = QColor(color)
    end.setAlpha(0)
    fade.setColorAt(1, end)
    return QBrush(fade)


def _is_dark_color_scheme(widget) -> bool:
    """システムまたはパレットからダーク配色かを見る。

    Args:
        widget: パレットを見るウィジェット。

    Returns:
        ダークなら True。
    """
    hints = QApplication.styleHints()
    color_scheme = getattr(Qt, "ColorScheme", None)
    if hints is not None and color_scheme is not None and hasattr(hints, "colorScheme"):
        scheme = hints.colorScheme()
        if scheme == color_scheme.Dark:
            return True
        if scheme == color_scheme.Light:
            return False
    window = widget.palette().window().color()
    return window.lightness() < 128


class TabCloseButton(QAbstractButton):
    """枠なしの直線バツ。ダークモードは白、ライトモードは黒。"""

    # 閉じるボタンの一辺。
    BUTTON_SIZE = 16
    # バツを枠の内側へ寄せる量。
    CROSS_INSET = 3.5
    # バツの線の太さ。
    STROKE_WIDTH = 1.8

    def __init__(self, parent=None):
        """サイズとホバーを設定する。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFixedSize(self.BUTTON_SIZE, self.BUTTON_SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

    def paintEvent(self, event):
        """ホバー背景と直線のバツを描く。

        Args:
            event: 描画イベント。
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self.underMouse():
            hover = QColor(255, 255, 255, 40) if _is_dark_color_scheme(self) else QColor(0, 0, 0, 28)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(hover)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 3, 3)
        color = QColor("#ffffff") if _is_dark_color_scheme(self) else QColor("#000000")
        pen = QPen(color, self.STROKE_WIDTH)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        inset = self.CROSS_INSET
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        painter.drawLine(rect.topLeft(), rect.bottomRight())
        painter.drawLine(rect.topRight(), rect.bottomLeft())


class ViewerTabBar(QTabBar):
    """幅固定。長い名前は省略し、ホバーで全文をツールチップ表示する。"""

    gestureRecognized = Signal(int, str)
    tabDropped = Signal(str, int)

    # 通常タブの幅。
    TAB_WIDTH = 160
    # ピン留めタブの幅。
    PINNED_TAB_WIDTH = 80

    def __init__(self, parent=None):
        """幅固定、名前の省略、閉じるボタンの見た目を設定する。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._mark_color = None
        self._mark_gradient = False
        self._drag_index = -1
        self._split_drag_started = False
        self._gesture = None
        self._gesture_index = -1
        self.setExpanding(False)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setUsesScrollButtons(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setStyleSheet(
            "QTabBar::close-button { image: none; width: 16px; height: 16px; }"
            "QTabBar::close-button:hover { background: transparent; }"
        )
        hints = QApplication.styleHints()
        if hints is not None and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(self._refresh_close_buttons)

    def set_current_mark(self, color, gradient=False):
        """カレントタブに塗る色を置く。塗らないときは None。

        Args:
            color: 塗る色。塗らないときは None。
            gradient: 左から右へ薄くするとき True。
        """
        self._mark_color = color
        self._mark_gradient = bool(gradient)
        self.update()

    def set_gesture_recognizer(self, gesture):
        """タブバー上の右ドラッグを、この認識器で記録する。

        Args:
            gesture: 方向を記録する認識器。
        """
        self._gesture = gesture

    def paintEvent(self, event):
        """通常のタブを描き、分割中のカレントタブだけ背景色を重ねる。

        Args:
            event: 描画イベント。
        """
        super().paintEvent(event)
        selected = self.currentIndex()
        if selected < 0:
            return
        rect = self.tabRect(selected)
        brush = current_tab_mark_brush(rect, self._mark_color, self._mark_gradient)
        if brush is None:
            return
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(brush)
        painter.drawRect(rect)

    def tabSizeHint(self, index: int):
        """未固定は固定幅、固定タブは狭くする。

        Args:
            index: タブの番号。

        Returns:
            高さは親のまま、幅は固定と未固定で分けたサイズ。
        """
        size = super().tabSizeHint(index)
        return QSize(self._tab_width(index), size.height())

    def minimumTabSizeHint(self, index: int):
        """最小幅も表示幅に揃える。

        Args:
            index: タブの番号。

        Returns:
            高さは親のまま、幅は表示幅に揃えたサイズ。
        """
        size = super().minimumTabSizeHint(index)
        return QSize(self._tab_width(index), size.height())

    def tabInserted(self, index: int):
        """追加したタブに閉じるボタンを付ける。固定タブは付けない。

        Args:
            index: 追加されたタブの番号。
        """
        super().tabInserted(index)
        if self._pane_pinned(index):
            self._hide_close_button(index)
        else:
            self._install_close_button(index)

    def apply_pin_chrome(self):
        """固定タブの閉じるボタンを外し、未固定タブには付ける。"""
        for index in range(self.count()):
            if self._pane_pinned(index):
                self._hide_close_button(index)
            else:
                self._install_close_button(index)

    def changeEvent(self, event):
        """配色変更で閉じるボタンを描き直す。

        Args:
            event: 変更イベント。
        """
        super().changeEvent(event)
        theme_events = {
            QEvent.Type.PaletteChange,
            QEvent.Type.ApplicationPaletteChange,
            QEvent.Type.StyleChange,
        }
        if hasattr(QEvent.Type, "ThemeChange"):
            theme_events.add(QEvent.Type.ThemeChange)
        if event.type() in theme_events:
            self._refresh_close_buttons()

    def mousePressEvent(self, event):
        """中クリックでタブを閉じる。右クリックはタブを選ばず、親へ渡さない。

        Args:
            event: マウス押下イベント。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_index = self.tabAt(event.position().toPoint())
            self._split_drag_started = False
        if event.button() == Qt.MouseButton.RightButton and self._gesture is not None:
            self._gesture_index = self.tabAt(event.position().toPoint())
            self._gesture.start(event.position().toPoint())
            event.accept()
            return
        if event.button() == Qt.MouseButton.MiddleButton:
            index = self.tabAt(event.position().toPoint())
            if index >= 0:
                self.tabCloseRequested.emit(index)
                event.accept()
                return
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """タブバーの外へ出た左ドラッグは分割用にする。右ドラッグはジェスチャーを記録する。

        Args:
            event: マウス移動イベント。
        """
        if event.buttons() & Qt.MouseButton.RightButton and self._gesture is not None and self._gesture.is_active():
            self._gesture.update(event.position().toPoint())
            event.accept()
            return
        pos = event.position().toPoint()
        if (
            not self._split_drag_started
            and event.buttons() & Qt.MouseButton.LeftButton
            and self._drag_index >= 0
            and not self.rect().contains(pos)
        ):
            self._split_drag_started = True
            index = self._drag_index
            QTimer.singleShot(0, lambda: self._start_split_drag(index))
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """右ボタンの離しはメニューだけを出し、親のクリック割り当てへ渡さない。

        Args:
            event: マウス離しイベント。
        """
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            gesture = None
            if self._gesture is not None and self._gesture.is_active():
                gesture = self._gesture.end()
            index = self._gesture_index
            self._gesture_index = -1
            if gesture and index >= 0:
                self.gestureRecognized.emit(index, gesture)
                return
            pos = event.position().toPoint()
            if self.tabAt(pos) >= 0:
                self.customContextMenuRequested.emit(pos)
            return
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event):
        """別のタブバーからのタブを受け入れる。

        Args:
            event: ドラッグ進入。
        """
        if event.mimeData().hasFormat(TAB_DRAG_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event):
        """タブバー上の移動を受け入れる。

        Args:
            event: ドラッグ移動。
        """
        if event.mimeData().hasFormat(TAB_DRAG_MIME):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event):
        """落とされたタブの識別子と挿入位置を知らせる。

        Args:
            event: ドロップ。
        """
        if not event.mimeData().hasFormat(TAB_DRAG_MIME):
            event.ignore()
            return
        token = bytes(event.mimeData().data(TAB_DRAG_MIME)).decode("utf-8")
        if not token:
            event.ignore()
            return
        local = self.tabAt(event.position().toPoint())
        if local < 0:
            local = self.count()
        self.tabDropped.emit(token, local)
        event.acceptProposedAction()

    def _start_split_drag(self, index):
        """タブの識別子を載せて、分割用のドラッグを始める。マウス処理の外から呼ぶ。

        Args:
            index: ドラッグするタブの位置。
        """
        if index < 0:
            return
        if not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            return
        parent = self.parent()
        if parent is None:
            return
        pane = parent.widget(index)
        if pane is None:
            return
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(TAB_DRAG_MIME, str(id(pane)).encode("utf-8"))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    def _tab_width(self, index: int) -> int:
        """タブの表示幅を返す。

        Args:
            index: タブの番号。

        Returns:
            固定タブは狭い幅、それ以外は通常幅。
        """
        if self._pane_pinned(index):
            return self.PINNED_TAB_WIDTH
        return self.TAB_WIDTH

    def _pane_pinned(self, index: int) -> bool:
        """そのタブのペインが固定されているかを返す。

        Args:
            index: タブの番号。

        Returns:
            固定のとき True。親からペインを取れないときは False。
        """
        parent = self.parent()
        if parent is None or not hasattr(parent, "widget"):
            return False
        pane = parent.widget(index)
        return bool(getattr(pane, "pinned", False))

    def _hide_close_button(self, index: int):
        """タブの左右の閉じるボタンを外す。

        Args:
            index: タブの番号。
        """
        for position in (QTabBar.ButtonPosition.RightSide, QTabBar.ButtonPosition.LeftSide):
            if self.tabButton(index, position) is not None:
                self.setTabButton(index, position, None)

    def _close_button_position(self, index: int):
        """既存のタブボタン位置を返す。無ければ右側。

        Args:
            index: タブの番号。

        Returns:
            既にボタンがある側。無ければ右側。
        """
        for position in (QTabBar.ButtonPosition.RightSide, QTabBar.ButtonPosition.LeftSide):
            if self.tabButton(index, position) is not None:
                return position
        return QTabBar.ButtonPosition.RightSide

    def _install_close_button(self, index: int):
        """タブに直線バツの閉じるボタンを置く。

        Args:
            index: タブの番号。
        """
        position = self._close_button_position(index)
        existing = self.tabButton(index, position)
        if isinstance(existing, TabCloseButton):
            existing.update()
            return
        button = TabCloseButton(self)
        button.clicked.connect(lambda: self._on_close_button_clicked(button))
        self.setTabButton(index, position, button)

    def _refresh_close_buttons(self):
        """配色に合わせて閉じるボタンを再描画する。"""
        for index in range(self.count()):
            for position in (QTabBar.ButtonPosition.RightSide, QTabBar.ButtonPosition.LeftSide):
                button = self.tabButton(index, position)
                if isinstance(button, TabCloseButton):
                    button.update()

    def _on_close_button_clicked(self, button):
        """押された閉じるボタンのタブを閉じる。

        Args:
            button: 押された閉じるボタン。
        """
        for index in range(self.count()):
            for position in (QTabBar.ButtonPosition.RightSide, QTabBar.ButtonPosition.LeftSide):
                if self.tabButton(index, position) is button:
                    self.tabCloseRequested.emit(index)
                    return
