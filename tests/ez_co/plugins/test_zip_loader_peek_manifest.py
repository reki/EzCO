"""対象: ez_co.plugins.zip_loader — peek_manifest（dir / ZIP / 壊れ）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ez_co.plugins.zip_loader import peek_manifest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "probe"
FIXTURE_ZIP = Path(__file__).parent / "fixtures" / "probe.zip"


def test_peek_manifest_from_directory():
    info = peek_manifest(FIXTURE_DIR)
    assert info["id"] == "com.ezco.test.probe"
    assert info["name"] == "Probe"
    assert info["version"] == "1.0.0"


def test_peek_manifest_from_zip():
    info = peek_manifest(FIXTURE_ZIP)
    assert info["id"] == "com.ezco.test.probe"
    assert info["name"] == "Probe"


def test_peek_manifest_name_falls_back_to_path(tmp_path, dir_plugin):
    root = dir_plugin(tmp_path, plugin_id="com.example.anon", name="", folder_name="anon-folder")
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest.pop("name", None)
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    info = peek_manifest(root)
    assert info["id"] == "com.example.anon"
    assert info["name"] == root.name


def test_peek_manifest_missing_file_raises(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="manifest"):
        peek_manifest(empty)


def test_peek_manifest_missing_id_raises(tmp_path, dir_plugin):
    root = dir_plugin(tmp_path, plugin_id="com.example.x")
    (root / "manifest.json").write_text(json.dumps({"name": "NoId"}), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest.id"):
        peek_manifest(root)


def test_peek_manifest_broken_zip_raises(tmp_path):
    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    with pytest.raises(Exception):
        peek_manifest(broken)


def test_peek_manifest_generated_zip(tmp_path, zip_plugin):
    zip_path = zip_plugin(tmp_path, plugin_id="com.example.zipped", name="Zipped")
    info = peek_manifest(zip_path)
    assert info["id"] == "com.example.zipped"
    assert info["name"] == "Zipped"
