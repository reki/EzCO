"""対象: ez_co.utils.data_location — データ置き場の解決。"""
from pathlib import Path

from ez_co.utils import data_location


def test_resolve_data_root_user_mode():
    """ユーザー置き場はアプリ配置ディレクトリになる。"""
    app_dir = data_location.get_app_location_dir()
    root = data_location.resolve_data_root(
        {"data_location": data_location.LOCATION_USER, "custom_path": ""}
    )
    assert root == app_dir


def test_resolve_data_root_exe_mode_uses_isolated_project():
    """実行ファイル置き場は隔離したプロジェクトルートになり、位置ファイルの親もそこになる。"""
    project = data_location.get_project_root()
    root = data_location.resolve_data_root(
        {"data_location": data_location.LOCATION_EXE, "custom_path": ""}
    )
    assert root == project
    assert (project / data_location.LOCATION_FILENAME).parent == project


def test_resolve_data_root_custom_mode(tmp_path):
    """カスタム置き場は指定したパスそのものになる。"""
    custom = tmp_path / "custom-data"
    root = data_location.resolve_data_root(
        {"data_location": data_location.LOCATION_CUSTOM, "custom_path": str(custom)}
    )
    assert root == Path(custom)


def test_exe_config_db_path_is_not_repo_db():
    """実行ファイル側の config.db は隔離したプロジェクト直下で、リポジトリの config.db ではない。"""
    path = data_location.exe_config_db_path()
    assert path.name == "config.db"
    assert path.parent == data_location.get_project_root()
    repo = Path(__file__).resolve().parents[3] / "config.db"
    assert path.resolve() != repo.resolve()
