"""タブバーとタブ一覧で同じ右クリックメニューを作る。"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QWidget

from ez_co.ui.viewer.tab_commands import tab_menu_state
from ez_co.utils.language_manager import get_text


def build_tab_context_menu(
    parent: QWidget | None,
    *,
    index: int,
    pinned: list[bool],
    path: str | None,
    on_close: Callable[[], None],
    on_close_others: Callable[[], None],
    on_close_right: Callable[[], None],
    on_close_left: Callable[[], None],
    on_pin: Callable[[], None],
    on_duplicate: Callable[[], None],
    on_copy_name: Callable[[], None],
    on_copy_path: Callable[[], None],
) -> QMenu:
    """項目の並びと有効／無効を決めてメニューを返す。ショートカットは付けない。"""
    state = tab_menu_state(index, pinned, path)
    menu = QMenu(parent)

    def add(text: str, enabled: bool, slot: Callable[[], None]) -> None:
        action = QAction(text, menu)
        action.setEnabled(enabled)
        action.triggered.connect(lambda _checked=False: slot())
        menu.addAction(action)

    add(get_text("ui.close_tab"), True, on_close)
    add(get_text("ui.close_other_tabs"), state["close_others_enabled"], on_close_others)
    add(get_text("ui.close_tabs_to_the_right"), state["close_right_enabled"], on_close_right)
    add(get_text("ui.close_tabs_to_the_left"), state["close_left_enabled"], on_close_left)
    menu.addSeparator()
    pin_key = "ui.unpin_tab" if state["pinned"] else "ui.pin_tab"
    add(get_text(pin_key), True, on_pin)
    add(get_text("ui.duplicate_tab"), True, on_duplicate)
    menu.addSeparator()
    add(get_text("ui.copy_file_name"), state["copy_enabled"], on_copy_name)
    add(get_text("ui.copy_full_path"), state["copy_enabled"], on_copy_path)
    return menu
