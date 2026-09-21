"""対象: ez_co.config"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_cache_defaults_use_measured_prefetch_window():
    config = Config()
    assert config.cache["prefetch_pages"] == 5
    assert config.cache["memory_limit"] == "256MB"
    assert config.cache["image_loader_workers"] == "auto"


def test_default_config_dict_matches_instance_defaults():
    defaults = Config.get_default_config()
    assert defaults["cache"]["prefetch_pages"] == 5
    assert defaults["cache"]["memory_limit"] == "256MB"


def test_saved_prefetch_value_is_kept_and_not_reset_to_default():
    config = Config.from_dict({"cache": {"prefetch_pages": 30}})
    assert config.cache["prefetch_pages"] == 30
