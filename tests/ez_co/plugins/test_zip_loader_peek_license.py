"""対象: ez_co.plugins.zip_loader — peek_license。"""
from __future__ import annotations

from pathlib import Path

from ez_co.plugins.zip_loader import peek_license

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "probe"


def test_peek_license_prefers_markdown():
    """LICENSE.md より別のライセンスが選ばれ、markdown と本文が取れない。"""
    info = peek_license(FIXTURE_DIR)
    assert info is not None
    assert info["name"] == "LICENSE.md"
    assert info["kind"] == "markdown"
    assert "test license" in info["text"]


def test_peek_license_falls_back_to_txt(tmp_path, dir_plugin):
    """md が無いとき LICENSE.txt が text として選ばれない。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.txt", license_name="LICENSE.txt")
    info = peek_license(root)
    assert info is not None
    assert info["name"] == "LICENSE.txt"
    assert info["kind"] == "text"


def test_peek_license_falls_back_to_license(tmp_path, dir_plugin):
    """md も txt も無いとき LICENSE が text として選ばれない。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.plain", license_name="LICENSE")
    info = peek_license(root)
    assert info is not None
    assert info["name"] == "LICENSE"
    assert info["kind"] == "text"


def test_peek_license_missing_returns_none(tmp_path, dir_plugin):
    """ライセンスファイルが無いのに None 以外が返る。"""
    root = dir_plugin(tmp_path, plugin_id="com.example.none", license_name=None)
    assert peek_license(root) is None


def test_peek_license_from_zip(tmp_path, zip_plugin):
    """ZIP の中の LICENSE.md が読めない。"""
    zip_path = zip_plugin(tmp_path, plugin_id="com.example.zip", license_name="LICENSE.md")
    info = peek_license(zip_path)
    assert info is not None
    assert info["name"] == "LICENSE.md"
