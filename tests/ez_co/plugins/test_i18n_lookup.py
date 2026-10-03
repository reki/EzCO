"""対象: ez_co.plugins.i18n — resources/langs を先頭に読む。"""
from __future__ import annotations

import json

from ez_co.plugins.i18n import make_plugin_get_text
from ez_co.utils.language_manager import set_language


class _LangRoot:
    """言語ファイルのバイト列だけを持つプラグイン root。"""

    def __init__(self, files: dict[str, bytes]):
        """ファイル名とバイト列、空の言語キャッシュを持つ。

        Args:
            files: 相対パスからバイト列への対応。
        """
        self.files = files
        self._lang_cache = {}

    def exists(self, name: str) -> bool:
        """その名前のファイルがあるかを返す。

        Args:
            name: 相対パス。

        Returns:
            あれば真。
        """
        return name in self.files

    def read_bytes(self, name: str) -> bytes:
        """その名前のバイト列を返す。

        Args:
            name: 相対パス。

        Returns:
            保存してあるバイト列。
        """
        return self.files[name]


def _json(payload: dict) -> bytes:
    """辞書を UTF-8 の JSON バイトにする。

    Args:
        payload: 言語ファイルの中身。

    Returns:
        JSON のバイト列。
    """
    return json.dumps(payload).encode("utf-8")


def test_resources_langs_wins_over_legacy_paths(monkeypatch):
    """resources/langs より langs や src/langs の title が勝つ。"""
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
    """resources/langs が無いとき、langs の title が読まれない。"""
    set_language("ja")
    root = _LangRoot({"langs/ja.json": _json({"title": "legacy"})})
    get_text = make_plugin_get_text(root)
    assert get_text("title") == "legacy"


def test_src_langs_used_when_others_missing(monkeypatch):
    """resources も langs も無いとき、src/langs の title が読まれない。"""
    set_language("ja")
    root = _LangRoot({"src/langs/ja.json": _json({"title": "src"})})
    get_text = make_plugin_get_text(root)
    assert get_text("title") == "src"
