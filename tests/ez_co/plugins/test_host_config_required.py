"""対象: ez_co.plugins.host — required / multiple の空 / is_config_empty。"""
from ez_co.plugins.host import PluginHost, is_config_empty


class _MemoryDb:
    """プラグイン設定を辞書に持つ、テスト用の DB。"""

    def __init__(self):
        """行の辞書を空にする。"""
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        """保存済みの値を返す。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            default: 行が無いときの値。

        Returns:
            保存値。無ければ default。
        """
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        """設定を辞書へ書く。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            value: 保存する値。

        Returns:
            常に真。
        """
        self.rows[(plugin_id, key)] = value
        return True

    def delete_plugin_setting(self, plugin_id, key):
        """設定の行を消す。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。

        Returns:
            常に真。
        """
        self.rows.pop((plugin_id, key), None)
        return True


def _scoped():
    """メモリ DB を載せたホストと、そのスコープを返す。

    Returns:
        ホストと com.example.x のスコープ。
    """
    host = PluginHost()
    host._db = _MemoryDb()
    return host, host.scoped("com.example.x")


def test_is_config_empty_by_type():
    """空白だけの文字列が空と見なされず、空白だけの password が空になり、false や 0 が空になり、空リスト以外の multiple が空になる。"""
    host = PluginHost()
    scoped = host.scoped("com.example.x")
    scoped.register_config("label", "string", default="")
    scoped.register_config("secret", "password", default="")
    scoped.register_config("flag", "bool", default=False)
    scoped.register_config("count", "int", default=0)
    scoped.register_config("items", "string", default=[], multiple=True)
    fields = {field.key: field for field in host.configs_for("com.example.x")}
    assert is_config_empty(fields["label"], "")
    assert is_config_empty(fields["label"], "   ")
    assert not is_config_empty(fields["secret"], "   ")
    assert is_config_empty(fields["secret"], "")
    assert not is_config_empty(fields["flag"], False)
    assert not is_config_empty(fields["count"], 0)
    assert is_config_empty(fields["items"], [])
    assert not is_config_empty(fields["items"], [""])


def test_required_false_saves_empty_string_and_list():
    """required でない項目が空文字と空リストを保存できず、get_config が空リストを埋め直す。"""
    host, scoped = _scoped()
    scoped.register_config("label", "string", default="x")
    scoped.register_config("items", "string", default=["a"], multiple=True)
    assert scoped.set_config("label", "") is True
    assert host._db.rows[("com.example.x", "label")] == ""
    assert scoped.set_config("items", []) is True
    assert host._db.rows[("com.example.x", "items")] == []
    assert scoped.get_config("items") == []


def test_required_true_rejects_empty_set_config():
    """required の空文字と空リストが保存され、config_changed が飛び、get_config が default の空から変わる。"""
    host, scoped = _scoped()
    scoped.register_config("need", "string", default="", required=True)
    scoped.register_config("needs", "string", default=[], multiple=True, required=True)
    seen = []
    scoped.on("config_changed", lambda payload: seen.append(payload))
    assert scoped.set_config("need", "") is False
    assert ("com.example.x", "need") not in host._db.rows
    assert scoped.set_config("needs", []) is False
    assert ("com.example.x", "needs") not in host._db.rows
    assert seen == []
    assert scoped.get_config("need") == ""
    assert scoped.get_config("needs") == []


def test_required_empty_default_can_register():
    """required でも空の default で登録できず、required が落ちる。"""
    host, scoped = _scoped()
    scoped.register_config("need", "string", default="", required=True)
    field = host.configs_for("com.example.x")[0]
    assert field.required is True
    assert field.default == ""


def test_multiple_does_not_fill_empty_list():
    """multiple の空リストが補完され、default の真が空のままになる。"""
    _host, scoped = _scoped()
    scoped.register_config("items", "string", default=[], multiple=True)
    assert scoped.get_config("items") == []
    scoped.register_config("flags", "bool", default=True, multiple=True)
    assert scoped.get_config("flags") == [True]


def test_reset_config_deletes_override_and_notifies_default():
    """reset 後も上書き行が残り、config_changed が default の空文字で飛ばず、after 通知が来ない。"""
    host, scoped = _scoped()
    scoped.register_config("need", "string", default="", required=True)
    assert scoped.set_config("need", "kept")
    seen = []
    after = []
    scoped.on("config_changed", lambda payload: seen.append(payload))
    host._after_plugin_config = lambda plugin_id: after.append(plugin_id)
    assert scoped.reset_config("need")
    assert scoped.get_config("need") == ""
    assert ("com.example.x", "need") not in host._db.rows
    assert seen == [{"key": "need", "value": ""}]
    assert after == ["com.example.x"]
