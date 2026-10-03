"""対象: ez_co.services.image_loading_benchmark_evaluator"""
import pytest

from ez_co.services.image_loading_benchmark import (
    STAGE_CACHE,
    STAGE_WORKER,
    BenchmarkConditionResult,
    BenchmarkReport,
)
from ez_co.services.image_loading_benchmark_evaluator import (
    evaluate_benchmark,
    select_best_condition,
    select_stage_a_winner,
)

pytestmark = pytest.mark.usefixtures("qapp")


def make_result(
    *,
    stage=STAGE_CACHE,
    worker_count=4,
    memory_limit="256MB",
    prefetch_pages=5,
    p95=40.0,
    duplicate=0,
    redecode=0,
    evicted=0,
    rss_delta=100,
):
    """比較用の計測結果を、指定した差だけ変えて作る。

    Args:
        stage: 段階。
        worker_count: ワーカー数。
        memory_limit: キャッシュ上限。
        prefetch_pages: 先読みページ数。
        p95: p95 遅延。
        duplicate: 二重デコード回数。
        redecode: 再デコード回数。
        evicted: 使用前に落ちた先読み回数。
        rss_delta: RSS 増分。

    Returns:
        計測結果。
    """
    return BenchmarkConditionResult(
        stage=stage,
        worker_count=worker_count,
        memory_limit=memory_limit,
        prefetch_pages=prefetch_pages,
        average_latency_ms=p95 / 2,
        p50_latency_ms=p95 / 2,
        p95_latency_ms=p95,
        max_latency_ms=p95 * 2,
        duplicate_decode_count=duplicate,
        redecode_count=redecode,
        prefetched_evicted_before_use=evicted,
        cache_peak_bytes=1024,
        condition_rss_delta_bytes=rss_delta,
        elapsed_seconds=1.0,
    )


def make_report(results, *, winner=4, auto_workers=4):
    """段階 A の勝者ワーカー数と auto 実効値を持つ報告書を作る。

    Args:
        results: 計測結果。
        winner: 段階 A の勝者ワーカー数。
        auto_workers: auto の実効ワーカー数。

    Returns:
        報告書。
    """
    return BenchmarkReport(
        results=list(results),
        stage_a_winner_workers=winner,
        auto_effective_workers=auto_workers,
        logical_cpu_count=24,
        physical_memory_bytes=32 * 1024**3,
        elapsed_seconds=42.0,
        source_pages=64,
        measurement_pages=20,
        warmup_runs=1,
        measured_runs=3,
    )


def test_duplicate_decode_is_rejected_even_when_it_is_fastest():
    """二重デコードがある条件は、より速くても選ばれない。"""
    fast_but_duplicating = make_result(p95=10.0, duplicate=2, prefetch_pages=10)
    clean = make_result(p95=40.0)

    assert select_best_condition([fast_but_duplicating, clean]) is clean


def test_churn_free_condition_wins_over_a_slightly_faster_one():
    """再デコードがある条件は、少し速くても選ばれない。"""
    churning = make_result(p95=30.0, redecode=4, prefetch_pages=10)
    clean = make_result(p95=40.0)

    assert select_best_condition([churning, clean]) is clean


def test_unused_prefetch_eviction_counts_as_churn():
    """未使用先読みの追い出しがある条件は、少し速くても選ばれない。"""
    evicting = make_result(p95=30.0, evicted=3, prefetch_pages=10)
    clean = make_result(p95=40.0)

    assert select_best_condition([evicting, clean]) is clean


def test_lower_p95_wins_when_both_are_clean():
    """どちらも汚れが無ければ、p95 が小さい方が選ばれる。"""
    slow = make_result(p95=60.0, memory_limit="256MB")
    fast = make_result(p95=30.0, memory_limit="512MB")

    assert select_best_condition([slow, fast]) is fast


def test_equivalent_p95_falls_back_to_smaller_rss_delta():
    """p95 が同等なら、RSS 増分が小さい方が選ばれる。"""
    heavy = make_result(p95=40.0, rss_delta=900_000_000, memory_limit="256MB")
    light = make_result(p95=40.4, rss_delta=100_000_000, memory_limit="512MB")

    assert select_best_condition([heavy, light]) is light


