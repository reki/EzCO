"""テスト共通。本番の APPDATA とプラグイン singleton を触らない。"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
_TESTS = Path(__file__).resolve().parent
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
sys.path[:] = [path for path in sys.path if Path(path).resolve() != _TESTS]

import pytest

from ez_co.plugins.manager import reset_plugin_manager
from ez_co.utils import data_location, path_utils
from ez_co.utils.database import CONFIG_DB_NAME, resolve_database_path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REPO_CONFIG_DB = _REPO_ROOT / CONFIG_DB_NAME


@pytest.fixture(autouse=True)
def isolate_app_data(tmp_path, monkeypatch):
    """user.json / data root / プロジェクトルートを一時ディレクトリへ向ける。本番の config.db は見ない。"""
    app_dir = tmp_path / "appdata"
    app_dir.mkdir()
    data_root = tmp_path / "data"
    data_root.mkdir()
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(data_location, "get_app_location_dir", lambda: app_dir)
    monkeypatch.setattr(path_utils, "get_project_root", lambda: project_root)
    monkeypatch.setattr(data_location, "get_project_root", lambda: project_root)
    data_location._data_root = None
    data_location.set_data_root(data_root)
    reset_plugin_manager()
    assert resolve_database_path().resolve() != _REPO_CONFIG_DB.resolve()
    yield
    reset_plugin_manager()
    data_location._data_root = None
    data_location._consent_version_cache = None


@pytest.fixture
def db_manager(qapp):
    """一時 data root 上に新しい config.db を作る。"""
    from ez_co.utils.database import DatabaseManager

    manager = DatabaseManager()
    assert manager.db_path.resolve() != _REPO_CONFIG_DB.resolve()
    assert manager.db_path.parent == data_location.get_data_root()
    return manager


def write_user_json(payload: dict) -> Path:
    """一時 user.json を書く。本番の APPDATA は見ない。"""
    path = data_location.location_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def write_dir_plugin(
    directory: Path,
    *,
    plugin_id: str,
    version: str = "1.0.0",
    name: str | None = None,
    folder_name: str | None = None,
    extension: str = ".probe",
    kind: str = "image",
    setup_counter: Path | None = None,
    license_name: str | None = "LICENSE.md",
    manifest_extra: dict | None = None,
) -> Path:
    """最小のディレクトリプラグインを置く。"""
    root = directory / (folder_name or plugin_id.split(".")[-1])
    src = root / "src"
    src.mkdir(parents=True)
    body = {
        "id": plugin_id,
        "name": name or plugin_id,
        "version": version,
        "api_version": 1,
        "entry": "plugin:ProbePlugin",
    }
    if manifest_extra:
        body.update(manifest_extra)
    (root / "manifest.json").write_text(json.dumps(body), encoding="utf-8")
    counter_line = ""
    if setup_counter is not None:
        setup_counter.write_text("0", encoding="utf-8")
        counter_line = f"COUNTER = r'''{setup_counter}'''\n"
    (src / "plugin.py").write_text(
        counter_line
        + "\n".join(
            [
                "class ProbePlugin:",
                "    def __init__(self, root, get_text, host):",
                "        self.root = root",
                f"    def supported_formats(self):",
                f"        return [({extension!r}, {kind!r})]",
                "    def setup(self):",
                "        if 'COUNTER' in globals():",
                "            from pathlib import Path",
                "            path = Path(COUNTER)",
                "            path.write_text(str(int(path.read_text() or '0') + 1), encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    if license_name:
        (root / license_name).write_text("test license\n", encoding="utf-8")
    return root


def write_zip_plugin(directory: Path, **kwargs) -> Path:
    """同じ内容の ZIP プラグインを置く。"""
    folder = write_dir_plugin(directory, **kwargs)
    zip_path = directory / f"{folder.name}.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        for path in folder.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(folder).as_posix())
    return zip_path


@pytest.fixture
def dir_plugin():
    return write_dir_plugin


@pytest.fixture
def zip_plugin():
    return write_zip_plugin


@pytest.fixture
def user_json():
    return write_user_json
