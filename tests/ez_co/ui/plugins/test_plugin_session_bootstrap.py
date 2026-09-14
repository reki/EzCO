"""対象: ez_co.ui.plugins.plugin_session — bootstrap（同意とロード）。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import get_plugin_manager
from ez_co.ui.plugins.plugin_session import PluginSession
from ez_co.utils import data_location
from ez_co.utils.data_location import get_data_root


def _config():
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def _plugins_dir():
    path = get_data_root() / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


class _Consent:
    instances = []
    result = 0

    def __init__(self, parent=None):
        _Consent.instances.append(self)

    def exec(self):
        return self.result


def test_bootstrap_skips_consent_when_no_candidates(monkeypatch):
    _Consent.instances.clear()
    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConsentDialog", _Consent)
    session = PluginSession()
    session.bootstrap(None, _config())
    assert _Consent.instances == []
    assert get_plugin_manager().plugins == []
    assert session.consent_accepted() is False


def test_bootstrap_reject_leaves_plugins_unloaded(monkeypatch, dir_plugin):
    dir_plugin(_plugins_dir(), plugin_id="com.example.probe", folder_name="probe")
    _Consent.instances.clear()
    _Consent.result = 0
    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConsentDialog", _Consent)
    session = PluginSession()
    session.bootstrap(None, _config())
    assert len(_Consent.instances) == 1
    assert get_plugin_manager().plugins == []
    assert get_plugin_manager()._loaded is False


def test_bootstrap_accepted_consent_skips_dialog(monkeypatch, dir_plugin, user_json):
    dir_plugin(_plugins_dir(), plugin_id="com.example.probe", folder_name="probe")
    user_json({data_location.PLUGIN_CONSENT_KEY: "1.0.0"})
    _Consent.instances.clear()
    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConsentDialog", _Consent)
    session = PluginSession()
    session.bootstrap(None, _config())
    assert _Consent.instances == []
    assert len(get_plugin_manager().plugins) == 1
    assert session.consent_accepted() is True
