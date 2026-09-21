"""このPCで最適な画像読み込み設定を、本番経路で実測する。Qtへは依存しない。"""
from __future__ import annotations

import io
import logging
import math
import shutil
import statistics
import tempfile
import threading
import time
import zipfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageChops

from ez_co.handlers.file_handler import FileHandler
from ez_co.plugins.api import FileKind
from ez_co.plugins.manager import HandlerDecision
from ez_co.utils import system_resources
from ez_co.utils.language_manager import get_log_text
from ez_co.utils.image_loader_workers import (
    MAX_IMAGE_LOADER_WORKERS,
    MIN_IMAGE_LOADER_WORKERS,
)
from ez_co.utils.image_loading_recommendation import (
    LARGE_MEMORY_LIMIT,
    MEMORY_LIMIT_RAM_THRESHOLD_BYTES,
    RECOMMENDED_PREFETCH_PAGES,
    SAFE_MEMORY_LIMIT,
    auto_effective_workers,
    recommend_image_loading_settings,
)

logger = logging.getLogger(__name__)

STAGE_PREPARE = "prepare"
STAGE_WORKER = "worker"
STAGE_CACHE = "cache"

DATASET_SEED = 20260921
DATASET_PAGE_SIZE = (2400, 3200)
SOURCE_PAGES = 64
MEASUREMENT_PAGES = 20
WARMUP_RUNS = 1
MEASURED_RUNS = 3
STAGE_B_PREFETCH_PAGES = (5, 10)
IDLE_TIMEOUT_SECONDS = 30.0


class BenchmarkCancelled(Exception):
    """キャンセル要求で測定を打ち切った。途中値は返さない。"""


@dataclass(frozen=True)
class BenchmarkCondition:
    """1回の測定条件。"""

    stage: str
    worker_count: int
    memory_limit: str
    prefetch_pages: int


@dataclass(frozen=True)
class BenchmarkConditionResult:
    """1条件の測定値。RSSは条件ごとのbaselineからのdelta。"""

    stage: str
    worker_count: int
    memory_limit: str
    prefetch_pages: int
    average_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    duplicate_decode_count: int
    redecode_count: int
    prefetched_evicted_before_use: int
    cache_peak_bytes: int
    condition_rss_delta_bytes: int | None
    elapsed_seconds: float


@dataclass(frozen=True)
class BenchmarkReport:
    """測定全体の結果と、判定に必要な環境情報。"""

    results: list[BenchmarkConditionResult]
    stage_a_winner_workers: int
    auto_effective_workers: int
    logical_cpu_count: int | None
    physical_memory_bytes: int | None
    elapsed_seconds: float
    source_pages: int
    measurement_pages: int
    warmup_runs: int
    measured_runs: int
    batch_rss_delta_bytes: int | None = None
    stage_results: dict[str, list[BenchmarkConditionResult]] = field(
        default_factory=dict
    )

    def stage_a_results(self) -> list[BenchmarkConditionResult]:
        return [result for result in self.results if result.stage == STAGE_WORKER]

    def stage_b_results(self) -> list[BenchmarkConditionResult]:
        return [result for result in self.results if result.stage == STAGE_CACHE]


def stage_b_memory_limits(physical_memory_bytes: int | None) -> tuple[str, ...]:
    """RAMが小さい環境では512MB候補を測らない。1GBは常に測らない。"""
    if (
        physical_memory_bytes is not None
        and physical_memory_bytes >= MEMORY_LIMIT_RAM_THRESHOLD_BYTES
    ):
        return (SAFE_MEMORY_LIMIT, LARGE_MEMORY_LIMIT)
    return (SAFE_MEMORY_LIMIT,)


