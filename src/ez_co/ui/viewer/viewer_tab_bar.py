"""幅固定タブバーと閉じるボタン。"""
from PySide6.QtCore import QEvent, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QApplication, QTabBar


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

    def mouseReleaseEvent(self, event):
        """右ボタンの離しはメニューだけを出し、親のクリック割り当てへ渡さない。

        Args:
            event: マウス離しイベント。
        """
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            pos = event.position().toPoint()
            if self.tabAt(pos) >= 0:
                self.customContextMenuRequested.emit(pos)
            return
        super().mouseReleaseEvent(event)

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
