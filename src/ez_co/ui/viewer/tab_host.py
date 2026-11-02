"""面ごとのタブバーと、最大4面の分割領域。"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ez_co.enums.config_defaults import ViewerDefaults
from ez_co.ui.viewer.pane_focus import PaneFocus
from ez_co.ui.viewer.pane_group import PaneGroup
from ez_co.ui.viewer.pane_layout import PaneLayout
from ez_co.ui.viewer.tab_commands import regroup_order
from ez_co.ui.viewer.viewer_tab_bar import current_tab_mark_color


class TabHost(QWidget):
    """各面のタブバーと、ショートカットが効くタブ。"""

    tabCloseRequested = Signal(int)
    currentChanged = Signal(int)
    gestureRecognized = Signal(int, str)
    tabContextMenuRequested = Signal(int)
    groupTabMoved = Signal(object, int, int)

    def __init__(self, parent=None):
        """空の分割領域を作る。タブバーは面ができてからその上に出す。

        Args:
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self._ids = {}
        self._focus = PaneFocus()
        self._guard = False
        self._movable = True
        self._closable = True
        self._gesture = None
        self._bars_allowed = True
        self._mark_color = ViewerDefaults.CURRENT_TAB_COLOR.default
        self._mark_alpha = ViewerDefaults.CURRENT_TAB_ALPHA.default
        self._mark_gradient = ViewerDefaults.CURRENT_TAB_GRADIENT.default
        self._layout_panes = PaneLayout()
        self._layout_panes.set_drop_handler(self._on_edge_drop)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._layout_panes, 1)

    def setDocumentMode(self, _enabled):
        """タブウィジェットと同じ呼び出しを受ける。面のタブバーでは見た目を変えない。

        Args:
            _enabled: ドキュメントモードにするとき True。ここでは使わない。
        """

    def setMovable(self, enabled):
        """すべての面でタブの並べ替えを許可する。

        Args:
            enabled: 並べ替えるとき True。
        """
        self._movable = enabled
        for group in self._groups():
            group.set_movable(enabled)

    def setTabsClosable(self, enabled):
        """すべての面でタブを閉じられるようにする。

        Args:
            enabled: 閉じるボタンを出すとき True。
        """
        self._closable = enabled
        for group in self._groups():
            group.set_tabs_closable(enabled)

    def set_gesture_recognizer(self, gesture):
        """すべての面の右ドラッグをジェスチャーとして認識させる。

        Args:
            gesture: 方向を記録する認識器。
        """
        self._gesture = gesture
        for group in self._groups():
            group.set_gesture_recognizer(gesture)

    def set_tab_bars_allowed(self, allowed):
        """タブバーを出してよいかを決め、面の数に合わせて出す。

        Args:
            allowed: フルスクリーンなどで隠すとき False。
        """
        self._bars_allowed = allowed
        self._apply_bar_visibility()

    def tabBar(self):
        """ショートカットが効く面のタブバーを返す。

        Returns:
            そのタブバー。面が無ければ None。
        """
        group = self._group_of(self.currentWidget())
        if group is None:
            groups = self._groups()
            return groups[0].tab_bar() if groups else None
        return group.tab_bar()

    def count(self):
        """タブの数を返す。

        Returns:
            タブの数。
        """
        return len(self._flat())

    def widget(self, index):
        """位置にあるタブを返す。

        Args:
            index: 面の並び、その中のタブ順での位置。

        Returns:
            そのタブ。範囲外なら None。
        """
        panes = self._flat()
        if 0 <= index < len(panes):
            return panes[index]
        return None

    def indexOf(self, pane):
        """タブの位置を返す。

        Args:
            pane: 探すタブ。

        Returns:
            位置。無ければ -1。
        """
        try:
            return self._flat().index(pane)
        except ValueError:
            # どの面にも無ければ -1 を返す。
            return -1

    def currentIndex(self):
        """ショートカットが効くタブの位置を返す。

        Returns:
            位置。無ければ -1。
        """
        return self.indexOf(self._focus.shortcut_target())

    def currentWidget(self):
        """ショートカットが効くタブを返す。

        Returns:
            最後に操作したタブ。無ければ None。
        """
        return self._focus.shortcut_target()

    def shown_panes(self):
        """各面で今見えているタブを、面の並びで返す。

        Returns:
            見えているタブの列。
        """
        shown = []
        for group in self._groups():
            pane = group.selected()
            if pane is not None:
                shown.append(pane)
        return shown

    def tabText(self, index):
        """タブの表示名を返す。

        Args:
            index: タブの位置。

        Returns:
            表示名。
        """
        located = self._locate(index)
        if located is None:
            return ""
        group, local = located
        return group.tab_text(local)

    def setTabText(self, index, text):
        """タブの表示名を変える。

        Args:
            index: タブの位置。
            text: 表示名。
        """
        located = self._locate(index)
        if located is None:
            return
        group, local = located
        group.set_tab_text(local, text)

    def setTabToolTip(self, index, text):
        """タブのツールチップを変える。表示名と同じ文字列を使う。

        Args:
            index: タブの位置。
            text: ツールチップ。
        """
        self.setTabText(index, text)

    def addTab(self, pane, title):
        """ショートカットが効く面の末尾へタブを足す。面が無ければ1面を作る。

        Args:
            pane: 足すタブ。
            title: 表示名。

        Returns:
            追加した位置。
        """
        self._ids[id(pane)] = pane
        group = self._group_of(self.currentWidget())
        if group is None:
            groups = self._groups()
            group = groups[-1] if groups else None
        if group is None:
            group = self._new_group()
            self._layout_panes.set_single(group)
        group.add_pane(pane, title)
        if group.count() == 1:
            self._focus.note(pane)
        self._refresh_mark()
        self._apply_bar_visibility()
        return self.indexOf(pane)

    def setCurrentIndex(self, index):
        """タブを、それがいる面の中で選び、ショートカット対象にする。別の面は変えない。

        Args:
            index: タブの位置。
        """
        pane = self.widget(index)
        if pane is None:
            return
        if self.signalsBlocked():
            self._focus.note(pane)
            return
        group = self._group_of(pane)
        if group is None:
            return
        if pane is self._focus.shortcut_target() and group.selected() is pane:
            return
        self._guard = True
        try:
            group.select(pane)
        finally:
            self._guard = False
        self._focus.note(pane)
        self._refresh_mark()
        if not self.signalsBlocked():
            self.currentChanged.emit(self.indexOf(pane))

    def note_only(self, pane):
        """画面は変えず、ショートカット対象だけを変える。

        Args:
            pane: 覚えておくタブ。
        """
        self._focus.note(pane)

    def note_gesture_tab(self, index):
        """ジェスチャーの開始タブを、その面の中で選ぶ。

        Args:
            index: 開始したタブの位置。
        """
        self.setCurrentIndex(index)

    def removeTab(self, index):
        """タブを面から外す。面が空なら畳む。

        Args:
            index: 外す位置。
        """
        located = self._locate(index)
        if located is None:
            return
        group, local = located
        focus_before = self._focus.shortcut_target()
        pane = group.remove_at(local)
        if pane is not None:
            self._ids.pop(id(pane), None)
        if group.count() == 0:
            self._layout_panes.detach(group)
            group.setParent(None)
            group.deleteLater()
            group = None
        if focus_before not in self._flat():
            replacement = group.selected() if group is not None and group.count() else None
            if replacement is None:
                shown = self.shown_panes()
                replacement = shown[0] if shown else None
            self._focus.note(replacement)
        current = self.currentIndex()
        self._refresh_mark()
        self._apply_bar_visibility()
        if self._flat() and not self.signalsBlocked() and self._focus.shortcut_target() is not focus_before:
            self.currentChanged.emit(current)

    def split_toward(self, direction):
        """対象タブのあとにあり、どの面でも選ばれていない次のタブを、指定側へ出す。

        Args:
            direction: left、right、up、down。

        Returns:
            面を出したとき True。
        """
        current = self.currentWidget()
        group = self._group_of(current)
        if current is None or group is None:
            return False
        if group.selected() is not current and not self.signalsBlocked():
            group.select(current)
        flat = self._flat()
        start = flat.index(current)
        selected = set(self.shown_panes())
        for pane in flat[start + 1:]:
            if pane in selected:
                continue
            if not self._move_to_new_group(pane, group, direction):
                return False
            self._refresh_mark()
            self._apply_bar_visibility()
            return True
        return False

    def split_grid(self):
        """対象タブと、そのあとの未選択タブを、左上から横へ最大4面に並べ直す。

        Returns:
            2面以上にしたとき True。
        """
        current = self.currentWidget()
        group = self._group_of(current)
        if current is None or group is None:
            return False
        flat = self._flat()
        start = flat.index(current)
        chosen = [current]
        selected = set(self.shown_panes())
        for pane in flat[start + 1:]:
            if pane in selected or pane in chosen:
                continue
            chosen.append(pane)
            if len(chosen) == 4:
                break
        if len(chosen) < 2:
            return False
        groups = [group]
        for pane in chosen[1:]:
            text = self._text_of(pane)
            source = self._group_of(pane)
            if source is None:
                continue
            source.remove_at(source.panes().index(pane))
            if source.count() == 0 and source is not group:
                self._layout_panes.detach(source)
                source.setParent(None)
                source.deleteLater()
            created = self._new_group()
            created.add_pane(pane, text)
            groups.append(created)
        for extra in list(self._groups()):
            if extra in groups:
                continue
            for pane in list(extra.panes()):
                text = extra.tab_text(extra.panes().index(pane))
                extra.remove_at(extra.panes().index(pane))
                group.add_pane(pane, text)
            self._layout_panes.detach(extra)
            extra.setParent(None)
            extra.deleteLater()
        self._layout_panes.arrange(groups)
        group.select(current)
        self._focus.note(current)
        self._refresh_mark()
        self._apply_bar_visibility()
        return True

    def join_view(self):
        """対象タブの面へすべてのタブを集め、そのタブを選ぶ。

        Returns:
            対象タブがあるとき True。
        """
        current = self.currentWidget()
        group = self._group_of(current)
        if current is None or group is None:
            return False
        items = []
        for pane in self._flat():
            items.append((pane, self._text_of(pane)))
        for extra in list(self._groups()):
            if extra is group:
                continue
            while extra.count():
                extra.remove_at(0)
            self._layout_panes.detach(extra)
            extra.setParent(None)
            extra.deleteLater()
        while group.count():
            group.remove_at(0)
        for pane, text in items:
            group.add_pane(pane, text)
        group.select(current)
        self._layout_panes.set_single(group)
        self._focus.note(current)
        self._refresh_mark()
        self._apply_bar_visibility()
        return True

    def regroup_pins(self):
        """各面の中だけで、固定タブを左へ寄せる。"""
        for group in self._groups():
            flags = [bool(getattr(pane, "pinned", False)) for pane in group.panes()]
            order = regroup_order(flags)
            group.reorder(order)

    def apply_pin_chrome(self):
        """すべての面のピン表示を更新する。"""
        for group in self._groups():
            group.tab_bar().apply_pin_chrome()

    def pane_at_local(self, pos):
        """分割領域の座標にある面で見えているタブを返す。

        Args:
            pos: 分割領域の中の位置。

        Returns:
            その位置のタブ。無ければ None。
        """
        group = self._layout_panes.pane_at(pos)
        if isinstance(group, PaneGroup):
            return group.selected()
        return None

    def tab_at_local(self, pos):
        """分割領域の座標にあるタブを返す。タブバーの空きや外は無い。

        Args:
            pos: 分割領域の中の位置。

        Returns:
            画像の上ならその面のタブ。タブバーのタブの上ならそのタブ。無ければ None。
        """
        group = self._layout_panes.pane_at(pos)
        if not isinstance(group, PaneGroup):
            return None
        bar = group.tab_bar()
        if not bar.isHidden():
            bar_pos = bar.mapFrom(self._layout_panes, pos)
            if bar.rect().contains(bar_pos):
                index = bar.tabAt(bar_pos)
                if index < 0:
                    return None
                return group.widget(index)
        return group.selected()

    def focus_tab_at(self, pos):
        """その位置のタブをカレントにする。空きや外なら変えない。

        Args:
            pos: 分割領域の中の位置。

        Returns:
            カレントにしたとき True。
        """
        pane = self.tab_at_local(pos)
        if pane is None:
            return False
        index = self.indexOf(pane)
        if index < 0:
            return False
        self.setCurrentIndex(index)
        return True

    def focus_tab_from(self, widget, pos):
        """別のウィジェット上の位置にあるタブをカレントにする。

        Args:
            widget: 座標の基準。
            pos: そのウィジェット上の位置。

        Returns:
            カレントにしたとき True。
        """
        return self.focus_tab_at(self._layout_panes.mapFrom(widget, pos))

    def set_current_tab_mark(self, color, alpha, gradient=True):
        """カレントタブに塗る色、透過度、グラデーションを覚える。

        Args:
            color: 16進の色。
            alpha: 0 から 255 の透過度。
            gradient: 左から右へ薄くするとき True。
        """
        self._mark_color = color
        self._mark_alpha = alpha
        self._mark_gradient = bool(gradient)
        self._refresh_mark()

    def _on_edge_drop(self, token, direction, target):
        """落とされたタブを、中央から見た先のタブバーへ移す。

        Args:
            token: ドラッグしたタブの識別子。
            direction: left、right、up、down。
            target: ドロップ先の面。
        """
        pane = self._pane_for_token(token)
        if pane is None or not isinstance(target, PaneGroup):
            return
        if direction not in ("left", "right", "up", "down"):
            return
        if self._group_of(pane) is None:
            return
        neighbor = self._layout_panes.neighbor(target, direction)
        if isinstance(neighbor, PaneGroup):
            self._move_into_group(pane, neighbor)
            return
        source = self._group_of(pane)
        was_shown = source.selected() is pane
        partner = self._partner(source, pane) if was_shown else None
        if not self._move_to_new_group(pane, target, direction):
            return
        if was_shown and partner is not None:
            home = self._group_of(partner)
            if home is not None:
                home.select(partner)
        self._finish_move(pane)

    def _move_into_group(self, pane, group):
        """タブを、すでにある面のタブバーへ移して選ぶ。

        Args:
            pane: 移すタブ。
            group: 移す先の面。
        """
        source = self._group_of(pane)
        if source is None:
            return
        if source is group:
            if group.selected() is not pane:
                group.select(pane)
            self._finish_move(pane)
            return
        was_shown = source.selected() is pane
        partner = self._partner(source, pane) if was_shown else None
        text = self._text_of(pane)
        source.remove_at(source.panes().index(pane))
        if source.count() == 0:
            self._layout_panes.detach(source)
            source.setParent(None)
            source.deleteLater()
        elif partner is not None:
            source.select(partner)
        group.insert_pane(group.count(), pane, text, True)
        self._finish_move(pane)

    def _finish_move(self, pane):
        """移したタブをカレントにし、タブバーと色を揃える。

        Args:
            pane: 移したタブ。
        """
        self._focus.note(pane)
        self._refresh_mark()
        self._apply_bar_visibility()
        if not self.signalsBlocked():
            self.currentChanged.emit(self.indexOf(pane))

    def _on_bar_drop(self, token, group, index):
        """タブバーへ落とされたタブを、その面へ移す。

        Args:
            token: ドラッグしたタブの識別子。
            group: ドロップ先の面。
            index: その面での挿入位置。
        """
        pane = self._pane_for_token(token)
        if pane is None or group is None:
            return
        source = self._group_of(pane)
        if source is None:
            return
        if source is group:
            old = source.panes().index(pane)
            if index > old:
                index -= 1
            if index == old:
                return
            group.move_local(old, index)
            return
        text = self._text_of(pane)
        source.remove_at(source.panes().index(pane))
        if source.count() == 0:
            self._layout_panes.detach(source)
            source.setParent(None)
            source.deleteLater()
        group.insert_pane(index, pane, text, True)
        self._focus.note(pane)
        self._refresh_mark()
        self._apply_bar_visibility()
        if not self.signalsBlocked():
            self.currentChanged.emit(self.indexOf(pane))

    def _move_to_new_group(self, pane, target, direction):
        """タブを対象の面の指定側へ移す。5面にはしない。

        Args:
            pane: 移すタブ。
            target: 分割する面。
            direction: left、right、up、down。

        Returns:
            移したとき True。
        """
        source = self._group_of(pane)
        if source is None or not isinstance(target, PaneGroup):
            return False
        if not self._layout_panes._is_visible(target):
            return False
        frees_group = source.count() == 1 and source is not target
        if self._layout_panes.visible_count() >= 4 and not frees_group:
            return False
        text = self._text_of(pane)
        source.remove_at(source.panes().index(pane))
        if source.count() == 0:
            self._layout_panes.detach(source)
            source.setParent(None)
            source.deleteLater()
            if source is target:
                shown = self._groups()
                target = shown[0] if shown else None
        if target is None or not self._layout_panes._is_visible(target):
            created = self._new_group()
            created.add_pane(pane, text)
            self._layout_panes.set_single(created)
            return True
        created = self._new_group()
        created.add_pane(pane, text)
        if self._layout_panes.split(target, direction, created):
            return True
        if not self._groups():
            self._layout_panes.set_single(created)
            return True
        home = self._groups()[0]
        created.remove_at(0)
        home.insert_pane(home.count(), pane, text, False)
        created.setParent(None)
        created.deleteLater()
        return False

    def _partner(self, group, pane):
        """同じ面で、左のタブを返す。左が無ければ右のタブ。

        Args:
            group: タブがいる面。
            pane: 基準のタブ。

        Returns:
            相手のタブ。1枚なら None。
        """
        panes = group.panes()
        index = panes.index(pane)
        if index > 0:
            return panes[index - 1]
        if index + 1 < len(panes):
            return panes[index + 1]
        return None

    def _new_group(self):
        """信号をつないだ空の面を作る。

        Returns:
            新しい面。
        """
        group = PaneGroup()
        group.set_movable(self._movable)
        group.set_tabs_closable(self._closable)
        if self._gesture is not None:
            group.set_gesture_recognizer(self._gesture)
        group.tabCloseRequested.connect(lambda local, g=group: self._emit_close(g, local))
        group.currentChanged.connect(lambda local, g=group: self._on_group_current(g, local))
        group.tabMoved.connect(lambda src, dest, g=group: self.groupTabMoved.emit(g, src, dest))
        group.gestureRecognized.connect(lambda local, gesture, g=group: self._emit_gesture(g, local, gesture))
        group.contextMenuRequested.connect(lambda pos, g=group: self._emit_menu(g, pos))
        group.tabDropped.connect(lambda token, local, g=group: self._on_bar_drop(token, g, local))
        group.tabClicked.connect(lambda local, g=group: self._on_group_clicked(g, local))
        return group

    def _emit_close(self, group, local):
        """面の中の位置を、全体の位置にして閉じる信号を出す。

        Args:
            group: 閉じるタブの面。
            local: その面の中の位置。
        """
        flat = self._flat_index(group, local)
        if flat >= 0:
            self.tabCloseRequested.emit(flat)

    def _emit_gesture(self, group, local, gesture):
        """面の中の位置を、全体の位置にしてジェスチャーを出す。

        Args:
            group: 開始した面。
            local: その面の中の位置。
            gesture: 認識した方向列。
        """
        flat = self._flat_index(group, local)
        if flat < 0:
            return
        self.note_gesture_tab(flat)
        self.gestureRecognized.emit(flat, gesture)

    def _emit_menu(self, group, pos):
        """タブバー上の位置を、全体のタブ位置にしてメニューを出す。

        Args:
            group: メニューを出す面。
            pos: そのタブバー上の位置。
        """
        local = group.tab_bar().tabAt(pos)
        flat = self._flat_index(group, local)
        if flat >= 0:
            self.tabContextMenuRequested.emit(flat)

    def _on_group_clicked(self, group, local):
        """クリックしたタブを、すでに選ばれていてもカレントにする。

        Args:
            group: クリックした面。
            local: その面の中の位置。
        """
        if self._guard:
            return
        pane = group.widget(local)
        if pane is None:
            return
        if group.selected() is not pane:
            self._guard = True
            try:
                group.select(pane)
            finally:
                self._guard = False
        if pane is self._focus.shortcut_target() and group.selected() is pane:
            self._refresh_mark()
            return
        self._focus.note(pane)
        self._refresh_mark()
        if not self.signalsBlocked():
            self.currentChanged.emit(self.indexOf(pane))

    def _on_group_current(self, group, local):
        """面の中で選ばれたタブを、ショートカット対象にする。

        Args:
            group: 選ばれた面。
            local: その面の中の位置。
        """
        if self._guard:
            return
        pane = group.widget(local)
        if pane is None:
            return
        self._focus.note(pane)
        self._refresh_mark()
        if not self.signalsBlocked():
            self.currentChanged.emit(self.indexOf(pane))

    def _groups(self):
        """左上から、今出ている面を返す。

        Returns:
            面の列。
        """
        return [group for group in self._layout_panes.visible_panes() if isinstance(group, PaneGroup)]

    def _group_of(self, pane):
        """タブがいる面を返す。

        Args:
            pane: 探すタブ。

        Returns:
            その面。無ければ None。
        """
        for group in self._groups():
            if pane in group.panes():
                return group
        return None

    def _flat(self):
        """面の並び、その中のタブ順でタブを返す。

        Returns:
            タブの列。
        """
        panes = []
        for group in self._groups():
            panes.extend(group.panes())
        return panes

    def _locate(self, index):
        """全体の位置を、面とその中の位置にする。

        Args:
            index: 全体の位置。

        Returns:
            (面, 面の中の位置)。範囲外なら None。
        """
        if index < 0:
            return None
        for group in self._groups():
            count = group.count()
            if index < count:
                return (group, index)
            index -= count
        return None

    def _flat_index(self, group, local):
        """面の中の位置を、全体の位置にする。

        Args:
            group: 面。
            local: その面の中の位置。

        Returns:
            全体の位置。無ければ -1。
        """
        if local < 0:
            return -1
        offset = 0
        for item in self._groups():
            if item is group:
                if local < item.count():
                    return offset + local
                return -1
            offset += item.count()
        return -1

    def _text_of(self, pane):
        """タブの表示名を返す。

        Args:
            pane: タブ。

        Returns:
            表示名。
        """
        group = self._group_of(pane)
        if group is None:
            return ""
        return group.tab_text(group.panes().index(pane))

    def _pane_for_token(self, token):
        """ドラッグの識別子からタブを返す。

        Args:
            token: 識別子。

        Returns:
            そのタブ。無ければ None。
        """
        try:
            key = int(token)
        except (TypeError, ValueError):
            # 識別子でなければドロップを捨てる。
            return None
        return self._ids.get(key)

    def _apply_bar_visibility(self):
        """分割中は各面のタブバーを出し、1面のときはタブが2枚以上のときだけ出す。"""
        groups = self._groups()
        split = len(groups) >= 2
        for group in groups:
            if not self._bars_allowed:
                group.set_bar_visible(False)
            elif split:
                group.set_bar_visible(True)
            else:
                group.set_bar_visible(group.count() > 1)

    def _refresh_mark(self):
        """タブバーが出ているカレントタブを塗る。"""
        groups = self._groups()
        split = len(groups) >= 2
        color = current_tab_mark_color(self._mark_color, self._mark_alpha)
        focus = self._focus.shortcut_target()
        for group in groups:
            shown = self._bars_allowed and (split or group.count() > 1)
            if shown and group.selected() is focus:
                group.set_current_mark(color, self._mark_gradient)
            else:
                group.set_current_mark(None, False)
