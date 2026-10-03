"""対象: ez_co.ui.plugins.plugin_session — 保持した host へ current_changed 1回。"""
from ez_co.ui.plugins.plugin_session import PluginSession


class _Host:
    """emit されたイベントを順に残す host の代わり。"""

    def __init__(self):
        """空のイベント列を用意する。"""
        self.events = []

    def emit(self, event, payload=None, plugin_id=None):
        """イベント名と引数を記録する。

        Args:
            event: イベント名。
            payload: イベントの中身。
            plugin_id: 宛先のプラグイン。無ければ全体。
        """
        self.events.append((event, payload, plugin_id))


def test_notify_current_changed_hits_kept_host_once():
    """現在位置の通知が保持している host 以外へ行く、または current_changed が1回以外。"""
    session = PluginSession()
    host = _Host()
    session._host = host
    session._current = lambda key: {"path": "a.png", "folder": "dir", "page": 2}[key]
    session.notify_current_changed()
    assert session._host is host
    assert host.events == [
        ("current_changed", {"path": "a.png", "folder": "dir", "page": 2}, None)
    ]


def test_notify_current_changed_can_target_one_plugin():
    """plugin_id を渡しても、その ID を載せた current_changed が1回にならない。"""
    session = PluginSession()
    host = _Host()
    session._host = host
    session._current = lambda key: {"path": "a.png", "folder": "dir", "page": 2}[key]
    session.notify_current_changed(plugin_id="com.ezco.product_info")
    assert host.events == [
        ("current_changed", {"path": "a.png", "folder": "dir", "page": 2}, "com.ezco.product_info")
    ]
