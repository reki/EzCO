"""対象: ez_co.services.image_loading_benchmark"""
import threading
from pathlib import Path

import pytest

from ez_co.config import Config
from ez_co.services.image_loading_benchmark import (
    STAGE_CACHE,
    STAGE_PREPARE,
    STAGE_WORKER,
    BenchmarkCancelled,
    BenchmarkCondition,
    generate_dataset,
    measure_condition,
    run_image_loading_benchmark,
)
from ez_co.utils import system_resources

GIB = 1024**3
SMALL_PAGES = 6

pytestmark = pytest.mark.usefixtures("qapp")


class _SmallDataset:
    """小さな素材を作り、置かれたrootを覚えておく。"""

    def __init__(self):
        self.roots = []

    def __call__(self, root: Path) -> Path:
        self.roots.append(Path(root))
        return generate_dataset(
            Path(root),
            page_count=SMALL_PAGES,
            page_size=(64, 64),
        )


def _run(**kwargs):
    defaults = dict(
        logical_cpu_count=4,
        physical_memory_bytes=8 * GIB,
        source_pages=SMALL_PAGES,
        measurement_pages=3,
        warmup_runs=0,
        measured_runs=1,
    )
    defaults.update(kwargs)
    return run_image_loading_benchmark(**defaults)


def test_single_condition_completes_with_small_dataset(tmp_path):
    dataset_path = generate_dataset(tmp_path, page_count=SMALL_PAGES, page_size=(64, 64))
    condition = BenchmarkCondition(
        stage=STAGE_WORKER,
        worker_count=2,
        memory_limit="256MB",
        prefetch_pages=5,
    )

    result = measure_condition(
        condition,
        dataset_path,
        source_pages=SMALL_PAGES,
        measurement_pages=3,
        warmup_runs=0,
        measured_runs=1,
    )

    assert result.worker_count == 2
    assert result.memory_limit == "256MB"
    assert result.prefetch_pages == 5
    assert result.average_latency_ms > 0
    assert result.p95_latency_ms >= result.p50_latency_ms
    assert result.max_latency_ms >= result.p95_latency_ms
    assert result.elapsed_seconds > 0
    assert result.duplicate_decode_count == 0


def test_run_measures_every_condition_and_reports_progress():
    dataset = _SmallDataset()
    progress = []

    report = _run(dataset_factory=dataset, progress=lambda *args: progress.append(args))

    assert [result.worker_count for result in report.stage_a_results()] == [1, 2]
    assert [
        (result.memory_limit, result.prefetch_pages)
        for result in report.stage_b_results()
    ] == [("256MB", 5), ("256MB", 10)]
    assert report.stage_a_winner_workers in (1, 2)
    assert report.elapsed_seconds > 0
    assert [call[0] for call in progress] == [
        STAGE_PREPARE,
        STAGE_WORKER,
        STAGE_WORKER,
        STAGE_CACHE,
        STAGE_CACHE,
    ]
    assert [call[4] for call in progress] == [4, 4, 4, 4, 4]


def test_temporary_dataset_is_removed_after_the_run():
    dataset = _SmallDataset()

    _run(dataset_factory=dataset)

    assert dataset.roots
    assert not dataset.roots[0].exists()


def test_cancel_stops_the_run_without_partial_results():
    dataset = _SmallDataset()
    cancel_event = threading.Event()

    def progress(stage, *args):
        if stage == STAGE_WORKER:
            cancel_event.set()

    with pytest.raises(BenchmarkCancelled):
        _run(
            dataset_factory=dataset,
            progress=progress,
            cancel_event=cancel_event,
        )

    assert not dataset.roots[0].exists()


def test_dataset_failure_still_removes_the_temporary_directory():
    roots = []

    def failing_factory(root):
        roots.append(Path(root))
        raise RuntimeError("dataset generation failed")

    with pytest.raises(RuntimeError):
        _run(dataset_factory=failing_factory)

    assert roots and not roots[0].exists()


def test_running_the_benchmark_does_not_change_the_real_config():
    config = Config()
    before = dict(config.cache)
    dataset = _SmallDataset()

    _run(dataset_factory=dataset)

    assert dict(config.cache) == before


def test_rss_baseline_is_taken_for_every_condition(monkeypatch: pytest.MonkeyPatch):
    step = 1024 * 1024
    counter = {"value": 0}

    def growing_resident_bytes():
        counter["value"] += 1
        return counter["value"] * step

    monkeypatch.setattr(
        system_resources,
        "process_resident_bytes",
        growing_resident_bytes,
    )
    dataset = _SmallDataset()

    report = _run(dataset_factory=dataset)

    deltas = [result.condition_rss_delta_bytes for result in report.results]
    # 各条件が開始直前のbaselineを取り直すので、条件順でdeltaが積み上がらない
    assert deltas == [3 * step] * len(report.results)
