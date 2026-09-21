"""測定結果から採用する設定を決める。UIへ選択policyを書かない。"""
from __future__ import annotations

import math
from dataclasses import dataclass

import humanfriendly

from ez_co.services.image_loading_benchmark import (
    STAGE_CACHE,
    STAGE_WORKER,
    BenchmarkConditionResult,
    BenchmarkReport,
)
from ez_co.utils.image_loader_workers import AUTO_IMAGE_LOADER_WORKERS

# p95がこの幅に収まる条件は同等とみなし、次の基準（RSS増分・小さい資源）で選ぶ
P95_EQUIVALENCE_MS = 2.0


@dataclass(frozen=True)
class BenchmarkOutcome:
    """採用候補と、画面へ出す根拠。"""

    memory_limit: str
    prefetch_pages: int
    image_loader_workers: str | int
    effective_workers: int
    p95_latency_ms: float
    max_latency_ms: float
    condition_rss_delta_bytes: int | None
    elapsed_seconds: float


def _memory_limit_bytes(memory_limit: str) -> int:
    try:
        return int(humanfriendly.parse_size(memory_limit))
    except Exception:
        return 0


def _has_churn(result: BenchmarkConditionResult) -> bool:
    return result.redecode_count > 0 or result.prefetched_evicted_before_use > 0


def condition_sort_key(result: BenchmarkConditionResult) -> tuple:
    """duplicate decodeなし → churnなし → p95が低い → RSS増分が小 → 小さい資源。"""
    return (
        1 if result.duplicate_decode_count > 0 else 0,
        1 if _has_churn(result) else 0,
        math.floor(max(0.0, result.p95_latency_ms) / P95_EQUIVALENCE_MS),
        result.condition_rss_delta_bytes or 0,
        _memory_limit_bytes(result.memory_limit),
        result.prefetch_pages,
        result.worker_count,
    )


def select_stage_a_winner(results) -> int:
    """worker候補の勝者。同等ならworker数が少ない方を選ぶ。"""
    stage_a = [result for result in results if result.stage == STAGE_WORKER]
    if not stage_a:
        raise ValueError("stage A results are required to pick a worker count")
    return min(stage_a, key=condition_sort_key).worker_count


def select_best_condition(results) -> BenchmarkConditionResult:
    """Stage Bがあればその中から、無ければStage Aから決定的に選ぶ。"""
    stage_b = [result for result in results if result.stage == STAGE_CACHE]
    candidates = stage_b or list(results)
    if not candidates:
        raise ValueError("no benchmark results to evaluate")
    return min(candidates, key=condition_sort_key)


def evaluate_benchmark(report: BenchmarkReport) -> BenchmarkOutcome:
    """保存候補を作る。Stage A勝者がauto実効値と同じなら ``"auto"`` で保存する。"""
    best = select_best_condition(report.results)
    if report.stage_a_winner_workers == report.auto_effective_workers:
        workers: str | int = AUTO_IMAGE_LOADER_WORKERS
    else:
        workers = report.stage_a_winner_workers
    return BenchmarkOutcome(
        memory_limit=best.memory_limit,
        prefetch_pages=best.prefetch_pages,
        image_loader_workers=workers,
        effective_workers=report.stage_a_winner_workers,
        p95_latency_ms=best.p95_latency_ms,
        max_latency_ms=best.max_latency_ms,
        condition_rss_delta_bytes=best.condition_rss_delta_bytes,
        elapsed_seconds=report.elapsed_seconds,
    )
