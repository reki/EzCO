"""対象: tooling.image_loader_benchmark"""
import threading
from pathlib import Path

import pytest

import tooling.image_loader_benchmark as benchmark
from tooling.image_loader_benchmark import (
    POLICY_MATRIX_MEASUREMENT_PAGES,
    POLICY_MATRIX_MEMORY_LIMITS,
    POLICY_MATRIX_PREFETCH_PAGES,
    POLICY_MATRIX_SOURCE_PAGES,
    POLICY_MATRIX_WORKER_COUNT,
    BenchmarkImageLoadScheduler,
    BenchmarkFileHandler,
    Dataset,
    RunResult,
    _benchmark_config,
    aggregate_results,
    cache_candidate_conditions,
    generate_datasets,
    matrix_conditions,
    multi_handler_conditions,
    percentile,
    policy_matrix_conditions,
    prefetch_window_conditions,
    render_matrix_markdown,
    render_policy_matrix_markdown,
    run_condition_subprocess,
    run_cold_jump_condition,
    run_collision_condition,
    run_multi_handler_condition,
    run_once,
    run_policy_matrix,
    worker_order,
)

# 計測に使うデータセット名。
DATASET_NAMES = ("jpg_folder", "jpg_png_zip", "high_resolution_zip")


def _stub_datasets(root: Path) -> list[Dataset]:
    """実ファイルを作らず、名前だけの Dataset を返す。

    Args:
        root: 各データセットの親パス。

    Returns:
        3種の Dataset。
    """
    return [Dataset(name, root / name) for name in DATASET_NAMES]


def test_worker_order_is_seeded_and_contains_all_manual_values():
    """同じ種のワーカー順が再現せず、1 から 8 のどれかが欠ける。"""
    assert worker_order(10) == worker_order(10)
    assert sorted(worker_order(10)) == list(range(1, 9))


def test_percentile_interpolates_sorted_samples():
    """空の標本が 0 以外になり、中央か 95% 点の内分がずれる。"""
    assert percentile([], 0.95) == 0.0
    assert percentile([40, 10, 20, 30], 0.5) == 25.0
    assert percentile([1, 2, 3, 4, 5], 0.95) == 4.8


def test_generate_datasets_and_run_actual_loading_paths(tmp_path: Path):
    """3種のどれかが欠け、成功ページが 3 以外になるか重複デコードが出る。"""
    datasets = generate_datasets(
        tmp_path,
        page_count=3,
        folder_size=(32, 24),
        mixed_size=(32, 24),
        high_resolution_size=(48, 64),
    )

    assert [dataset.name for dataset in datasets] == [
        "jpg_folder",
        "jpg_png_zip",
        "high_resolution_zip",
    ]
    for dataset in datasets:
        result = run_once(
            dataset,
            workers=2,
            memory_limit="512MB",
            prefetch_pages=7,
        )
        assert result.successful_pages == 3
        assert len(result.latencies_ms) == 3
        assert result.cache_hits + result.cache_misses == 3
        assert result.memory_limit == "512MB"
        assert result.prefetch_pages == 7
        assert result.duplicate_decode_count == 0
        assert result.decoded_total_bytes > 0


