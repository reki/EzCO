"""対象: ez_co.ui.plugins.plugin_session — ソース変更のときだけ reload_selected。"""
from types import SimpleNamespace

from ez_co.ui.plugins.plugin_session import PluginSession


class _Manager:
    """reload と UI 再有効化の回数を数える manager の代わり。"""

    def __init__(self):
        """両方の回数を 0 にする。"""
        self.reload_calls = 0
        self.activate_calls = 0

    def reload_selected(self, config):
        """ソースの再読み込み回数を増やす。

        Args:
            config: 再読み込みに渡される設定。
        """
        self.reload_calls += 1

    def activate_ui(self, config):
        """UI 再有効化の回数を増やす。

        Args:
            config: 再有効化に渡される設定。
        """
        self.activate_calls += 1


class _Host:
    """emit されたイベント名を順に残す host の代わり。"""

    def __init__(self):
        """空のイベント列を用意する。"""
        self.events = []

    def emit(self, event, payload=None, plugin_id=None):
        """イベント名を記録する。

        Args:
            event: イベント名。
            payload: イベントの中身。記録しない。
            plugin_id: 宛先のプラグイン。記録しない。
        """
        self.events.append(event)


def test_after_config_reloads_only_when_sources_change(monkeypatch):
    """ソースを変えないのに reload する、変えたのに reload が増えない、または同意ダイアログが開く。"""
    class _Dialog:
        """開かれたら失敗させる同意ダイアログの代わり。"""

        def __init__(self, *args, **kwargs):
            """生成された時点で失敗させる。

            Args:
                *args: ダイアログへ渡される位置引数。
                **kwargs: ダイアログへ渡されるキーワード引数。

            Raises:
                AssertionError: ダイアログを開こうとしたとき。
            """
            raise AssertionError("dialog exec should be stubbed")

        def exec(self):
            """表示された時点で失敗させる。

            Raises:
                AssertionError: exec が呼ばれたとき。
            """
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
