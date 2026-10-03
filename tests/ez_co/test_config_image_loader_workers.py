"""対象: ez_co.config"""
import pytest

from ez_co.config import Config


pytestmark = pytest.mark.usefixtures("qapp")


def test_old_profile_without_worker_setting_defaults_to_auto():
    """ワーカー設定が無い古いプロファイルは auto になる。"""
    config = Config.from_dict({"cache": {"prefetch_pages": 5}})
    assert config.cache["image_loader_workers"] == "auto"


def test_invalid_profile_worker_setting_is_normalized_to_auto():
    """範囲外のワーカー数 99 は auto になる。"""
    config = Config.from_dict({"cache": {"image_loader_workers": 99}})
    assert config.cache["image_loader_workers"] == "auto"


def test_runtime_override_is_used_when_effective_value_is_first_frozen():
    """最初の固定では実行中オーバーライドの 7 が実効値にも開始時の値にもなる。"""
    config = Config()
    config.set_runtime_override("cache.image_loader_workers", 7)
    assert config.freeze_image_loader_workers(logical_cpu_count=2) == 7
    assert config.image_loader_workers_configured_at_start == 7


def test_effective_value_does_not_change_after_settings_or_profile_change():
    """一度固めた実効値 4 は、設定変更やオーバーライドや apply_dict のあとでも変わらない。"""
    config = Config.from_dict({"cache": {"image_loader_workers": 4}})
    assert config.freeze_image_loader_workers(logical_cpu_count=40) == 4

    config.cache["image_loader_workers"] = 8
    config.set_runtime_override("cache.image_loader_workers", 6)
    config.apply_dict({"cache": {"image_loader_workers": 2}})

    assert config.effective_image_loader_workers == 4
    assert config.image_loader_workers_configured_at_start == 4
    assert config.image_loader_logical_cpu_count == 40
