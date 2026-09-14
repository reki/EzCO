"""対象: ez_co.ui.plugins.plugin_session — ソース変更のときだけ reload_selected。"""
from types import SimpleNamespace

from ez_co.ui.plugins.plugin_session import PluginSession


class _Manager:
    def __init__(self):
        self.reload_calls = 0
        self.activate_calls = 0

    def reload_selected(self, config):
        self.reload_calls += 1

    def activate_ui(self, config):
        self.activate_calls += 1


class _Host:
    def __init__(self):
        self.events = []

    def emit(self, event, payload=None, plugin_id=None):
        self.events.append(event)


def test_after_config_reloads_only_when_sources_change(monkeypatch):
    class _Dialog:
        def __init__(self, *args, **kwargs):
            raise AssertionError("dialog exec should be stubbed")

        def exec(self):
            raise AssertionError("dialog exec should be stubbed")

    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConsentDialog", _Dialog)
    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConflictDialog", _Dialog)
    session = PluginSession()
    manager = _Manager()
    host = _Host()
    session._manager = manager
    session._host = host
    session._config = SimpleNamespace()
    session.after_config_change(reload_sources=False)
    assert manager.reload_calls == 0
    assert manager.activate_calls == 1
    session.after_config_change(reload_sources=True)
    assert manager.reload_calls == 1
    assert manager.activate_calls == 2
