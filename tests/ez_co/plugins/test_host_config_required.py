"""対象: ez_co.plugins.host — required / multiple の空 / is_config_empty。"""
from ez_co.plugins.host import PluginHost, is_config_empty


class _MemoryDb:
    def __init__(self):
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        self.rows[(plugin_id, key)] = value
        return True

    def delete_plugin_setting(self, plugin_id, key):
        self.rows.pop((plugin_id, key), None)
        return True


def _scoped():
    host = PluginHost()
    host._db = _MemoryDb()
    return host, host.scoped("com.example.x")


def test_is_config_empty_by_type():
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
    host, scoped = _scoped()
    scoped.register_config("label", "string", default="x")
    scoped.register_config("items", "string", default=["a"], multiple=True)
    assert scoped.set_config("label", "") is True
    assert host._db.rows[("com.example.x", "label")] == ""
    assert scoped.set_config("items", []) is True
    assert host._db.rows[("com.example.x", "items")] == []
    assert scoped.get_config("items") == []


def test_required_true_rejects_empty_set_config():
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
    host, scoped = _scoped()
    scoped.register_config("need", "string", default="", required=True)
    field = host.configs_for("com.example.x")[0]
    assert field.required is True
    assert field.default == ""


def test_multiple_does_not_fill_empty_list():
    _host, scoped = _scoped()
    scoped.register_config("items", "string", default=[], multiple=True)
    assert scoped.get_config("items") == []
    scoped.register_config("flags", "bool", default=True, multiple=True)
    assert scoped.get_config("flags") == [True]


def test_reset_config_deletes_override_and_notifies_default():
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
