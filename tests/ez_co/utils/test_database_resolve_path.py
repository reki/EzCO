"""対象: ez_co.utils.database — resolve_database_path。"""
from ez_co.utils import data_location
from ez_co.utils.database import CONFIG_DB_NAME, LEGACY_DB_NAME, resolve_database_path


def test_resolve_database_path_is_under_temp_data_root():
    path = resolve_database_path()
    assert path.name == CONFIG_DB_NAME
    assert path.parent == data_location.get_data_root()
    assert path.resolve() != (data_location.get_project_root() / CONFIG_DB_NAME).resolve()


def test_resolve_database_path_renames_legacy_bookmarks():
    root = data_location.get_data_root()
    legacy = root / LEGACY_DB_NAME
    legacy.write_bytes(b"legacy")
    path = resolve_database_path()
    assert path == root / CONFIG_DB_NAME
    assert path.is_file()
    assert not legacy.exists()
    assert path.read_bytes() == b"legacy"


def test_resolve_database_path_keeps_config_when_both_exist():
    root = data_location.get_data_root()
    config_db = root / CONFIG_DB_NAME
    legacy = root / LEGACY_DB_NAME
    config_db.write_bytes(b"config")
    legacy.write_bytes(b"legacy")
    path = resolve_database_path()
    assert path == config_db
    assert config_db.read_bytes() == b"config"
    assert legacy.exists()
