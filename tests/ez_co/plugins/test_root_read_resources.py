"""対象: ez_co.plugins.root — resources 配下の read_ui / read_asset / read_config。"""
import tempfile
from pathlib import Path

import pytest

from ez_co.plugins.root import PluginRoot, resource_relative


class _MemorySource:
    """名前でバイト列を返す、メモリ上のプラグインソース。"""

    def __init__(self, files: dict[str, bytes]):
        """ファイル名とバイト列を持つ。

        Args:
            files: 相対パスからバイト列への対応。
        """
        self.files = files

    def read_bytes(self, name: str) -> bytes:
        """その名前のバイト列を返す。

        Args:
            name: 相対パス。

        Returns:
            保存してあるバイト列。

        Raises:
            KeyError: 名前が無いとき。
        """
        if name not in self.files:
            raise KeyError(name)
        return self.files[name]

    def exists(self, name: str) -> bool:
        """その名前のファイルがあるかを返す。

        Args:
            name: 相対パス。

        Returns:
            あれば真。
        """
        return name in self.files

    def namelist(self):
        """持っている名前の一覧を返す。

        Returns:
            名前のリスト。
        """
        return list(self.files)

    def close(self):
        """閉じる操作は何もしない。"""
        return None


def test_resource_relative_prefixes_kind():
    """ui、assets、config が resources 配下の相対パスにならない。"""
    assert resource_relative("ui", "sidebar.ui") == "resources/ui/sidebar.ui"
    assert resource_relative("assets", "sounds/beep.wav") == "resources/assets/sounds/beep.wav"
    assert resource_relative("config", "fields.json") == "resources/config/fields.json"


def test_read_helpers_use_prefix_and_subfolder(tmp_path):
    """read_ui、read_asset、read_config が種類ごとの接頭辞とサブフォルダを外して読む。"""
    source = _MemorySource(
        {
            "resources/ui/sidebar.ui": b"<ui/>",
            "resources/assets/sounds/beep.wav": b"WAV",
            "resources/config/fields.json": b"[]",
        }
    )
    root = PluginRoot(tmp_path / "plugin", source, get_text=lambda key: key, host=None)
    assert root.read_ui("sidebar.ui") == b"<ui/>"
    assert root.read_asset("sounds/beep.wav") == b"WAV"
    assert root.read_config("fields.json") == b"[]"


def test_resource_relative_rejects_parent_and_absolute():
    """親ディレクトリ、絶対パス、空文字が KeyError にならない。"""
    with pytest.raises(KeyError):
        resource_relative("ui", "../outside.ui")
    with tempfile.TemporaryDirectory() as folder:
        with pytest.raises(KeyError):
            resource_relative("config", str(Path(folder) / "fields.json"))
    with pytest.raises(KeyError):
        resource_relative("assets", "")
