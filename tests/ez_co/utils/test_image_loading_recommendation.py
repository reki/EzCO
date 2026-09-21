"""対象: ez_co.utils.image_loading_recommendation"""
from types import SimpleNamespace

from ez_co.utils.image_loader_workers import AUTO_IMAGE_LOADER_WORKERS
from ez_co.utils.image_loading_recommendation import (
    LARGE_MEMORY_LIMIT,
    MEMORY_LIMIT_RAM_THRESHOLD_BYTES,
    RECOMMENDED_PREFETCH_PAGES,
    SAFE_MEMORY_LIMIT,
    apply_recommendation,
    auto_effective_workers,
    recommend_image_loading_settings,
)

GIB = 1024**3


def test_small_ram_uses_safe_memory_limit():
    recommendation = recommend_image_loading_settings(8, 8 * GIB)
    assert recommendation.memory_limit == SAFE_MEMORY_LIMIT


def test_ram_just_below_threshold_uses_safe_memory_limit():
    recommendation = recommend_image_loading_settings(
        24,
        MEMORY_LIMIT_RAM_THRESHOLD_BYTES - 1,
    )
    assert recommendation.memory_limit == SAFE_MEMORY_LIMIT


def test_ram_at_threshold_uses_large_memory_limit():
    recommendation = recommend_image_loading_settings(
        24,
        MEMORY_LIMIT_RAM_THRESHOLD_BYTES,
    )
    assert recommendation.memory_limit == LARGE_MEMORY_LIMIT


def test_unknown_ram_falls_back_to_safe_memory_limit():
    recommendation = recommend_image_loading_settings(None, None)
    assert recommendation.memory_limit == SAFE_MEMORY_LIMIT


def test_prefetch_and_workers_are_fixed_for_every_machine():
    for physical_memory in (None, 4 * GIB, 16 * GIB, 128 * GIB):
        recommendation = recommend_image_loading_settings(24, physical_memory)
        assert recommendation.prefetch_pages == RECOMMENDED_PREFETCH_PAGES == 5
        assert recommendation.image_loader_workers == AUTO_IMAGE_LOADER_WORKERS


def test_one_gigabyte_is_never_recommended():
    for physical_memory in (None, 16 * GIB, 64 * GIB, 512 * GIB):
        recommendation = recommend_image_loading_settings(64, physical_memory)
        assert recommendation.memory_limit in (
            SAFE_MEMORY_LIMIT,
            LARGE_MEMORY_LIMIT,
        )
        assert recommendation.memory_limit != "1GB"


def test_auto_effective_workers_matches_auto_resolver_table():
    assert auto_effective_workers(24) == 4
    assert auto_effective_workers(4) == 1
    assert auto_effective_workers(None) == 3


def test_apply_recommendation_touches_only_three_cache_keys():
    config = SimpleNamespace(
        cache={
            "memory_limit": "1GB",
            "prefetch_pages": 30,
            "image_loader_workers": 8,
            "optimize_large_images": True,
            "optimize_threshold": "50MB",
        },
        window={"width": 1280},
    )

    recommendation = apply_recommendation(
        config,
        recommend_image_loading_settings(24, 32 * GIB),
    )

    assert config.cache["memory_limit"] == LARGE_MEMORY_LIMIT
    assert config.cache["prefetch_pages"] == RECOMMENDED_PREFETCH_PAGES
    assert config.cache["image_loader_workers"] == AUTO_IMAGE_LOADER_WORKERS
    assert config.cache["optimize_large_images"] is True
    assert config.cache["optimize_threshold"] == "50MB"
    assert config.window == {"width": 1280}
    assert recommendation.memory_limit == LARGE_MEMORY_LIMIT


def test_apply_recommendation_without_argument_uses_system_resources(monkeypatch):
    import ez_co.utils.system_resources as system_resources

    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 4 * GIB)
    config = SimpleNamespace(cache={})

    apply_recommendation(config)

    assert config.cache["memory_limit"] == SAFE_MEMORY_LIMIT
    assert config.cache["prefetch_pages"] == RECOMMENDED_PREFETCH_PAGES
