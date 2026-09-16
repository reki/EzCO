"""対象: ez_co.ui.plugins.plugin_session — 保持した host へ current_changed 1回。"""
from ez_co.ui.plugins.plugin_session import PluginSession


class _Host:
    def __init__(self):
        self.events = []

    def emit(self, event, payload=None, plugin_id=None):
        self.events.append((event, payload, plugin_id))


def test_notify_current_changed_hits_kept_host_once():
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
    session = PluginSession()
    host = _Host()
    session._host = host
    session._current = lambda key: {"path": "a.png", "folder": "dir", "page": 2}[key]
    session.notify_current_changed(plugin_id="com.ezco.product_info")
    assert host.events == [
        ("current_changed", {"path": "a.png", "folder": "dir", "page": 2}, "com.ezco.product_info")
    ]
