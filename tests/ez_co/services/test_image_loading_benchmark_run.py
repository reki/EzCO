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
        """生成した root を空のリストで待ち受ける。"""
        self.roots = []

    def __call__(self, root: Path) -> Path:
        """渡された root を覚えて、小さなデータセットのパスを返す。

        Args:
            root: データセットを置くディレクトリ。

        Returns:
            生成したデータセットのパス。
        """
        self.roots.append(Path(root))
        return generate_dataset(
            Path(root),
            page_count=SMALL_PAGES,
            page_size=(64, 64),
        )


def _run(**kwargs):
    """小さなページ数と 1 回計測でベンチマークを走らせる。

    Args:
        kwargs: run_image_loading_benchmark へ渡す上書き。

    Returns:
        計測報告書。
    """
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
    """1 条件の計測は指定したワーカー数と上限と先読みを返し、遅延は正で二重デコードは 0 になる。"""
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
    """小容量の実行は段階 A がワーカー 1 と 2、段階 B が 256MB の先読み 5 と 10 になり、進捗は準備のあと各条件の順で総数は 4 になる。"""
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
    """実行が終わると、データセットを置いた一時ディレクトリは消える。"""
    dataset = _SmallDataset()

    _run(dataset_factory=dataset)

    assert dataset.roots
    assert not dataset.roots[0].exists()


def test_cancel_stops_the_run_without_partial_results():
    """ワーカー段階でキャンセルすると BenchmarkCancelled になり、一時ディレクトリは残らない。"""
    dataset = _SmallDataset()
    cancel_event = threading.Event()

    def progress(stage, *args):
        """ワーカー段階に入ったらキャンセルを立てる。

        Args:
            stage: 進捗の段階。
            args: 段階に続く進捗の値。
        """
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
    """データセット生成が失敗しても、置かれた一時ディレクトリは消える。"""
    roots = []

    def failing_factory(root):
        """置かれた root を覚えてから、データセット生成の失敗を送出する。

        Args:
            root: データセットを置くディレクトリ。

        Raises:
            RuntimeError: データセットを作れないとき。
        """
        roots.append(Path(root))
        raise RuntimeError("dataset generation failed")

    with pytest.raises(RuntimeError):
        _run(dataset_factory=failing_factory)

    assert roots and not roots[0].exists()


def test_running_the_benchmark_does_not_change_the_real_config():
    """ベンチマークを走らせても、実行前のキャッシュ設定は変わらない。"""
    config = Config()
    before = dict(config.cache)
    dataset = _SmallDataset()

    _run(dataset_factory=dataset)

    assert dict(config.cache) == before


def test_rss_baseline_is_taken_for_every_condition(monkeypatch: pytest.MonkeyPatch):
    """各条件の RSS 増分は、開始直前を基準にした同じ値になる。"""
    step = 1024 * 1024
    counter = {"value": 0}

    def growing_resident_bytes():
        """呼ぶたびに RSS を一定量増やす。

        Returns:
            増やしたあとのバイト数。
        """
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