def test_aggregate_results_uses_all_runs():
    """片方の実行を落とすと合わない遅延・ヒット・追い出し・キュー最大・RSS 差を、2回分で使う。"""
    results = [
        RunResult(
            dataset="pages",
            worker_count=3,
            memory_limit="512MB",
            prefetch_pages=15,
            latencies_ms=[1.0, 3.0],
            wall_seconds=2.0,
            cpu_seconds=1.0,
            successful_pages=2,
            cache_hits=1,
            cache_misses=1,
            cache_peak_bytes=100,
            prefetched_evicted_before_use=1,
            prefetched_evicted_before_use_bytes=10,
            prefetched_image_count=2,
            prefetched_image_bytes=20,
            duplicate_decode_count=0,
            redecode_count=0,
            decoded_total_bytes=100,
            decoded_average_bytes_per_page=50.0,
            decoded_max_bytes_per_page=60,
            queue_depth_samples=[0, 2, 1],
            active_worker_samples=[0, 1],
            rss_bytes=None,
        ),
        RunResult(
            dataset="pages",
            worker_count=3,
            memory_limit="512MB",
            prefetch_pages=15,
            latencies_ms=[5.0, 7.0],
            wall_seconds=2.0,
            cpu_seconds=2.0,
            successful_pages=2,
            cache_hits=2,
            cache_misses=0,
            cache_peak_bytes=200,
            prefetched_evicted_before_use=2,
            prefetched_evicted_before_use_bytes=20,
            prefetched_image_count=3,
            prefetched_image_bytes=30,
            duplicate_decode_count=1,
            redecode_count=1,
            decoded_total_bytes=100,
            decoded_average_bytes_per_page=50.0,
            decoded_max_bytes_per_page=60,
            queue_depth_samples=[3, 1],
            active_worker_samples=[2, 1],
            rss_bytes=300,
        ),
    ]

    result = aggregate_results(
        results,
        rss_start_bytes=100,
        rss_end_bytes=250,
        rss_peak_bytes=400,
    )

    assert result["runs"] == 2
    assert result["samples"] == 4
    assert result["average_latency_ms"] == 4.0
    assert result["p50_latency_ms"] == 4.0
    assert result["cache_hits"] == 3
    assert result["cache_hit_rate"] == 0.75
    assert result["duplicate_decode_count"] == 1
    assert result["prefetched_evicted_before_use"] == 3
    assert result["prefetched_evicted_before_use_bytes"] == 30
    assert result["prefetched_image_count"] == 5
    assert result["cache_peak_bytes"] == 200
    assert result["decoded_total_bytes"] == 100
    assert result["queue_depth_max"] == 3
    assert result["queue_depth_event_sample_p95"] > 2
    assert result["active_workers_max"] == 2
    assert "not wall-clock" in result["queue_sample_semantics"]
    assert result["rss_peak_bytes"] == 400
    assert result["rss_delta_bytes"] == 150


def test_matrix_has_all_24_unique_conditions_in_seeded_order():
    """同じ種の行列が順まで一致せず、24 件が重複するかワーカーかメモリの集合が欠ける。"""
    first = matrix_conditions(99)
    second = matrix_conditions(99)

    assert first == second
    assert len(first) == 24
    assert len(set(first)) == 24
    assert {workers for workers, _memory in first} == set(range(1, 9))
    assert {memory for _workers, memory in first} == {"256MB", "512MB", "1GB"}


def test_benchmark_config_applies_memory_and_prefetch_values():
    """計測用設定のメモリ上限か先読みページが、渡した値のまま入らない。"""
    config = _benchmark_config("1GB", 9)
    assert config.cache["memory_limit"] == "1GB"
    assert config.cache["prefetch_pages"] == 9


def test_markdown_contains_sorted_matrix_fields():
    """行列の Markdown 行が、メモリ・ワーカー・p95・ヒット率・再デコード・追い出し・RSS の順にならない。"""
    result = {
        "memory_limit": "512MB",
        "worker_count": 2,
        "p95_latency_ms": 12.345,
        "cache_hit_rate": 0.75,
        "duplicate_decode_count": 0,
        "redecode_count": 3,
        "prefetched_evicted_before_use": 4,
        "prefetched_evicted_before_use_bytes": 500,
        "rss_peak_bytes": 600,
    }
    text = render_matrix_markdown({"results": [result]})
    assert "| 512MB | 2 | 12.35 | 75.00% | 0 | 3 | 4 | 500 | 600 |" in text


