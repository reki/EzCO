"""対象: ez_co.plugins.host — 表示時だけ {key} を展開し、台帳はテンプレートのまま。"""
from ez_co.plugins.host import PluginHost, make_plugin_action_id
from ez_co.utils.language_manager import set_language


def _bind(host: PluginHost, plugin_id: str, mapping: dict[str, str]):
    scoped = host.scoped(plugin_id)
    scoped.bind_plugin(None, lambda key, **kwargs: mapping.get(key, key))
    return scoped


def test_action_label_expands_at_display_ledger_stays():
    host = PluginHost()
    host.enter_phase("com.example.x", "setup")
    scoped = _bind(host, "com.example.x", {"go": "実行"})
    scoped.register_action("go", "{go}", lambda: None)
    public_id = make_plugin_action_id("com.example.x", "go")
    assert host.resolve_action(public_id).label == "{go}"
    assert host.action_label(public_id) == "実行"


def test_config_label_stays_template_across_language_switch():
    set_language("ja")
    host = PluginHost()
    host.enter_phase("com.example.x", "load")
    scoped = _bind(host, "com.example.x", {"title": "題名"})
    scoped.register_config("flag", "bool", True, label="{title}")
    assert host.configs_for("com.example.x")[0].label == "{title}"
    assert host.expand_text("com.example.x", "{title}") == "題名"
    set_language("en")
    _bind(host, "com.example.x", {"title": "Title"})
    assert host.configs_for("com.example.x")[0].label == "{title}"
    assert host.expand_text("com.example.x", "{title}") == "Title"
    set_language("ja")
    _bind(host, "com.example.x", {"title": "題名"})
    assert host.configs_for("com.example.x")[0].label == "{title}"
    assert host.expand_text("com.example.x", "{title}") == "題名"


def test_refresh_display_titles_remounts_without_unmount():
    host = PluginHost()
    mounted = []
    unmounted = []

    def mount(plugin_id, sidebar_id, title, widget):
        mounted.append((plugin_id, sidebar_id, title, widget))

    def unmount(plugin_id, sidebar_id):
        unmounted.append((plugin_id, sidebar_id))

    host.bind(parent=None, mount_sidebar=mount, unmount_sidebar=unmount)
    host.set_manifest_provides("com.example.x", sidebar=True)
    host.enter_phase("com.example.x", "setup")
    scoped = _bind(host, "com.example.x", {"title": "題名"})
    widget = object()
    scoped.register_sidebar("main", "{title}", widget)
    assert mounted[-1][2] == "題名"
    assert host.sidebars_for("com.example.x")[0].title == "{title}"
    _bind(host, "com.example.x", {"title": "Title"})
    host.refresh_display_titles()
    assert mounted[-1][2] == "Title"
    assert unmounted == []
    assert host.sidebars_for("com.example.x")[0].title == "{title}"
    assert mounted[-1][3] is widget
