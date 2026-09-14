"""対象: ez_co.utils.data_location — データ置き場の解決。"""
from pathlib import Path

from ez_co.utils import data_location


def test_resolve_data_root_user_mode():
    app_dir = data_location.get_app_location_dir()
    root = data_location.resolve_data_root(
        {"data_location": data_location.LOCATION_USER, "custom_path": ""}
    )
    assert root == app_dir


def test_resolve_data_root_exe_mode_uses_isolated_project():
    project = data_location.get_project_root()
    root = data_location.resolve_data_root(
        {"data_location": data_location.LOCATION_EXE, "custom_path": ""}
    )
    assert root == project
    assert (project / data_location.LOCATION_FILENAME).parent == project


def test_resolve_data_root_custom_mode(tmp_path):
    custom = tmp_path / "custom-data"
    root = data_location.resolve_data_root(
        {"data_location": data_location.LOCATION_CUSTOM, "custom_path": str(custom)}
    )
    assert root == Path(custom)


def test_exe_config_db_path_is_not_repo_db():
    path = data_location.exe_config_db_path()
    assert path.name == "config.db"
    assert path.parent == data_location.get_project_root()
    repo = Path(__file__).resolve().parents[3] / "config.db"
    assert path.resolve() != repo.resolve()
