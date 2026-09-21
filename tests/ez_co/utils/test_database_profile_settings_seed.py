"""対象: ez_co.utils.database"""
import pytest

from ez_co.config import Config
from ez_co.utils import system_resources
from ez_co.utils.database import DatabaseManager

GIB = 1024**3

pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture
def small_ram(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 4)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 8 * GIB)


@pytest.fixture
def large_ram(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 32 * GIB)


def test_first_database_seeds_recommended_values(large_ram):
    manager = DatabaseManager()

    seeded = manager.load_profile_config(manager.current_profile)

    assert seeded["cache"]["memory_limit"] == "512MB"
    assert seeded["cache"]["prefetch_pages"] == 5
    assert seeded["cache"]["image_loader_workers"] == "auto"


def test_small_ram_machine_is_seeded_with_safe_cache_limit(small_ram):
    manager = DatabaseManager()

    seeded = manager.load_profile_config(manager.current_profile)

    assert seeded["cache"]["memory_limit"] == "256MB"


def test_profile_without_given_settings_uses_recommended_values(large_ram):
    manager = DatabaseManager()

    assert manager.create_profile("seed-target", None)

    seeded = manager.load_profile_config("seed-target")
    assert seeded["cache"]["memory_limit"] == "512MB"
    assert seeded["cache"]["prefetch_pages"] == 5


def test_explicit_settings_are_stored_unchanged(large_ram):
    manager = DatabaseManager()
    source = Config.from_dict(
        {
            "cache": {
                "memory_limit": "1GB",
                "prefetch_pages": 30,
                "image_loader_workers": 8,
            }
        }
    )

    assert manager.create_profile("copy-target", source.to_dict())

    stored = manager.load_profile_config("copy-target")
    assert stored["cache"]["memory_limit"] == "1GB"
    assert stored["cache"]["prefetch_pages"] == 30
    assert stored["cache"]["image_loader_workers"] == 8


def test_seeding_again_keeps_existing_rows(large_ram):
    manager = DatabaseManager()
    source = Config.from_dict({"cache": {"prefetch_pages": 25}})
    assert manager.create_profile("keep-target", source.to_dict())

    manager._seed_missing_profile_settings()

    stored = manager.load_profile_config("keep-target")
    assert stored["cache"]["prefetch_pages"] == 25