def stage_a_conditions(
    logical_cpu_count: int | None,
    physical_memory_bytes: int | None,
) -> list[BenchmarkCondition]:
    """auto実効値を中心にworkerを振る。現在のConfigの手動値は中心にしない。"""
    center = auto_effective_workers(logical_cpu_count)
    recommendation = recommend_image_loading_settings(
        logical_cpu_count,
        physical_memory_bytes,
    )
    candidates = []
    for worker_count in (center - 1, center, center + 1):
        clipped = min(
            MAX_IMAGE_LOADER_WORKERS,
            max(MIN_IMAGE_LOADER_WORKERS, worker_count),
        )
        if clipped not in candidates:
            candidates.append(clipped)
    return [
        BenchmarkCondition(
            stage=STAGE_WORKER,
            worker_count=worker_count,
            memory_limit=recommendation.memory_limit,
            prefetch_pages=RECOMMENDED_PREFETCH_PAGES,
        )
        for worker_count in sorted(candidates)
    ]


def stage_b_conditions(
    worker_count: int,
    physical_memory_bytes: int | None,
) -> list[BenchmarkCondition]:
    """Stage A勝者workerで、cache上限と先読み窓の組み合わせを測る。"""
    return [
        BenchmarkCondition(
            stage=STAGE_CACHE,
            worker_count=worker_count,
            memory_limit=memory_limit,
            prefetch_pages=prefetch_pages,
        )
        for memory_limit in stage_b_memory_limits(physical_memory_bytes)
        for prefetch_pages in STAGE_B_PREFETCH_PAGES
    ]


def condition_total(physical_memory_bytes: int | None, logical_cpu_count: int | None) -> int:
    """進捗表示のために、開始前に総条件数を数える。"""
    stage_a = stage_a_conditions(logical_cpu_count, physical_memory_bytes)
    memory_limits = stage_b_memory_limits(physical_memory_bytes)
    return len(stage_a) + len(memory_limits) * len(STAGE_B_PREFETCH_PAGES)


class _BenchmarkConfig:
    """実Configを触らずに、cache条件だけを差し替えたスナップショット。"""

    def __init__(self, memory_limit: str, prefetch_pages: int):
        self.cache = {
            "memory_limit": memory_limit,
            "prefetch_pages": prefetch_pages,
            "optimize_large_images": False,
        }
        self.debug = {
            "enabled": False,
            "keep_archive_handles": False,
            "cache_archive_metadata": True,
        }
        self.archive = {"enabled": True}


class _BenchmarkFileHandler(FileHandler):
    """本番の読み込み経路のまま、worker数固定と計測counterだけを足す。"""

    def __init__(self, config, worker_count: int):
        self._benchmark_worker_count = int(worker_count)
        self._benchmark_lock = threading.Lock()
        self._benchmark_cache_peak = 0
        self._benchmark_puts: Counter[str] = Counter()
        self._benchmark_active_decodes: Counter[str] = Counter()
        self._benchmark_duplicate_decodes = 0
        self._benchmark_decode_context = threading.local()
        super().__init__(config)

    def _start_workers(self):
        from ez_co.handlers.image_load_scheduler import ImageLoadScheduler

        self._scheduler = ImageLoadScheduler(
            self._load_scheduled_task,
            self._is_session_active,
            worker_count=self._benchmark_worker_count,
        )

    def _resolve_handler(self, file_path):
        # benchmark素材は自前のZIPなので、プラグイン解決を通さない
        kind = (
            FileKind.ARCHIVE
            if Path(file_path).suffix.lower() == ".zip"
            else FileKind.IMAGE
        )
        return HandlerDecision("builtin", kind)

    def reset_benchmark_metrics(self):
        with self._benchmark_lock:
            self._benchmark_cache_peak = 0
            self._benchmark_puts.clear()
            self._benchmark_active_decodes.clear()
            self._benchmark_duplicate_decodes = 0
        self._prefetched_evicted_before_use = 0

    def _cache_put_if_session_active(
        self,
        cache_key,
        image,
        estimated_size,
        session_id,
        *,
        prefetched,
    ):
        stored = super()._cache_put_if_session_active(
            cache_key,
            image,
            estimated_size,
            session_id,
            prefetched=prefetched,
        )
        if stored:
            with self._benchmark_lock:
                self._benchmark_puts[cache_key] += 1
                self._benchmark_cache_peak = max(
                    self._benchmark_cache_peak,
                    self.cache_size,
                )
        return stored

    def _with_decode_key(self, cache_key, callback, *args, **kwargs):
        previous = getattr(self._benchmark_decode_context, "cache_key", None)
        self._benchmark_decode_context.cache_key = cache_key
        try:
            return callback(*args, **kwargs)
        finally:
            self._benchmark_decode_context.cache_key = previous

    def _get_image_from_archive_sync(self, file):
        return self._with_decode_key(
            self._cache_key_for_file(file),
            super()._get_image_from_archive_sync,
            file,
        )

    def _get_image_from_archive(self, file, session_id=None):
        return self._with_decode_key(
            self._cache_key_for_file(file),
            super()._get_image_from_archive,
            file,
            session_id,
        )

    @contextmanager
    def _track_decode(self, cache_key):
        with self._benchmark_lock:
            if self._benchmark_active_decodes[cache_key]:
                self._benchmark_duplicate_decodes += 1
            self._benchmark_active_decodes[cache_key] += 1
        try:
            yield
        finally:
            with self._benchmark_lock:
                self._benchmark_active_decodes[cache_key] -= 1
                if not self._benchmark_active_decodes[cache_key]:
                    self._benchmark_active_decodes.pop(cache_key, None)

    def _decode_image(self, source):
        cache_key = getattr(self._benchmark_decode_context, "cache_key", None)
        if cache_key is None and isinstance(source, (str, Path)):
            cache_key = self._cache_key_for_file(source)
        if cache_key is None:
            return super()._decode_image(source)
        with self._track_decode(cache_key):
            return super()._decode_image(source)

    def benchmark_metrics(self) -> dict[str, int]:
        with self._benchmark_lock:
            return {
                "cache_peak_bytes": self._benchmark_cache_peak,
                "duplicate_decode_count": self._benchmark_duplicate_decodes,
                "redecode_count": sum(
                    max(0, count - 1) for count in self._benchmark_puts.values()
                ),
                "prefetched_evicted_before_use": (
                    self._prefetched_evicted_before_use
                ),
            }


