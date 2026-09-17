"""対象: plugins/example_txt/src/layout.py — 文字コード一覧の先頭順。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PLUGIN_SRC = Path(__file__).resolve().parents[3] / "plugins" / "example_txt" / "src"

pytestmark = pytest.mark.usefixtures("qapp")


def _layout():
    if str(PLUGIN_SRC) not in sys.path:
        sys.path.insert(0, str(PLUGIN_SRC))
    import layout

    return layout


def test_charset_names_put_common_codecs_first():
    names = _layout().charset_names()
    assert names[:4] == ("utf-8", "cp932", "shift_jis", "latin_1")
    rest = names[4:]
    assert rest == tuple(sorted(rest))
    assert names.count("utf-8") == 1
    assert "cp932" in names
