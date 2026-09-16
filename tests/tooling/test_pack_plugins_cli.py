"""対象: tooling.pack_plugins_cli"""
import json
import zipfile
from pathlib import Path

import pytest

from tooling.pack_plugins_cli import (
    iter_plugin_dirs,
    lint_plugin_dir,
    pack_plugin_dir,
    pack_plugins,
    zip_name_for,
)


def _write_plugin(root: Path, folder: str, *, manifest=None, module_name="plugin") -> Path:
    src = root / folder
    (src / "src").mkdir(parents=True)
    body = {
        "id": f"com.example.{folder}",
        "name": folder,
        "version": "1.0.0",
        "api_version": 1,
        "entry": f"{module_name}:Probe",
    }
    if manifest:
        body.update(manifest)
    (src / "manifest.json").write_text(json.dumps(body), encoding="utf-8")
    (src / "src" / f"{module_name}.py").write_text("class Probe:\n    pass\n", encoding="utf-8")
    return src


def test_iter_plugin_dirs_requires_manifest(tmp_path: Path):
    plugins = tmp_path / "plugins"
    (plugins / "ok").mkdir(parents=True)
    (plugins / "ok" / "manifest.json").write_text("{}", encoding="utf-8")
    (plugins / "skip").mkdir()
    (plugins / "README.md").write_text("x", encoding="utf-8")
    assert [path.name for path in iter_plugin_dirs(plugins)] == ["ok"]


def test_zip_name_includes_version():
    assert zip_name_for("example_zip", "1.1.0") == "example_zip-1.1.0.zip"


def test_pack_plugin_dir_puts_manifest_at_zip_root(tmp_path: Path):
    src = _write_plugin(tmp_path, "sample")
    cache = src / "src" / "__pycache__"
    cache.mkdir()
    (cache / "plugin.cpython-312.pyc").write_bytes(b"x")

    dest = tmp_path / "out" / "sample-1.0.0.zip"
    pack_plugin_dir(src, dest)

    with zipfile.ZipFile(dest) as archive:
        names = set(archive.namelist())
    assert "manifest.json" in names
    assert "src/plugin.py" in names
    assert not any("__pycache__" in name for name in names)
    assert "sample/manifest.json" not in names


def test_pack_plugins_writes_versioned_zip(tmp_path: Path):
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "keep_me", manifest={"version": "2.3.0"})
    _write_plugin(plugins, "skip_me")

    report = pack_plugins(tmp_path, ["keep_me"])
    assert report.success_count == 1
    assert report.fail_count == 0
    assert [path.name for path in report.written] == ["keep_me-2.3.0.zip"]
    assert (tmp_path / "dist-sample-plugins" / "keep_me-2.3.0.zip").is_file()
    assert not (tmp_path / "dist-sample-plugins" / "skip_me-1.0.0.zip").is_file()


def test_pack_plugins_unknown_name_is_failure_not_abort(tmp_path: Path):
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "only")
    report = pack_plugins(tmp_path, ["missing", "only"])
    assert report.success_count == 1
    assert report.fail_count == 1
    assert report.failed[0][0] == "missing"


def test_lint_rejects_invalid_json(tmp_path: Path):
    src = _write_plugin(tmp_path, "broken")
    (src / "manifest.json").write_text("{", encoding="utf-8")
    with pytest.raises(ValueError, match="構文エラー"):
        lint_plugin_dir(src)


def test_lint_rejects_invalid_version(tmp_path: Path):
    src = _write_plugin(tmp_path, "badver", manifest={"version": "not-a-version"})
    with pytest.raises(ValueError, match="valid version"):
        lint_plugin_dir(src)


def test_lint_rejects_unknown_permission(tmp_path: Path):
    src = _write_plugin(tmp_path, "badperm", manifest={"permissions": {"location": True}})
    with pytest.raises(ValueError, match="unknown key"):
        lint_plugin_dir(src)


def test_lint_rejects_non_bool_permission(tmp_path: Path):
    src = _write_plugin(
        tmp_path, "badperm", manifest={"permissions": {"inactive_callback": "yes"}}
    )
    with pytest.raises(ValueError, match="must be a bool"):
        lint_plugin_dir(src)


def test_pack_plugins_skips_invalid_and_continues(tmp_path: Path, capsys):
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "good")
    bad = _write_plugin(plugins, "bad", manifest={"version": "??"})
    (bad / "manifest.json").write_text("{", encoding="utf-8")

    report = pack_plugins(tmp_path)
    assert report.success_count == 1
    assert report.fail_count == 1
    assert report.written[0].name == "good-1.0.0.zip"
    assert report.failed[0][0] == "bad"
    err = capsys.readouterr().err
    assert "ERROR bad:" in err
