"""対象: ez_co.plugins.host — make_plugin_action_id とエイリアス。"""
from ez_co.plugins.host import PluginHost, make_plugin_action_id


def test_make_plugin_action_id():
    assert make_plugin_action_id("com.example.x", "go") == "plugin:com.example.x:go"


def test_register_action_stores_public_id_and_aliases():
    host = PluginHost()
    called = []
    host.scoped("com.example.x").register_action(
        "go",
        "Go",
        lambda: called.append(1),
        aliases=("next_page",),
    )
    public_id = make_plugin_action_id("com.example.x", "go")
    record = host.resolve_action(public_id)
    assert record is not None
    assert record.public_id == public_id
    assert record.aliases == ("next_page",)
    assert host.resolve_action("next_page") is record
    assert host.action_ids_for("next_page") == [public_id, "next_page"]
