"""対象: plugins/product_info — ページ送りで取得スレッドを捨てない。"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PLUGIN_SRC = Path(__file__).resolve().parents[3] / "plugins" / "product_info" / "src"


def _plugin():
    if str(PLUGIN_SRC) not in sys.path:
        sys.path.insert(0, str(PLUGIN_SRC))
    from plugin import ProductInfoPlugin

    class Host:
        def __init__(self):
            self.current = {}

        def register_config(self, *args, **kwargs):
            return None

        def get_config(self, key, default=None):
            return default

        def get_current(self, key):
            return self.current.get(key)

    plugin = ProductInfoPlugin()
    plugin.load(None, lambda *args, **kwargs: "", Host())
    return plugin


def test_same_product_id_does_not_refresh_when_folder_changes():
    plugin = _plugin()
    called = []
    plugin.refresh = lambda folder: called.append(folder)
    plugin._on_current({"folder": "K:/manga/d_799677", "path": "a.png"})
    plugin._on_current({"folder": "K:/other/d_799677", "path": "b.png"})
    assert called == ["K:/manga/d_799677"]


def test_product_id_change_refreshes():
    plugin = _plugin()
    called = []
    plugin.refresh = lambda folder: called.append(folder)
    plugin._on_current({"folder": "K:/manga/d_799677"})
    plugin._on_current({"folder": "K:/manga/d_111111"})
    assert called == ["K:/manga/d_799677", "K:/manga/d_111111"]


def test_same_filename_id_does_not_refresh_on_page_turn():
    plugin = _plugin()
    called = []
    plugin.refresh = lambda folder: called.append(folder)
    plugin._on_current({"folder": "K:/manga", "path": "RJ123456_1.png"})
    plugin._on_current({"folder": "K:/manga", "path": "RJ123456_2.png"})
    assert called == ["K:/manga"]


def test_stop_fetch_does_not_drop_running_thread():
    plugin = _plugin()

    class Running:
        def isRunning(self):
            return True

        def quit(self):
            raise AssertionError("running fetch thread must not be quit")

    thread = Running()
    plugin._thread = thread
    plugin._stop_fetch()
    assert plugin._thread is thread


def test_start_fetch_queues_when_another_product_is_running():
    plugin = _plugin()

    class Running:
        def isRunning(self):
            return True

    thread = Running()
    plugin._thread = thread
    plugin._worker = SimpleNamespace(folder="a", kind="dmm", product_id="d_1")
    plugin._start_fetch("b", "dmm", "d_2")
    assert plugin._thread is thread
    assert plugin._pending_fetch == ("b", "dmm", "d_2")


class _Alive:
    def objectName(self):
        return "product_info"


def test_same_folder_does_not_reuse_other_product_cache():
    plugin = _plugin()
    plugin.widget = _Alive()
    shown = []
    started = []
    plugin._show_info = lambda data, folder, cover=None: shown.append(data.get("タイトル"))
    plugin._show_empty = lambda: None
    plugin._start_fetch = lambda folder, kind, pid: started.append((kind, pid))
    plugin._cache[("dlsite", "RJ111111")] = ({"タイトル": "One"}, None)
    plugin._on_current({"folder": "K:/manga", "path": "RJ222222.png"})
    assert shown == []
    assert started == [("dlsite", "RJ222222")]
    plugin._on_current({"folder": "K:/manga", "path": "RJ111111.png"})
    assert shown == ["One"]


def test_stale_fetch_result_is_discarded():
    plugin = _plugin()
    plugin.widget = _Alive()
    shown = []
    plugin._show_info = lambda data, folder, cover=None: shown.append(data.get("タイトル"))
    plugin._folder = "K:/manga"
    plugin._product_key = ("dlsite", "RJ222222")
    plugin._fetch_token = 2
    plugin._on_fetched(
        "K:/manga",
        {"タイトル": "One"},
        token=1,
        kind="dlsite",
        product_id="RJ111111",
    )
    assert shown == []
    plugin._on_fetched(
        "K:/manga",
        {"タイトル": "Two"},
        token=2,
        kind="dlsite",
        product_id="RJ222222",
    )
    assert shown == ["Two"]
    assert ("dlsite", "RJ222222") in plugin._cache
    assert ("dlsite", "RJ111111") not in plugin._cache
