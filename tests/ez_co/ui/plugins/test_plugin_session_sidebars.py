"""対象: ez_co.ui.plugins.plugin_session — フルスクリーン用のサイドバー隠しと復元。"""
from ez_co.ui.plugins.plugin_session import PluginSession


class _Dock:
    """表示の切り替えだけを持つドックの代わり。"""

    def __init__(self, visible=True):
        """初期の表示状態を入れる。

        Args:
            visible: 最初から見えているか。
        """
        self._visible = visible

    def isVisible(self):
        """今見えているかを返す。

        Returns:
            見えていれば True。
        """
        return self._visible

    def hide(self):
        """非表示にする。"""
        self._visible = False

    def show(self):
        """表示する。"""
        self._visible = True


class _Action:
    """チェック状態だけを持つアクションの代わり。"""

    def __init__(self):
        """チェックをオンにする。"""
        self.checked = True

    def setChecked(self, value):
        """チェック状態を bool で入れる。

        Args:
            value: 新しいチェック状態。
        """
        self.checked = bool(value)


def test_hide_visible_sidebars_returns_hidden_and_restore_shows_them():
    """見えていたサイドバーが隠しと復元で戻らず、最初から隠れていたものまで出る。"""
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
