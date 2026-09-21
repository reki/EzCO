"""対象: ez_co.main"""
import pytest

from ez_co import main as main_module
from ez_co.utils import system_resources

GIB = 1024**3

pytestmark = pytest.mark.usefixtures("qapp")


class _FakeDatabaseManager:
    """load_config_from_db が使う最小のDB窓口。"""

    def __init__(self, data=None):
        self.current_profile = "default"
        self.data = data
        self.saved = {}

    def load_profile_config(self, profile_name):
        return self.data

    def save_profile_config(self, profile_name, payload):
        self.saved[profile_name] = payload
        return True


@pytest.fixture
def large_ram(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 32 * GIB)


def test_new_profile_config_is_created_with_recommended_values(large_ram):
    db_manager = _FakeDatabaseManager()

    config = main_module.load_config_from_db(db_manager)

    assert config.cache["memory_limit"] == "512MB"
    assert config.cache["prefetch_pages"] == 5
    assert config.cache["image_loader_workers"] == "auto"
    assert db_manager.saved["default"]["cache"]["memory_limit"] == "512MB"
    assert db_manager.saved["default"]["cache"]["prefetch_pages"] == 5


def test_low_ram_machine_gets_safe_cache_limit(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 4)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 8 * GIB)
    db_manager = _FakeDatabaseManager()

    config = main_module.load_config_from_db(db_manager)

    assert config.cache["memory_limit"] == "256MB"
    assert config.cache["prefetch_pages"] == 5


def test_existing_config_is_not_overwritten_by_recommendation(large_ram):
    existing = main_module.Config.from_dict(
        {
            "cache": {
                "memory_limit": "1GB",
                "prefetch_pages": 30,
                "image_loader_workers": 8,
            }
        }
    )
    db_manager = _FakeDatabaseManager(existing.to_dict())

    config = main_module.load_config_from_db(db_manager)

    assert config.cache["memory_limit"] == "1GB"
    assert config.cache["prefetch_pages"] == 30
    assert config.cache["image_loader_workers"] == 8
    assert db_manager.saved == {}