def _pattern_image(size: tuple[int, int], variant: int) -> Image.Image:
    gradient = Image.linear_gradient("L").resize(size)
    green = ImageChops.offset(gradient, variant * 37, variant * 53)
    blue = ImageChops.offset(gradient, variant * 71, variant * 29)
    return Image.merge("RGB", (gradient, green, blue))


def _encoded_page(size: tuple[int, int], variant: int) -> bytes:
    image = _pattern_image(size, variant)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=88)
    image.close()
    return output.getvalue()


def generate_dataset(
    root: Path,
    *,
    page_count: int = SOURCE_PAGES,
    page_size: tuple[int, int] = DATASET_PAGE_SIZE,
    seed: int = DATASET_SEED,
) -> Path:
    """高解像度ZIP相当の素材を、固定seedで作る。"""
    root.mkdir(parents=True, exist_ok=True)
    archive_path = root / "benchmark-high-resolution.zip"
    variant_offset = seed % 211
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED) as archive:
        for index in range(page_count):
            archive.writestr(
                f"{index:03d}.jpg",
                _encoded_page(page_size, index + variant_offset),
            )
    return archive_path


def _percentile(values, percent: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percent
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _check_cancelled(cancel_event) -> None:
    if cancel_event is not None and cancel_event.is_set():
        raise BenchmarkCancelled()


def _wait_for_idle(handler, timeout: float = IDLE_TIMEOUT_SECONDS) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = handler._scheduler.snapshot()
        if snapshot["queue_size"] == 0 and snapshot["active_workers"] == 0:
            return
        time.sleep(0.01)
    raise TimeoutError("image loader workers did not become idle")


def _run_pages(
    handler,
    page_count: int,
    cancel_event,
    resident_samples: list[int],
) -> list[float]:
    latencies = []
    for index in range(page_count):
        _check_cancelled(cancel_event)
        started = time.perf_counter()
        if index == 0:
            image = handler.get_current_image()
            succeeded = image is not None
        else:
            moved = handler.next_file()
            image = handler.get_current_image() if moved else None
            succeeded = moved and image is not None
        latencies.append((time.perf_counter() - started) * 1000)
        if not succeeded:
            raise RuntimeError(f"benchmark page {index} could not be loaded")
        resident = system_resources.process_resident_bytes()
        if resident is not None:
            resident_samples.append(resident)
    return latencies


def _run_single(
    condition: BenchmarkCondition,
    dataset_path: Path,
    *,
    source_pages: int,
    measurement_pages: int,
    cancel_event,
    resident_samples: list[int],
) -> tuple[list[float], dict[str, int]]:
    handler = _BenchmarkFileHandler(
        _BenchmarkConfig(condition.memory_limit, condition.prefetch_pages),
        condition.worker_count,
    )
    try:
        if not handler.open_files([dataset_path]):
            raise RuntimeError(f"failed to open benchmark dataset: {dataset_path}")
        if source_pages is not None and source_pages < handler.get_total_pages():
            handler.stop_all_loading()
            _wait_for_idle(handler)
            handler.reset_benchmark_metrics()
            handler.current_files = handler.current_files[: max(1, int(source_pages))]
            handler.current_index = 0
            handler._prefetch_around(0)
        page_count = min(handler.get_total_pages(), max(1, int(measurement_pages)))
        latencies = _run_pages(handler, page_count, cancel_event, resident_samples)
        _wait_for_idle(handler)
        return latencies, handler.benchmark_metrics()
    finally:
        handler.close()


def measure_condition(
    condition: BenchmarkCondition,
    dataset_path: Path,
    *,
    source_pages: int = SOURCE_PAGES,
    measurement_pages: int = MEASUREMENT_PAGES,
    warmup_runs: int = WARMUP_RUNS,
    measured_runs: int = MEASURED_RUNS,
    cancel_event=None,
) -> BenchmarkConditionResult:
    """1条件を測る。RSSのbaselineはこの条件の開始直前に取り直す。"""
    baseline_resident = system_resources.process_resident_bytes()
    resident_samples = []
    started = time.perf_counter()
    latencies = []
    duplicate_decodes = 0
    redecodes = 0
    evicted_before_use = 0
    cache_peak = 0
    for run_index in range(warmup_runs + measured_runs):
        _check_cancelled(cancel_event)
        run_latencies, metrics = _run_single(
            condition,
            dataset_path,
            source_pages=source_pages,
            measurement_pages=measurement_pages,
            cancel_event=cancel_event,
            resident_samples=resident_samples,
        )
        if run_index < warmup_runs:
            continue
        latencies.extend(run_latencies)
        duplicate_decodes += metrics["duplicate_decode_count"]
        redecodes += metrics["redecode_count"]
        evicted_before_use += metrics["prefetched_evicted_before_use"]
        cache_peak = max(cache_peak, metrics["cache_peak_bytes"])
    if baseline_resident is None or not resident_samples:
        rss_delta = None
    else:
        rss_delta = max(0, max(resident_samples) - baseline_resident)
    return BenchmarkConditionResult(
        stage=condition.stage,
        worker_count=condition.worker_count,
        memory_limit=condition.memory_limit,
        prefetch_pages=condition.prefetch_pages,
        average_latency_ms=statistics.fmean(latencies) if latencies else 0.0,
        p50_latency_ms=_percentile(latencies, 0.50),
        p95_latency_ms=_percentile(latencies, 0.95),
        max_latency_ms=max(latencies, default=0.0),
        duplicate_decode_count=duplicate_decodes,
        redecode_count=redecodes,
        prefetched_evicted_before_use=evicted_before_use,
        cache_peak_bytes=cache_peak,
        condition_rss_delta_bytes=rss_delta,
        elapsed_seconds=time.perf_counter() - started,
    )


def _notify(progress, stage, stage_index, stage_total, overall_index, overall_total):
    if progress is None:
        return
    progress(stage, stage_index, stage_total, overall_index, overall_total)


def run_image_loading_benchmark(
    *,
    progress=None,
    cancel_event=None,
    logical_cpu_count: int | None = None,
    physical_memory_bytes: int | None = None,
    dataset_factory=None,
    source_pages: int = SOURCE_PAGES,
    measurement_pages: int = MEASUREMENT_PAGES,
    warmup_runs: int = WARMUP_RUNS,
    measured_runs: int = MEASURED_RUNS,
) -> BenchmarkReport:
    """Stage A（worker）→ Stage B（cache・先読み）を測る。素材と後片付けはここが持つ。"""
    from ez_co.services.image_loading_benchmark_evaluator import select_stage_a_winner

    if logical_cpu_count is None:
        logical_cpu_count = system_resources.logical_cpu_count()
    if physical_memory_bytes is None:
        physical_memory_bytes = system_resources.physical_memory_bytes()
    stage_a = stage_a_conditions(logical_cpu_count, physical_memory_bytes)
    overall_total = condition_total(physical_memory_bytes, logical_cpu_count)
    logger.info(get_log_text("image_loading_benchmark_started", total=overall_total))
    batch_baseline = system_resources.process_resident_bytes()
    batch_peak_samples = []
    started = time.perf_counter()
    temp_root = Path(tempfile.mkdtemp(prefix="ezco-image-benchmark-"))
    results: list[BenchmarkConditionResult] = []
    try:
        _check_cancelled(cancel_event)
        _notify(progress, STAGE_PREPARE, 1, 1, 0, overall_total)
        factory = dataset_factory or generate_dataset
        dataset_path = Path(factory(temp_root))
        overall_index = 0
        for stage_index, condition in enumerate(stage_a, start=1):
            _check_cancelled(cancel_event)
            overall_index += 1
            _notify(
                progress,
                STAGE_WORKER,
                stage_index,
                len(stage_a),
                overall_index,
                overall_total,
            )
            results.append(
                measure_condition(
                    condition,
                    dataset_path,
                    source_pages=source_pages,
                    measurement_pages=measurement_pages,
                    warmup_runs=warmup_runs,
                    measured_runs=measured_runs,
                    cancel_event=cancel_event,
                )
            )
        winner_workers = select_stage_a_winner(
            [result for result in results if result.stage == STAGE_WORKER]
        )
        stage_b = stage_b_conditions(winner_workers, physical_memory_bytes)
        for stage_index, condition in enumerate(stage_b, start=1):
            _check_cancelled(cancel_event)
            overall_index += 1
            _notify(
                progress,
                STAGE_CACHE,
                stage_index,
                len(stage_b),
                overall_index,
                overall_total,
            )
            results.append(
                measure_condition(
                    condition,
                    dataset_path,
                    source_pages=source_pages,
                    measurement_pages=measurement_pages,
                    warmup_runs=warmup_runs,
                    measured_runs=measured_runs,
                    cancel_event=cancel_event,
                )
            )
        elapsed = time.perf_counter() - started
        resident_end = system_resources.process_resident_bytes()
        if resident_end is not None:
            batch_peak_samples.append(resident_end)
        if batch_baseline is None or not batch_peak_samples:
            batch_delta = None
        else:
            batch_delta = max(0, max(batch_peak_samples) - batch_baseline)
        logger.info(
            get_log_text(
                "image_loading_benchmark_completed",
                conditions=len(results),
                elapsed=elapsed,
            )
        )
        return BenchmarkReport(
            results=results,
            stage_a_winner_workers=winner_workers,
            auto_effective_workers=auto_effective_workers(logical_cpu_count),
            logical_cpu_count=logical_cpu_count,
            physical_memory_bytes=physical_memory_bytes,
            elapsed_seconds=elapsed,
            source_pages=source_pages,
            measurement_pages=measurement_pages,
            warmup_runs=warmup_runs,
            measured_runs=measured_runs,
            batch_rss_delta_bytes=batch_delta,
            stage_results={
                STAGE_WORKER: [
                    result for result in results if result.stage == STAGE_WORKER
                ],
                STAGE_CACHE: [
                    result for result in results if result.stage == STAGE_CACHE
                ],
            },
        )
    except BenchmarkCancelled:
        logger.info(
            get_log_text(
                "image_loading_benchmark_cancelled",
                completed=len(results),
                total=overall_total,
            )
        )
        raise
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