def test_duplicate_decode_counter_is_thread_safe():
    """同じキーのデコードが重なると重複が 1 件以外になり、加算が割れる。"""
    handler = BenchmarkFileHandler(_benchmark_config(), worker_count=1)
    entered = threading.Barrier(3)
    release = threading.Event()

    def decode_scope():
        """同じキーのデコード区間に入り、両スレッドがそろうまで待つ。"""
        with handler._track_decode("same"):
            entered.wait(timeout=2)
            release.wait(timeout=2)

    threads = [threading.Thread(target=decode_scope) for _ in range(2)]
    try:
        for thread in threads:
            thread.start()
        entered.wait(timeout=2)
        release.set()
        for thread in threads:
            thread.join(timeout=2)
        assert handler.benchmark_metrics()["duplicate_decode_count"] == 1
    finally:
        release.set()
        handler.close()


def test_single_condition_runs_in_isolated_subprocess(tmp_path: Path):
    """サブプロセスの1条件でデータセット・ワーカー・メモリ・先読み・標本数・デコード量・RSS のどれかが欠ける。"""
    dataset = generate_datasets(
        tmp_path,
        page_count=2,
        folder_size=(16, 16),
        mixed_size=(16, 16),
        high_resolution_size=(24, 32),
    )[2]

    result = run_condition_subprocess(
        dataset,
        worker_count=2,
        memory_limit="512MB",
        prefetch_pages=15,
        warmups=0,
        repeats=1,
    )

    assert result["dataset"] == "high_resolution_zip"
    assert result["worker_count"] == 2
    assert result["memory_limit"] == "512MB"
    assert result["prefetch_pages"] == 15
    assert result["samples"] == 2
    assert result["decoded_total_bytes"] > 0
    assert "queue_depth_event_sample_p95" in result
    assert "rss_peak_bytes" in result


def test_cache_and_prefetch_batches_have_expected_conditions(tmp_path: Path):
    """キャッシュ候補が全データセットの2メモリ以外になり、先読みにフォルダが入るか zip の窓が欠ける。"""
    datasets = generate_datasets(
        tmp_path,
        page_count=64,
        folder_size=(8, 8),
        mixed_size=(8, 8),
        high_resolution_size=(8, 8),
    )

    cache = cache_candidate_conditions(datasets, seed=7)
    prefetch = prefetch_window_conditions(datasets, seed=7)

    assert len(cache) == 6
    assert {
        (dataset.name, memory) for dataset, memory in cache
    } == {
        (dataset.name, memory)
        for dataset in datasets
        for memory in ("256MB", "512MB")
    }
    assert len(prefetch) == 8
    assert {
        (dataset.name, pages) for dataset, pages in prefetch
    } == {
        (name, pages)
        for name in ("jpg_png_zip", "high_resolution_zip")
        for pages in (5, 10, 15, 20)
    }


def test_measurement_span_limits_64_page_source_to_20(tmp_path: Path):
    """64ページのソースで計測ページを20にしても、成功ページか遅延標本が20で止まらない。"""
    dataset = generate_datasets(
        tmp_path,
        page_count=64,
        folder_size=(8, 8),
        mixed_size=(8, 8),
        high_resolution_size=(8, 8),
    )[1]

    result = run_once(
        dataset,
        workers=2,
        memory_limit="512MB",
        prefetch_pages=5,
        measurement_pages=20,
        source_pages=64,
    )

    assert result.successful_pages == 20
    assert len(result.latencies_ms) == 20


def test_source_span_reset_does_not_count_setup_decode_as_redecode(
    tmp_path: Path,
):
    """ソース幅と計測幅が同じ20のとき、準備のデコードを再デコードに数える。"""
    dataset = generate_datasets(
        tmp_path,
        page_count=24,
        folder_size=(8, 8),
        mixed_size=(8, 8),
        high_resolution_size=(8, 8),
    )[0]

    result = run_once(
        dataset,
        workers=2,
        memory_limit="256MB",
        prefetch_pages=5,
        measurement_pages=20,
        source_pages=20,
    )

    assert result.successful_pages == 20
    assert result.redecode_count == 0


