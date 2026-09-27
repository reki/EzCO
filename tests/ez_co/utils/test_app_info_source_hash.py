"""対象: ez_co.utils.app_info"""
import json
from pathlib import Path

import pytest

from ez_co.utils import app_info
from ez_co.utils.app_info import (
    INFO_JSON_RELATIVE,
    current_build_id,
    short_build_id,
    source_tree_hash,
    stamped_info_json,
)


def _write(root: Path, relative: str, data: bytes) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _tree(root: Path) -> None:
    _write(root, "ez_co/a.txt", b"alpha")
    _write(root, "ez_co/b/c.txt", b"beta")


def test_hash_is_64_lowercase_hex(tmp_path: Path):
    _tree(tmp_path)
    digest = source_tree_hash(tmp_path)
    assert len(digest) == 64
    assert digest == digest.lower()
    int(digest, 16)


def test_walk_order_does_not_change_the_hash(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    _write(first, "ez_co/b/c.txt", b"beta")
    _write(first, "ez_co/a.txt", b"alpha")
    _write(second, "ez_co/a.txt", b"alpha")
    _write(second, "ez_co/b/c.txt", b"beta")
    assert source_tree_hash(first) == source_tree_hash(second)


def test_content_change_changes_the_hash(tmp_path: Path):
    _tree(tmp_path)
    before = source_tree_hash(tmp_path)
    _write(tmp_path, "ez_co/a.txt", b"alpha2")
    assert source_tree_hash(tmp_path) != before


def test_path_change_changes_the_hash(tmp_path: Path):
    _tree(tmp_path)
    before = source_tree_hash(tmp_path)
    source = tmp_path / "ez_co/a.txt"
    source.rename(tmp_path / "ez_co/a-renamed.txt")
    assert source_tree_hash(tmp_path) != before


def test_adding_and_removing_a_file_changes_the_hash(tmp_path: Path):
    _tree(tmp_path)
    before = source_tree_hash(tmp_path)
    _write(tmp_path, "ez_co/extra.txt", b"more")
    added = source_tree_hash(tmp_path)
    assert added != before
    (tmp_path / "ez_co/extra.txt").unlink()
    assert source_tree_hash(tmp_path) == before


def test_info_json_and_pycache_are_excluded(tmp_path: Path):
    _tree(tmp_path)
    before = source_tree_hash(tmp_path)
    _write(tmp_path, INFO_JSON_RELATIVE, b'{"hash":"should-not-count"}')
    _write(tmp_path, "ez_co/__pycache__/a.pyc", b"bytecode")
    assert source_tree_hash(tmp_path) == before


def test_short_build_id_is_the_leading_16_characters():
    full = "ab" * 32
    assert short_build_id(full) == full[:16]
    assert len(short_build_id(full)) == 16


def test_source_launch_computes_and_nuitka_uses_the_stored_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    from ez_co.utils import path_utils

    src = tmp_path / "src"
    _tree(src)
    monkeypatch.setattr(path_utils, "is_nuitka", lambda: False)
    monkeypatch.setattr(path_utils, "get_project_root", lambda: tmp_path)
    assert current_build_id() == source_tree_hash(src)

    stored = "cd" * 32
    monkeypatch.setattr(path_utils, "is_nuitka", lambda: True)
    monkeypatch.setattr(app_info, "load_app_info", lambda: {"hash": stored, "version": "1"})
    assert current_build_id() == stored


def test_stamp_changes_only_hash_and_restore_matches_original_bytes(tmp_path: Path):
    info_path = tmp_path / "info.json"
    original = (
        '{\n  "name": "EzCo",\n  "version": "1.1.2",\n  "hash": ""\n}\n'
    ).encode("utf-8")
    info_path.write_bytes(original)
    build_id = "ef" * 32
    try:
        with stamped_info_json(info_path, build_id):
            stamped = json.loads(info_path.read_text(encoding="utf-8"))
            assert stamped["hash"] == build_id
            assert stamped["name"] == "EzCo"
            assert stamped["version"] == "1.1.2"
            raise KeyboardInterrupt
    except KeyboardInterrupt:
        pass
    assert info_path.read_bytes() == original
