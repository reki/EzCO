"""対象: ez_co.services.image_loading_benchmark"""
import pytest

from ez_co.services.image_loading_benchmark import (
    STAGE_CACHE,
    STAGE_WORKER,
    condition_total,
    stage_a_conditions,
    stage_b_conditions,
    stage_b_memory_limits,
)

GIB = 1024**3

pytestmark = pytest.mark.usefixtures("qapp")


def test_stage_a_is_centred_on_auto_effective_workers():
    """24 論理 CPU の段階 A はワーカー 3、4、5 で、先読み 5 と 512MB になる。"""
    conditions = stage_a_conditions(24, 32 * GIB)

    assert [condition.worker_count for condition in conditions] == [3, 4, 5]
    assert all(condition.stage == STAGE_WORKER for condition in conditions)
    assert all(condition.prefetch_pages == 5 for condition in conditions)
    assert all(condition.memory_limit == "512MB" for condition in conditions)


def test_stage_a_center_ignores_manual_worker_setting_in_config():
    """設定上の手動ワーカー数が 8 でも、段階 A の中心は 3、4、5 のまま。"""
    from ez_co.config import Config

    config = Config.from_dict({"cache": {"image_loader_workers": 8}})
    assert config.cache["image_loader_workers"] == 8

    conditions = stage_a_conditions(24, 32 * GIB)

    assert [condition.worker_count for condition in conditions] == [3, 4, 5]


def test_stage_a_clips_and_dedupes_at_the_lower_bound():
    """下限に当たるとワーカー数は 1 と 2 になる。"""
    conditions = stage_a_conditions(4, 8 * GIB)

    assert [condition.worker_count for condition in conditions] == [1, 2]


def test_stage_a_clips_at_the_upper_bound():
    """上限ではワーカー数が 5、6、7 になる。"""
    conditions = stage_a_conditions(40, 32 * GIB)

    assert [condition.worker_count for condition in conditions] == [5, 6, 7]


def test_stage_a_uses_safe_cache_limit_when_ram_is_unknown():
    """CPU もメモリも不明な段階 A はワーカー 2、3、4 と 256MB になる。"""
    conditions = stage_a_conditions(None, None)

    assert [condition.worker_count for condition in conditions] == [2, 3, 4]
    assert all(condition.memory_limit == "256MB" for condition in conditions)


def test_stage_b_covers_cache_and_prefetch_pairs():
    """段階 B は 256MB と 512MB のそれぞれに先読み 5 と 10 を組み合わせ、ワーカー数は渡した値になる。"""
    conditions = stage_b_conditions(4, 32 * GIB)

    assert [
        (condition.memory_limit, condition.prefetch_pages) for condition in conditions
    ] == [("256MB", 5), ("256MB", 10), ("512MB", 5), ("512MB", 10)]
    assert all(condition.worker_count == 4 for condition in conditions)
    assert all(condition.stage == STAGE_CACHE for condition in conditions)


def test_stage_b_never_measures_one_gigabyte():
    """どのメモリ量でも段階 B の上限と条件に 1GB は入らない。"""
    for physical_memory in (None, 8 * GIB, 32 * GIB, 256 * GIB):
        limits = stage_b_memory_limits(physical_memory)
        assert "1GB" not in limits
        conditions = stage_b_conditions(4, physical_memory)
        assert all(condition.memory_limit != "1GB" for condition in conditions)


def test_small_ram_machine_skips_the_large_cache_candidate():
    """小容量メモリの段階 B は 256MB だけになり、条件総数は 4 になる。"""
    conditions = stage_b_conditions(2, 8 * GIB)

    assert [condition.memory_limit for condition in conditions] == ["256MB", "256MB"]
    assert condition_total(8 * GIB, 4) == 2 + 2


def test_condition_total_never_exceeds_seven():
    """どの CPU 数とメモリ量でも条件総数は 7 を超えない。"""
    for cpu_count in (None, 1, 4, 8, 16, 24, 32, 64):
        for physical_memory in (None, 8 * GIB, 32 * GIB):
            assert condition_total(physical_memory, cpu_count) <= 7


def test_condition_total_matches_generated_conditions():
    """条件総数は生成した段階 A と段階 B の件数の和と一致する。"""
    stage_a = stage_a_conditions(24, 32 * GIB)
    stage_b = stage_b_conditions(4, 32 * GIB)

    assert condition_total(32 * GIB, 24) == len(stage_a) + len(stage_b) == 7