def test_equivalent_results_prefer_the_smaller_cache_and_window():
    """同等なら、キャッシュ上限と先読み窓が小さい方が選ばれる。"""
    large = make_result(p95=40.0, memory_limit="512MB", prefetch_pages=10)
    small = make_result(p95=40.0, memory_limit="256MB", prefetch_pages=5)

    assert select_best_condition([large, small]) is small


def test_selection_is_deterministic_regardless_of_input_order():
    """入力順を逆にしても、選ばれるキャッシュ上限と先読みは同じになる。"""
    results = [
        make_result(p95=40.0, memory_limit="512MB", prefetch_pages=10),
        make_result(p95=40.0, memory_limit="256MB", prefetch_pages=5),
        make_result(p95=39.5, memory_limit="256MB", prefetch_pages=10, rss_delta=500),
    ]

    first = select_best_condition(results)
    second = select_best_condition(list(reversed(results)))

    assert (first.memory_limit, first.prefetch_pages) == (
        second.memory_limit,
        second.prefetch_pages,
    )


def test_stage_b_results_are_preferred_over_stage_a_results():
    """段階 A が速くても、選ばれるのは段階 B の結果になる。"""
    stage_a = make_result(stage=STAGE_WORKER, p95=1.0, memory_limit="256MB")
    stage_b = make_result(stage=STAGE_CACHE, p95=50.0, memory_limit="512MB")

    assert select_best_condition([stage_a, stage_b]) is stage_b


def test_stage_a_winner_prefers_fewer_workers_on_a_tie():
    """段階 A の p95 が同等なら、ワーカー数が少ない方が勝者になる。"""
    results = [
        make_result(stage=STAGE_WORKER, worker_count=3, p95=40.0),
        make_result(stage=STAGE_WORKER, worker_count=4, p95=40.2),
        make_result(stage=STAGE_WORKER, worker_count=5, p95=40.1),
    ]

    assert select_stage_a_winner(results) == 3


def test_stage_a_winner_uses_the_faster_worker_count():
    """段階 A の勝者は、p95 が小さい方のワーカー数になる。"""
    results = [
        make_result(stage=STAGE_WORKER, worker_count=3, p95=90.0),
        make_result(stage=STAGE_WORKER, worker_count=4, p95=40.0),
    ]

    assert select_stage_a_winner(results) == 4


def test_stage_a_winner_requires_stage_a_results():
    """段階 A の結果が無ければ段階 A の勝者は選べず ValueError になる。"""
    with pytest.raises(ValueError):
        select_stage_a_winner([make_result(stage=STAGE_CACHE)])


def test_auto_is_stored_when_the_winner_matches_the_auto_effective_value():
    """勝者ワーカー数が auto の実効値と同じなら保存値は auto になり、実効値と段階 B の上限、先読み、経過秒が残る。"""
    report = make_report(
        [
            make_result(stage=STAGE_WORKER, worker_count=4),
            make_result(stage=STAGE_CACHE, worker_count=4, memory_limit="512MB"),
        ],
        winner=4,
        auto_workers=4,
    )

    outcome = evaluate_benchmark(report)

    assert outcome.image_loader_workers == "auto"
    assert outcome.effective_workers == 4
    assert outcome.memory_limit == "512MB"
    assert outcome.prefetch_pages == 5
    assert outcome.elapsed_seconds == 42.0


def test_manual_worker_count_is_stored_when_it_beats_the_auto_value():
    """勝者ワーカー数が auto の実効値と違えば、その整数が保存される。"""
    report = make_report(
        [make_result(stage=STAGE_WORKER, worker_count=5)],
        winner=5,
        auto_workers=4,
    )

    outcome = evaluate_benchmark(report)

    assert outcome.image_loader_workers == 5
    assert outcome.effective_workers == 5


def test_evaluating_an_empty_report_raises():
    """結果の無い報告書の評価は ValueError になる。"""
    with pytest.raises(ValueError):
        evaluate_benchmark(make_report([]))
