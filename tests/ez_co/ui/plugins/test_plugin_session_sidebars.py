"""対象: ez_co.ui.plugins.plugin_session — フルスクリーン用のサイドバー隠しと復元。"""
from ez_co.ui.plugins.plugin_session import PluginSession


class _Dock:
    def __init__(self, visible=True):
        self._visible = visible

    def isVisible(self):
        return self._visible

    def hide(self):
        self._visible = False

    def show(self):
        self._visible = True


class _Action:
    def __init__(self):
        self.checked = True

    def setChecked(self, value):
        self.checked = bool(value)


def test_hide_visible_sidebars_returns_hidden_and_restore_shows_them():
    session = PluginSession()
    shown = {"dock": _Dock(True), "action": _Action()}
    hidden = {"dock": _Dock(False), "action": _Action()}
    hidden["action"].setChecked(False)
    session._sidebars = {"shown": shown, "hidden": hidden}

    closed = session.hide_visible_sidebars()
    assert closed == [shown]
    assert shown["dock"].isVisible() is False
    assert shown["action"].checked is False
    assert hidden["dock"].isVisible() is False

    session.restore_sidebars(closed)
    assert shown["dock"].isVisible() is True
    assert shown["action"].checked is True
    assert hidden["dock"].isVisible() is False
