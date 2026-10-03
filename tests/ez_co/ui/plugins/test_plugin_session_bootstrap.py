"""対象: ez_co.ui.plugins.plugin_session — bootstrap（同意とロード）。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import get_plugin_manager
from ez_co.ui.plugins.plugin_session import PluginSession
from ez_co.utils import data_location
from ez_co.utils.data_location import get_data_root


def _config():
    """ソース選択も有効化も空の設定を作る。

    Returns:
        bootstrap へ渡す設定。
    """
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def _plugins_dir():
    """データルート配下の plugins ディレクトリを用意する。

    Returns:
        作成したディレクトリ。
    """
    path = get_data_root() / "plugins"
    path.mkdir(parents=True, exist_ok=True)
    return path


class _Consent:
    """同意ダイアログの代わり。生成回数と戻り値を外から決める。"""

    # 生成されたダイアログ。
    instances = []
    # exec が返す結果。0 は拒否。
    result = 0

    def __init__(self, parent=None):
        """生成された自分を一覧へ足す。

        Args:
            parent: ダイアログの親。使わない。
        """
        _Consent.instances.append(self)

    def exec(self):
        """あらかじめ入れた同意結果を返す。

        Returns:
            クラスに入れた結果。
        """
        return self.result


def test_bootstrap_skips_consent_when_no_candidates(monkeypatch):
    """候補が無いのに同意ダイアログが開き、プラグインが残るか同意済みになる。"""
    _Consent.instances.clear()
    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConsentDialog", _Consent)
    session = PluginSession()
    session.bootstrap(None, _config())
    assert _Consent.instances == []
    assert get_plugin_manager().plugins == []
    assert session.consent_accepted() is False


def test_bootstrap_reject_leaves_plugins_unloaded(monkeypatch, dir_plugin):
    """同意を拒否してもロードされる、またはダイアログが1回以外。"""
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
    """保存済みの同意があってもダイアログが出る、または候補が1件ロードされず同意済みにならない。"""
    dir_plugin(_plugins_dir(), plugin_id="com.example.probe", folder_name="probe")
    user_json({data_location.PLUGIN_CONSENT_KEY: "1.0.0"})
    _Consent.instances.clear()
    monkeypatch.setattr("ez_co.ui.plugins.plugin_session.PluginConsentDialog", _Consent)
    session = PluginSession()
    session.bootstrap(None, _config())
    assert _Consent.instances == []
    assert len(get_plugin_manager().plugins) == 1
    assert session.consent_accepted() is True