def test_scheduler_observer_records_state_change_queue_samples():
    """投入から世代破棄までのどれかの理由が、キューの状態変化から欠ける。"""
    loaded = threading.Event()
    scheduler = BenchmarkImageLoadScheduler(
        lambda _task: loaded.set() or True,
        lambda _session: True,
        worker_count=1,
    )
    try:
        assert scheduler.enqueue(
            file="page.jpg",
            cache_key="page",
            page_index=0,
            session_id=1,
            generation=0,
            priority=1,
        )
        assert loaded.wait(timeout=2)
        scheduler.advance_generation()
        reasons = [event["reason"] for event in scheduler.events()]
        assert "enqueue" in reasons
        assert "dequeue_claim" in reasons
        assert "worker_start" in reasons
        assert "worker_finish" in reasons
        assert "generation_cleanup" in reasons
    finally:
        scheduler.shutdown(wait=True)


def test_foreground_cold_jump_and_collision_are_deterministic(tmp_path: Path):
    """コールドジャンプの前提が外れ、衝突の待ちか再利用が1以外になるか重複デコードが出る。"""
    datasets = generate_datasets(
        tmp_path,
        page_count=8,
        folder_size=(16, 16),
        mixed_size=(16, 16),
        high_resolution_size=(24, 32),
    )
    cold = run_cold_jump_condition(
        datasets[1],
        repeats=1,
        jumps=(0, 4),
    )
    collision = run_collision_condition(
        datasets[2],
        repeats=1,
        target=4,
    )

    assert cold["samples"] == 2
    assert cold["owner_claim_count"] == 2
    assert all(
        sample["cold_precondition_verified"]
        for sample in cold["details"]
    )
    assert collision["wait_claim_count"] == 1
    assert collision["completion_reuse_count"] == 1
    assert collision["duplicate_decode_count"] == 0


def test_multi_handler_conditions_and_close_release_resources(tmp_path: Path):
    """複数ハンドラ条件が12件で重複し、close 後にキャッシュかワーカーが残る。"""
    conditions = multi_handler_conditions(seed=9)
    assert len(conditions) == 12
    assert len(set(conditions)) == 12

    dataset = generate_datasets(
        tmp_path,
        page_count=6,
        folder_size=(16, 16),
        mixed_size=(16, 16),
        high_resolution_size=(24, 32),
    )[0]
    result = run_multi_handler_condition(
        dataset,
        scenario="realistic",
        handler_count=2,
        memory_limit="256MB",
    )

    assert result["before_close"]["scheduler_workers"] == 8
    assert result["after_close"]["cache_bytes"] == 0
    assert result["after_close"]["resident_pages"] == 0
    assert result["after_close"]["alive_workers"] == 0
    assert result["release_verified"]


def test_policy_matrix_has_27_unique_conditions_in_seeded_order(tmp_path: Path):
    """同じ種の方針行列が順まで一致せず、27件が重複するかメモリか先読みの集合が欠ける。"""
    datasets = _stub_datasets(tmp_path)

    first = policy_matrix_conditions(datasets, seed=99)
    second = policy_matrix_conditions(datasets, seed=99)
    keys = [(dataset.name, memory, pages) for dataset, memory, pages in first]

    assert keys == [
        (dataset.name, memory, pages) for dataset, memory, pages in second
    ]
    assert len(keys) == 27
    assert len(set(keys)) == 27
    assert {memory for _name, memory, _pages in keys} == set(
        POLICY_MATRIX_MEMORY_LIMITS
    )
    assert {pages for _name, _memory, pages in keys} == set(
        POLICY_MATRIX_PREFETCH_PAGES
    )


