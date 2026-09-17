"""対象: ez_co.plugins.i18n — resources/langs を先頭に読む。"""
from __future__ import annotations

import json

from ez_co.plugins.i18n import make_plugin_get_text
from ez_co.utils.language_manager import set_language


class _LangRoot:
    def __init__(self, files: dict[str, bytes]):
        self.files = files
        self._lang_cache = {}

    def exists(self, name: str) -> bool:
        return name in self.files

    def read_bytes(self, name: str) -> bytes:
        return self.files[name]


def _json(payload: dict) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_resources_langs_wins_over_legacy_paths(monkeypatch):
    set_language("ja")
    root = _LangRoot(
        {
            "resources/langs/ja.json": _json({"title": "resources"}),
            "langs/ja.json": _json({"title": "legacy"}),
            "src/langs/ja.json": _json({"title": "src"}),
        }
    )
    get_text = make_plugin_get_text(root)
    assert get_text("title") == "resources"


def test_legacy_langs_used_when_resources_missing(monkeypatch):
    set_language("ja")
    root = _LangRoot({"langs/ja.json": _json({"title": "legacy"})})
    get_text = make_plugin_get_text(root)
    assert get_text("title") == "legacy"


def test_src_langs_used_when_others_missing(monkeypatch):
    set_language("ja")
    root = _LangRoot({"src/langs/ja.json": _json({"title": "src"})})
    get_text = make_plugin_get_text(root)
    assert get_text("title") == "src"
