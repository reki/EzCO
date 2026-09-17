"""対象: ez_co.plugins.root — resources 配下の read_ui / read_asset / read_config。"""
import tempfile
from pathlib import Path

import pytest

from ez_co.plugins.root import PluginRoot, resource_relative


class _MemorySource:
    def __init__(self, files: dict[str, bytes]):
        self.files = files

    def read_bytes(self, name: str) -> bytes:
        if name not in self.files:
            raise KeyError(name)
        return self.files[name]

    def exists(self, name: str) -> bool:
        return name in self.files

    def namelist(self):
        return list(self.files)

    def close(self):
        return None


def test_resource_relative_prefixes_kind():
    assert resource_relative("ui", "sidebar.ui") == "resources/ui/sidebar.ui"
    assert resource_relative("assets", "sounds/beep.wav") == "resources/assets/sounds/beep.wav"
    assert resource_relative("config", "fields.json") == "resources/config/fields.json"


def test_read_helpers_use_prefix_and_subfolder(tmp_path):
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
    with pytest.raises(KeyError):
        resource_relative("ui", "../outside.ui")
    with tempfile.TemporaryDirectory() as folder:
        with pytest.raises(KeyError):
            resource_relative("config", str(Path(folder) / "fields.json"))
    with pytest.raises(KeyError):
        resource_relative("assets", "")