def test_policy_matrix_covers_every_cache_and_prefetch_per_dataset(tmp_path: Path):
    """各データセットが、メモリと先読みの全組み合わせ9件を持たない。"""
    keys = [
        (dataset.name, memory, pages)
        for dataset, memory, pages in policy_matrix_conditions(
            _stub_datasets(tmp_path),
            seed=3,
        )
    ]

    for name in DATASET_NAMES:
        per_dataset = [
            (memory, pages)
            for dataset_name, memory, pages in keys
            if dataset_name == name
        ]
        assert len(per_dataset) == 9
        assert set(per_dataset) == {
            (memory, pages)
            for memory in POLICY_MATRIX_MEMORY_LIMITS
            for pages in POLICY_MATRIX_PREFETCH_PAGES
        }


def test_policy_matrix_report_fixes_condition_values_and_records_elapsed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """方針行列のワーカー・ソース・計測ページ・27条件が固定されず、経過時間が負になる。"""
    calls = []

    monkeypatch.setattr(
        benchmark,
        "generate_datasets",
        lambda root, *, page_count=20: _stub_datasets(tmp_path),
    )

    def fake_condition(dataset, **kwargs):
        """呼ばれた条件を記録し、データセット名だけの結果を返す。

        Args:
            dataset: 計測対象。
            **kwargs: サブプロセスへ渡す条件。

        Returns:
            データセット名だけを持つ結果。
        """
        calls.append(kwargs)
        return {"dataset": dataset.name}

    monkeypatch.setattr(benchmark, "run_condition_subprocess", fake_condition)

    report = run_policy_matrix(tmp_path, warmups=0, repeats=1, seed=5)
    conditions = report["conditions"]

    assert report["mode"] == "recommendation_policy_matrix"
    assert conditions["worker_count"] == POLICY_MATRIX_WORKER_COUNT
    assert conditions["source_pages"] == POLICY_MATRIX_SOURCE_PAGES
    assert conditions["measurement_pages"] == POLICY_MATRIX_MEASUREMENT_PAGES
    assert conditions["condition_count"] == 27
    assert len(conditions["condition_order"]) == 27
    assert "not wall-clock" in conditions["queue_sample_semantics"]
    assert len(calls) == 27
    assert {call["source_pages"] for call in calls} == {
        POLICY_MATRIX_SOURCE_PAGES
    }
    assert {call["measurement_pages"] for call in calls} == {
        POLICY_MATRIX_MEASUREMENT_PAGES
    }
    assert {call["worker_count"] for call in calls} == {
        POLICY_MATRIX_WORKER_COUNT
    }
    assert report["dataset_generation_seconds"] >= 0
    assert report["batch_elapsed_seconds"] >= 0
    assert all(
        result["condition_elapsed_seconds"] >= 0
        for result in report["results"]
    )


def test_policy_matrix_source_pages_ignore_pages_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """--pages 1 で方針行列の生成ページかソースページが定義値以外になり、既存モードが走る。"""
    generated = []

    def fake_generate(root, *, page_count=20):
        """生成に使ったページ数を記録し、実ファイルは作らない。

        Args:
            root: 生成先。使わない。
            page_count: 要求されたページ数。

        Returns:
            名前だけの Dataset。
        """
        generated.append(page_count)
        return _stub_datasets(tmp_path)

    calls = []

    def fake_condition(dataset, **kwargs):
        """呼ばれた条件を記録し、データセット名だけの結果を返す。

        Args:
            dataset: 計測対象。
            **kwargs: サブプロセスへ渡す条件。

        Returns:
            データセット名だけを持つ結果。
        """
        calls.append(kwargs)
        return {"dataset": dataset.name}

    monkeypatch.setattr(benchmark, "generate_datasets", fake_generate)
    monkeypatch.setattr(benchmark, "run_condition_subprocess", fake_condition)
    monkeypatch.setattr(
        benchmark,
        "run_benchmark",
        lambda *args, **kwargs: pytest.fail("existing mode must not run"),
    )

    assert benchmark.main(["--policy-matrix", "--pages", "1"]) == 0
    assert generated == [POLICY_MATRIX_SOURCE_PAGES]
    assert {call["source_pages"] for call in calls} == {
        POLICY_MATRIX_SOURCE_PAGES
    }


