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
        def register_config(self, *args, **kwargs):
            return None

        def get_config(self, key, default=None):
            return default

        def get_current(self, key):
            return None

    return ProductInfoPlugin(None, lambda *args, **kwargs: "", Host())


def test_same_folder_page_turn_does_not_refresh():
    plugin = _plugin()
    plugin._folder = "K:/manga/d_799677"
    called = []
    plugin.refresh = lambda folder: called.append(folder)
    plugin._on_current({"folder": "K:/manga/d_799677"})
    assert called == []
    plugin._on_current({"folder": "K:/manga/other"})
    assert called == ["K:/manga/other"]


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
