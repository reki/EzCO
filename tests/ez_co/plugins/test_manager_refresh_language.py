"""対象: ez_co.plugins.manager — 言語変更は setup を再実行せず hook 例外を隔離する。"""
from __future__ import annotations

from types import SimpleNamespace

from ez_co.plugins.manager import PluginManager


def _config():
    return SimpleNamespace(
        plugins={"source_choice": {}, "extension_handlers": {}, "enabled": {}}
    )


def test_refresh_language_does_not_rerun_setup_or_add_listeners(tmp_path, dir_plugin):
    counter = tmp_path / "setup.txt"
    root = dir_plugin(
        tmp_path,
        plugin_id="com.example.lang",
        folder_name="lang",
        setup_counter=counter,
        manifest_extra={"sidebar": True},
    )
    (root / "src" / "plugin.py").write_text(
        "COUNTER = r'''%s'''\n"
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "        self.calls = 0\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        "    def setup(self):\n"
        "        from pathlib import Path\n"
        "        path = Path(COUNTER)\n"
        "        path.write_text(str(int(path.read_text() or '0') + 1), encoding='utf-8')\n"
        "        self.host.on('config_changed', self._on)\n"
        "        self.host.register_sidebar('main', '{title}', object())\n"
        "    def _on(self, payload=None):\n"
        "        return None\n"
        "    def language_changed(self):\n"
        "        self.calls += 1\n" % counter.as_posix(),
        encoding="utf-8",
    )
    unmounted = []
    manager = PluginManager()
    manager.host.bind(parent=None, unmount_sidebar=lambda pid, sid: unmounted.append((pid, sid)))
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    plugin = manager.plugins[0]
    listeners_before = len(manager.host._listeners.get("config_changed") or [])
    manager.refresh_language()
    manager.refresh_language()
    assert counter.read_text(encoding="utf-8") == "1"
    assert plugin.instance.calls == 2
    assert plugin.ui_active is True
    assert unmounted == []
    assert len(manager.host._listeners.get("config_changed") or []) == listeners_before


def test_language_changed_exception_keeps_plugin_and_continues(tmp_path, dir_plugin):
    boom = dir_plugin(
        tmp_path,
        plugin_id="com.example.boom",
        folder_name="boom",
        extension=".boom",
    )
    (boom / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        "    def setup(self):\n"
        "        return None\n"
        "    def language_changed(self):\n"
        "        raise RuntimeError('lang-boom')\n",
        encoding="utf-8",
    )
    ok = dir_plugin(
        tmp_path,
        plugin_id="com.example.ok",
        folder_name="ok",
        extension=".ok",
    )
    (ok / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "        self.calls = 0\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        "    def setup(self):\n"
        "        return None\n"
        "    def language_changed(self):\n"
        "        self.calls += 1\n",
        encoding="utf-8",
    )
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    manager.refresh_language()
    by_id = {plugin.plugin_id: plugin for plugin in manager.plugins}
    assert by_id["com.example.boom"].ui_active is True
    assert by_id["com.example.boom"].error is None
    assert by_id["com.example.ok"].instance.calls == 1


def test_missing_language_changed_is_not_an_error(tmp_path, dir_plugin):
    dir_plugin(tmp_path, plugin_id="com.example.plain", folder_name="plain")
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    manager.refresh_language()
    plugin = manager.plugins[0]
    assert plugin.ui_active is True
    assert plugin.error is None


def test_language_changed_cannot_register(tmp_path, dir_plugin):
    root = dir_plugin(
        tmp_path,
        plugin_id="com.example.deny",
        folder_name="deny",
        manifest_extra={"sidebar": True},
    )
    (root / "src" / "plugin.py").write_text(
        "class ProbePlugin:\n"
        "    def __init__(self):\n"
        "        self.host = None\n"
        "        self.denied = False\n"
        "    def load(self, root, get_text, host):\n"
        "        self.host = host\n"
        "    def setup(self):\n"
        "        self.host.register_sidebar('main', '{title}', object())\n"
        "        self.host.on('config_changed', self._on)\n"
        "    def _on(self, payload=None):\n"
        "        return None\n"
        "    def language_changed(self):\n"
        "        try:\n"
        "            self.host.register_sidebar('other', 'X', object())\n"
        "        except Exception:\n"
        "            self.denied = True\n"
        "            raise\n",
        encoding="utf-8",
    )
    manager = PluginManager()
    manager.discover(tmp_path)
    manager.load_selected(_config())
    manager.activate_ui()
    sidebars_before = len(manager.host.sidebars_for("com.example.deny"))
    listeners_before = len(manager.host._listeners.get("config_changed") or [])
    manager.refresh_language()
    plugin = manager.plugins[0]
    assert plugin.instance.denied is True
    assert plugin.ui_active is True
    assert len(manager.host.sidebars_for("com.example.deny")) == sidebars_before
    assert len(manager.host._listeners.get("config_changed") or []) == listeners_before