def test_existing_modes_keep_their_pages_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """既存の3モードが --pages 1 を受けず、性能バッチの生成ページが 64 以外になる。"""
    generated = []

    def fake_generate(root, *, page_count=20):
        """生成に使ったページ数を記録し、実ファイルは作らない。

        Args:
            root: 生成先。使わない。
            page_count: 要求されたページ数。

        Returns:
            名前だけの Dataset。
        """
        generated.append(page_count)
        return _stub_datasets(tmp_path)

    monkeypatch.setattr(benchmark, "generate_datasets", fake_generate)
    monkeypatch.setattr(
        benchmark,
        "run_benchmark",
        lambda *args, **kwargs: {"mode": "worker_benchmark"},
    )
    monkeypatch.setattr(
        benchmark,
        "run_matrix",
        lambda *args, **kwargs: {"mode": "worker_cache_matrix"},
    )
    monkeypatch.setattr(
        benchmark,
        "run_loader_experiment_batch",
        lambda *args, **kwargs: {"mode": "cache_prefetch_batch"},
    )

    assert benchmark.main(["--pages", "1"]) == 0
    assert benchmark.main(["--matrix", "--pages", "1"]) == 0
    assert benchmark.main(["--performance-batch", "--pages", "1"]) == 0

    assert generated == [1, 1, 64]


def test_policy_matrix_markdown_lists_dataset_cache_and_prefetch():
    """方針行列の Markdown からデータセット・メモリ・先読みの行、キューが壁時計でないこと、バッチ合計秒が消える。"""
    report = {
        "conditions": {
            "worker_count": 4,
            "source_pages": 64,
            "measurement_pages": 20,
            "warmups": 1,
            "measurement_runs": 5,
        },
        "dataset_generation_seconds": 12.5,
        "batch_elapsed_seconds": 300.25,
        "results": [
            {
                "dataset": "high_resolution_zip",
                "memory_limit": "1GB",
                "prefetch_pages": 5,
                "p50_latency_ms": 6.5,
                "p95_latency_ms": 15.25,
                "max_latency_ms": 41.5,
                "cache_hit_rate": 0.65,
                "prefetched_evicted_before_use": 0,
                "prefetched_evicted_before_use_bytes": 0,
                "redecode_count": 0,
                "queue_depth_max": 2,
                "queue_depth_event_sample_p95": 2.0,
                "decoded_average_bytes_per_page": 23040000.0,
                "decoded_max_bytes_per_page": 23040000,
                "rss_peak_bytes": 814903296,
                "condition_elapsed_seconds": 9.5,
            }
        ],
    }

    text = render_policy_matrix_markdown(report)

    assert "| high_resolution_zip | 1GB | 5 | 6.50 | 15.25 | 41.50 | 65.00% |" in text
    assert "not wall-clock time-weighted" in text
    assert "including subprocess" in text
    assert "batch total: 300.25 s" in text


def test_policy_matrix_condition_runs_in_isolated_subprocess(tmp_path: Path):
    """方針行列の1条件でページ数かワーカーが戻りと違い、重複デコードが出る。"""
    dataset = generate_datasets(
        tmp_path,
        page_count=6,
        folder_size=(16, 16),
        mixed_size=(16, 16),
        high_resolution_size=(24, 32),
    )[1]

    result = run_condition_subprocess(
        dataset,
        worker_count=POLICY_MATRIX_WORKER_COUNT,
        memory_limit="1GB",
        prefetch_pages=5,
        measurement_pages=4,
        source_pages=6,
        warmups=0,
        repeats=1,
    )

    assert result["worker_count"] == POLICY_MATRIX_WORKER_COUNT
    assert result["memory_limit"] == "1GB"
    assert result["prefetch_pages"] == 5
    assert result["source_pages"] == 6
    assert result["measurement_pages"] == 4
    assert result["samples"] == 4
    assert result["duplicate_decode_count"] == 0
    assert "queue_depth_event_sample_p95" in result
    assert "rss_peak_bytes" in result
