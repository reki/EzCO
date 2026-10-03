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
    """8GB ではメモリ上限が安全側になる。"""
    recommendation = recommend_image_loading_settings(8, 8 * GIB)
    assert recommendation.memory_limit == SAFE_MEMORY_LIMIT


def test_ram_just_below_threshold_uses_safe_memory_limit():
    """閾値の 1 バイト下ではメモリ上限が安全側になる。"""
    recommendation = recommend_image_loading_settings(
        24,
        MEMORY_LIMIT_RAM_THRESHOLD_BYTES - 1,
    )
    assert recommendation.memory_limit == SAFE_MEMORY_LIMIT


def test_ram_at_threshold_uses_large_memory_limit():
    """閾値ちょうどではメモリ上限が大きい側になる。"""
    recommendation = recommend_image_loading_settings(
        24,
        MEMORY_LIMIT_RAM_THRESHOLD_BYTES,
    )
    assert recommendation.memory_limit == LARGE_MEMORY_LIMIT


def test_unknown_ram_falls_back_to_safe_memory_limit():
    """CPU もメモリも不明ならメモリ上限は安全側になる。"""
    recommendation = recommend_image_loading_settings(None, None)
    assert recommendation.memory_limit == SAFE_MEMORY_LIMIT


def test_prefetch_and_workers_are_fixed_for_every_machine():
    """メモリ量が違っても先読みページ数は 5、ワーカー指定は auto のまま。"""
    for physical_memory in (None, 4 * GIB, 16 * GIB, 128 * GIB):
        recommendation = recommend_image_loading_settings(24, physical_memory)
        assert recommendation.prefetch_pages == RECOMMENDED_PREFETCH_PAGES == 5
        assert recommendation.image_loader_workers == AUTO_IMAGE_LOADER_WORKERS


def test_one_gigabyte_is_never_recommended():
    """どのメモリ量でも推奨上限は安全側か大きい側だけで、1GB にはならない。"""
    for physical_memory in (None, 16 * GIB, 64 * GIB, 512 * GIB):
        recommendation = recommend_image_loading_settings(64, physical_memory)
        assert recommendation.memory_limit in (
            SAFE_MEMORY_LIMIT,
            LARGE_MEMORY_LIMIT,
        )
        assert recommendation.memory_limit != "1GB"


def test_auto_effective_workers_matches_auto_resolver_table():
    """auto の実効ワーカー数は 24 論理 CPU で 4、4 で 1、不明で 3 になる。"""
    assert auto_effective_workers(24) == 4
    assert auto_effective_workers(4) == 1
    assert auto_effective_workers(None) == 3


def test_apply_recommendation_touches_only_three_cache_keys():
    """推奨の適用はメモリ上限、先読み、ワーカーだけを変え、最適化設定とウィンドウは残す。"""
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
    """引数なしの適用は、測定した CPU とメモリから安全側の上限と先読みを書く。"""
    import ez_co.utils.system_resources as system_resources

    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 4 * GIB)
    config = SimpleNamespace(cache={})

    apply_recommendation(config)

    assert config.cache["memory_limit"] == SAFE_MEMORY_LIMIT
    assert config.cache["prefetch_pages"] == RECOMMENDED_PREFETCH_PAGES
