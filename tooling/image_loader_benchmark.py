"""画像読込worker数を生成素材で比較する再現可能なbenchmark。"""
from __future__ import annotations

import argparse
import ctypes
import io
import json
import logging
import math
import os
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from PIL import Image, ImageChops
import PIL

from ez_co.handlers.file_handler import FileHandler
from ez_co.handlers.image_load_scheduler import ImageLoadScheduler
from ez_co.plugins.api import FileKind
from ez_co.plugins.manager import HandlerDecision


DEFAULT_WORKERS = tuple(range(1, 9))
MATRIX_MEMORY_LIMITS = ("256MB", "512MB", "1GB")
DEFAULT_SEED = 20260921
# policy matrix専用。CLIの--pagesへは依存させない。
POLICY_MATRIX_MEMORY_LIMITS = ("256MB", "512MB", "1GB")
POLICY_MATRIX_PREFETCH_PAGES = (5, 10, 15)
POLICY_MATRIX_WORKER_COUNT = 4
POLICY_MATRIX_SOURCE_PAGES = 64
POLICY_MATRIX_MEASUREMENT_PAGES = 20
DATASET_DIMENSIONS = {
    "jpg_folder": (1600, 1200),
    "jpg_png_zip": (1600, 1200),
    "high_resolution_zip": (2400, 3200),
}


@dataclass(frozen=True)
class Dataset:
    name: str
    path: Path


@dataclass
class RunResult:
    dataset: str
    worker_count: int
    memory_limit: str
    prefetch_pages: int
    latencies_ms: list[float]
    wall_seconds: float
    cpu_seconds: float
    successful_pages: int
    cache_hits: int
    cache_misses: int
    cache_peak_bytes: int
    prefetched_evicted_before_use: int
    prefetched_evicted_before_use_bytes: int
    prefetched_image_count: int
    prefetched_image_bytes: int
    duplicate_decode_count: int
    redecode_count: int
    decoded_total_bytes: int
    decoded_average_bytes_per_page: float
    decoded_max_bytes_per_page: int
    queue_depth_samples: list[int] = field(default_factory=list)
    active_worker_samples: list[int] = field(default_factory=list)
    rss_bytes: int | None = None


class BenchmarkImageLoadScheduler(ImageLoadScheduler):
    """状態変化eventごとのqueue/worker snapshotをtooling内だけで記録する。"""

    def __init__(self, load_task, is_session_active, *, worker_count):
        self._benchmark_event_lock = threading.Lock()
        self._benchmark_events = []

        def observed_load(task):
            self._record_event("worker_start")
            return load_task(task)

        super().__init__(
            observed_load,
            is_session_active,
            worker_count=worker_count,
        )

    def _record_event(self, reason):
        snapshot = self.snapshot()
        snapshot["reason"] = reason
        with self._benchmark_event_lock:
            self._benchmark_events.append(snapshot)

    def events(self):
        with self._benchmark_event_lock:
            return [dict(event) for event in self._benchmark_events]

    def reset_events(self):
        with self._benchmark_event_lock:
            self._benchmark_events.clear()

    def cache_key_state(self, cache_key):
        with self._lock:
            state = self._states.get(cache_key)
            return state.state if state is not None else None

    def advance_generation(self):
        generation = super().advance_generation()
        self._record_event("generation_cleanup")
        return generation

    def enqueue(self, **kwargs):
        queued = super().enqueue(**kwargs)
        self._record_event("enqueue" if queued else "enqueue_skipped")
        return queued

    def claim_foreground(self, cache_key, session_id):
        result = super().claim_foreground(cache_key, session_id)
        self._record_event(f"foreground_{result[0]}")
        return result

    def _claim_background(self, task):
        state = super()._claim_background(task)
        self._record_event("dequeue_claim" if state is not None else "stale_discard")
        return state

    def _finish_background(self, task, claimed_state, success):
        super()._finish_background(task, claimed_state, success)
        self._record_event("worker_finish")

    def cancel_pending(self):
        super().cancel_pending()
        self._record_event("cancel_pending")


class BenchmarkFileHandler(FileHandler):
    """本番経路を使い、worker数とbenchmark用counterだけを差し替える。"""

    def __init__(self, config, worker_count: int):
        self._benchmark_worker_count = int(worker_count)
        self._benchmark_lock = threading.Lock()
        self._benchmark_cache_hits = 0
        self._benchmark_cache_misses = 0
        self._benchmark_cache_peak = 0
        self._benchmark_puts: Counter[str] = Counter()
        self._benchmark_prefetched_count = 0
        self._benchmark_prefetched_bytes = 0
        self._benchmark_evicted_before_use_bytes = 0
        self._benchmark_decoded_sizes: dict[str, int] = {}
        self._benchmark_active_decodes: Counter[str] = Counter()
        self._benchmark_duplicate_decodes = 0
        self._benchmark_decode_context = threading.local()
        super().__init__(config)

    def _start_workers(self):
        self._scheduler = BenchmarkImageLoadScheduler(
            self._load_scheduled_task,
            self._is_session_active,
            worker_count=self._benchmark_worker_count,
        )

    def scheduler_events(self):
        return self._scheduler.events()

    def reset_benchmark_metrics(self):
        with self._benchmark_lock:
            self._benchmark_cache_hits = 0
            self._benchmark_cache_misses = 0
            self._benchmark_cache_peak = 0
            self._benchmark_puts.clear()
            self._benchmark_prefetched_count = 0
            self._benchmark_prefetched_bytes = 0
            self._benchmark_evicted_before_use_bytes = 0
            self._benchmark_decoded_sizes.clear()
            self._benchmark_active_decodes.clear()
            self._benchmark_duplicate_decodes = 0
        self._prefetched_evicted_before_use = 0
        self._scheduler.reset_events()

    def _resolve_handler(self, file_path):
        kind = FileKind.ARCHIVE if Path(file_path).suffix.lower() == ".zip" else FileKind.IMAGE
        return HandlerDecision("builtin", kind)

    def get_image_at(self, index: int):
        cache_hit = False
        if 0 <= index < len(self.current_files):
            cache_key = self._cache_key_for_file(self.current_files[index])
            with self._cache_lock:
                cache_hit = cache_key in self.image_cache
        with self._benchmark_lock:
            if cache_hit:
                self._benchmark_cache_hits += 1
            else:
                self._benchmark_cache_misses += 1
        return super().get_image_at(index)

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
                self._benchmark_decoded_sizes.setdefault(
                    cache_key,
                    int(estimated_size),
                )
                if prefetched:
                    self._benchmark_prefetched_count += 1
                    self._benchmark_prefetched_bytes += int(estimated_size)
                self._benchmark_cache_peak = max(
                    self._benchmark_cache_peak,
                    self.cache_size,
                )
        return stored

    def _evict_cache_unlocked(self):
        before = {
            cache_key: self._estimate_image_size(self.image_cache[cache_key])
            for cache_key, usage in self._cache_usage.items()
            if cache_key in self.image_cache
            and usage.get("prefetched")
            and not usage.get("used")
        }
        super()._evict_cache_unlocked()
        removed = set(before) - set(self.image_cache)
        if removed:
            with self._benchmark_lock:
                self._benchmark_evicted_before_use_bytes += sum(
                    before[cache_key] for cache_key in removed
                )

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

    def benchmark_metrics(self) -> dict[str, int | float]:
        with self._benchmark_lock:
            decoded_sizes = list(self._benchmark_decoded_sizes.values())
            return {
                "cache_hits": self._benchmark_cache_hits,
                "cache_misses": self._benchmark_cache_misses,
                "cache_peak_bytes": self._benchmark_cache_peak,
                "prefetched_image_count": self._benchmark_prefetched_count,
                "prefetched_image_bytes": self._benchmark_prefetched_bytes,
                "prefetched_evicted_before_use_bytes": (
                    self._benchmark_evicted_before_use_bytes
                ),
                "duplicate_decode_count": self._benchmark_duplicate_decodes,
                "redecode_count": sum(
                    max(0, count - 1) for count in self._benchmark_puts.values()
                ),
                "decoded_total_bytes": sum(decoded_sizes),
                "decoded_average_bytes_per_page": (
                    statistics.fmean(decoded_sizes) if decoded_sizes else 0.0
                ),
                "decoded_max_bytes_per_page": max(decoded_sizes, default=0),
            }


class ForegroundBenchmarkFileHandler(BenchmarkFileHandler):
    """foreground claimと性能値を文字列logにせず直接収集する。"""

    def __init__(self, config, worker_count):
        self._foreground_performance = []
        self._blocked_decode_key = None
        self._blocked_decode_started = threading.Event()
        self._blocked_decode_release = threading.Event()
        super().__init__(config, worker_count)

    def _performance_logging_enabled(self):
        return True

    def _log_load_performance(self, **values):
        with self._benchmark_lock:
            self._foreground_performance.append(dict(values))

    def performance_samples(self):
        with self._benchmark_lock:
            return [dict(sample) for sample in self._foreground_performance]

    def block_background_decode(self, cache_key):
        self._blocked_decode_key = cache_key
        self._blocked_decode_started.clear()
        self._blocked_decode_release.clear()

    def release_background_decode(self):
        self._blocked_decode_release.set()

    def _decode_image(self, source):
        cache_key = getattr(self._benchmark_decode_context, "cache_key", None)
        if (
            cache_key == self._blocked_decode_key
            and threading.current_thread().name.startswith("EzCoImageLoader-")
        ):
            self._blocked_decode_started.set()
            if not self._blocked_decode_release.wait(timeout=30):
                raise TimeoutError("blocked benchmark decode was not released")
        return super()._decode_image(source)


def _pattern_image(size: tuple[int, int], variant: int) -> Image.Image:
    gradient = Image.linear_gradient("L").resize(size)
    green = ImageChops.offset(gradient, variant * 37, variant * 53)
    blue = ImageChops.offset(gradient, variant * 71, variant * 29)
    return Image.merge("RGB", (gradient, green, blue))


def _encoded_image(
    size: tuple[int, int],
    variant: int,
    image_format: str,
) -> bytes:
    image = _pattern_image(size, variant)
    output = io.BytesIO()
    options = {"quality": 88} if image_format == "JPEG" else {"compress_level": 6}
    image.save(output, format=image_format, **options)
    image.close()
    return output.getvalue()


def generate_datasets(
    root: Path,
    *,
    page_count: int = 20,
    folder_size: tuple[int, int] = (1600, 1200),
    mixed_size: tuple[int, int] = (1600, 1200),
    high_resolution_size: tuple[int, int] = (2400, 3200),
) -> list[Dataset]:
    folder = root / "jpg-folder"
    folder.mkdir(parents=True, exist_ok=True)
    for index in range(page_count):
        data = _encoded_image(folder_size, index, "JPEG")
        (folder / f"{index:03d}.jpg").write_bytes(data)

    mixed_zip = root / "jpg-png.zip"
    with zipfile.ZipFile(mixed_zip, "w", compression=zipfile.ZIP_STORED) as archive:
        for index in range(page_count):
            image_format = "JPEG" if index % 2 == 0 else "PNG"
            suffix = "jpg" if image_format == "JPEG" else "png"
            archive.writestr(
                f"{index:03d}.{suffix}",
                _encoded_image(mixed_size, index + 100, image_format),
            )

    high_zip = root / "high-resolution.zip"
    with zipfile.ZipFile(high_zip, "w", compression=zipfile.ZIP_STORED) as archive:
        for index in range(page_count):
            archive.writestr(
                f"{index:03d}.jpg",
                _encoded_image(high_resolution_size, index + 200, "JPEG"),
            )

    return [
        Dataset("jpg_folder", folder),
        Dataset("jpg_png_zip", mixed_zip),
        Dataset("high_resolution_zip", high_zip),
    ]


def worker_order(seed: int = DEFAULT_SEED) -> list[int]:
    workers = list(DEFAULT_WORKERS)
    random.Random(seed).shuffle(workers)
    return workers


def percentile(values: Iterable[float], percent: float) -> float:
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


def _process_memory_bytes() -> tuple[int | None, int | None]:
    if sys.platform != "win32":
        return None, None
    try:
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        get_process_memory_info.restype = ctypes.c_bool
        process = get_current_process()
        success = get_process_memory_info(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        if not success:
            return None, None
        return int(counters.WorkingSetSize), int(counters.PeakWorkingSetSize)
    except (AttributeError, OSError):
        return None, None


def _rss_bytes() -> int | None:
    return _process_memory_bytes()[0]


def _benchmark_config(memory_limit: str = "256MB", prefetch_pages: int = 15):
    return SimpleNamespace(
        cache={
            "memory_limit": memory_limit,
            "prefetch_pages": prefetch_pages,
            "optimize_large_images": False,
        },
        debug={
            "enabled": False,
            "keep_archive_handles": False,
            "cache_archive_metadata": True,
        },
        archive={"enabled": True},
    )


def _wait_for_idle(handler: BenchmarkFileHandler, timeout: float = 30.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = handler._scheduler.snapshot()
        if snapshot["queue_size"] == 0 and snapshot["active_workers"] == 0:
            return
        time.sleep(0.01)
    raise TimeoutError("image loader workers did not become idle")


def run_once(
    dataset: Dataset,
    workers: int,
    *,
    memory_limit: str = "256MB",
    prefetch_pages: int = 15,
    measurement_pages: int | None = None,
    source_pages: int | None = None,
) -> RunResult:
    handler = BenchmarkFileHandler(
        _benchmark_config(memory_limit, prefetch_pages),
        workers,
    )
    latencies = []
    successful_pages = 0
    wall_started = time.perf_counter()
    cpu_started = time.process_time()
    try:
        if not handler.open_files([dataset.path]):
            raise RuntimeError(f"failed to open benchmark dataset: {dataset.path}")
        if (
            source_pages is not None
            and source_pages < handler.get_total_pages()
        ):
            handler.stop_all_loading()
            _wait_for_idle(handler)
            handler.reset_benchmark_metrics()
            handler.current_files = handler.current_files[
                : max(1, int(source_pages))
            ]
            handler.current_index = 0
            handler._prefetch_around(0)
        page_count = handler.get_total_pages()
        if measurement_pages is not None:
            page_count = min(page_count, max(1, int(measurement_pages)))
        for index in range(page_count):
            started = time.perf_counter()
            if index == 0:
                image = handler.get_current_image()
                succeeded = image is not None
            else:
                moved = handler.next_file()
                image = handler.get_current_image() if moved else None
                succeeded = moved and image is not None
            latencies.append((time.perf_counter() - started) * 1000)
            successful_pages += int(succeeded)
        _wait_for_idle(handler)
        metrics = handler.benchmark_metrics()
        scheduler_events = handler.scheduler_events()
        return RunResult(
            dataset=dataset.name,
            worker_count=workers,
            memory_limit=memory_limit,
            prefetch_pages=prefetch_pages,
            latencies_ms=latencies,
            wall_seconds=time.perf_counter() - wall_started,
            cpu_seconds=time.process_time() - cpu_started,
            successful_pages=successful_pages,
            cache_hits=metrics["cache_hits"],
            cache_misses=metrics["cache_misses"],
            cache_peak_bytes=metrics["cache_peak_bytes"],
            prefetched_evicted_before_use=handler._prefetched_evicted_before_use,
            prefetched_evicted_before_use_bytes=metrics[
                "prefetched_evicted_before_use_bytes"
            ],
            prefetched_image_count=metrics["prefetched_image_count"],
            prefetched_image_bytes=metrics["prefetched_image_bytes"],
            duplicate_decode_count=metrics["duplicate_decode_count"],
            redecode_count=metrics["redecode_count"],
            decoded_total_bytes=metrics["decoded_total_bytes"],
            decoded_average_bytes_per_page=metrics[
                "decoded_average_bytes_per_page"
            ],
            decoded_max_bytes_per_page=metrics["decoded_max_bytes_per_page"],
            queue_depth_samples=[
                event["queue_size"] for event in scheduler_events
            ],
            active_worker_samples=[
                event["active_workers"] for event in scheduler_events
            ],
            rss_bytes=_rss_bytes(),
        )
    finally:
        handler.close()


def aggregate_results(
    results: list[RunResult],
    *,
    rss_start_bytes: int | None = None,
    rss_end_bytes: int | None = None,
    rss_peak_bytes: int | None = None,
) -> dict:
    latencies = [
        latency
        for result in results
        for latency in result.latencies_ms
    ]
    wall_seconds = sum(result.wall_seconds for result in results)
    cpu_seconds = sum(result.cpu_seconds for result in results)
    pages = sum(result.successful_pages for result in results)
    rss_values = [result.rss_bytes for result in results if result.rss_bytes is not None]
    cache_hits = sum(result.cache_hits for result in results)
    cache_misses = sum(result.cache_misses for result in results)
    queue_depth_samples = [
        sample
        for result in results
        for sample in result.queue_depth_samples
    ]
    active_worker_samples = [
        sample
        for result in results
        for sample in result.active_worker_samples
    ]
    return {
        "dataset": results[0].dataset,
        "worker_count": results[0].worker_count,
        "memory_limit": results[0].memory_limit,
        "prefetch_pages": results[0].prefetch_pages,
        "runs": len(results),
        "samples": len(latencies),
        "average_latency_ms": statistics.fmean(latencies) if latencies else 0.0,
        "p50_latency_ms": percentile(latencies, 0.50),
        "p95_latency_ms": percentile(latencies, 0.95),
        "max_latency_ms": max(latencies, default=0.0),
        "decode_throughput_pages_per_second": pages / wall_seconds if wall_seconds else 0.0,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
        "cache_hit_rate": (
            cache_hits / (cache_hits + cache_misses)
            if cache_hits + cache_misses
            else 0.0
        ),
        "duplicate_decode_count": sum(
            result.duplicate_decode_count for result in results
        ),
        "redecode_count": sum(result.redecode_count for result in results),
        "prefetched_evicted_before_use": sum(
            result.prefetched_evicted_before_use for result in results
        ),
        "prefetched_evicted_before_use_bytes": sum(
            result.prefetched_evicted_before_use_bytes for result in results
        ),
        "prefetched_image_count": sum(
            result.prefetched_image_count for result in results
        ),
        "prefetched_image_bytes": sum(
            result.prefetched_image_bytes for result in results
        ),
        "cache_peak_bytes": max(
            (result.cache_peak_bytes for result in results),
            default=0,
        ),
        "decoded_total_bytes": max(
            (result.decoded_total_bytes for result in results),
            default=0,
        ),
        "decoded_average_bytes_per_page": max(
            (result.decoded_average_bytes_per_page for result in results),
            default=0.0,
        ),
        "decoded_max_bytes_per_page": max(
            (result.decoded_max_bytes_per_page for result in results),
            default=0,
        ),
        "queue_depth_max": max(queue_depth_samples, default=0),
        "queue_depth_event_sample_p95": percentile(
            queue_depth_samples,
            0.95,
        ),
        "active_workers_max": max(active_worker_samples, default=0),
        "queue_sample_semantics": (
            "state-change event samples; not wall-clock time weighted"
        ),
        "process_cpu_percent": (cpu_seconds / wall_seconds * 100.0) if wall_seconds else 0.0,
        "rss_start_bytes": rss_start_bytes,
        "rss_end_bytes": rss_end_bytes,
        "rss_peak_bytes": (
            rss_peak_bytes
            if rss_peak_bytes is not None
            else max(rss_values) if rss_values else None
        ),
        "rss_delta_bytes": (
            rss_end_bytes - rss_start_bytes
            if rss_start_bytes is not None and rss_end_bytes is not None
            else None
        ),
    }


def run_benchmark(
    datasets: list[Dataset],
    *,
    warmups: int = 1,
    repeats: int = 5,
    seed: int = DEFAULT_SEED,
) -> dict:
    results = []
    order = worker_order(seed)
    for dataset in datasets:
        for workers in order:
            for _ in range(warmups):
                run_once(dataset, workers)
            measured = [run_once(dataset, workers) for _ in range(repeats)]
            results.append(aggregate_results(measured))
    return {
        "conditions": {
            "worker_order": order,
            "warmups": warmups,
            "measurement_runs": repeats,
            "os_file_cache_controlled": False,
            "logical_cpu_count": os.cpu_count(),
            "rss_optional": True,
        },
        "results": results,
    }


def matrix_conditions(seed: int = DEFAULT_SEED) -> list[tuple[int, str]]:
    conditions = [
        (worker_count, memory_limit)
        for memory_limit in MATRIX_MEMORY_LIMITS
        for worker_count in DEFAULT_WORKERS
    ]
    random.Random(seed).shuffle(conditions)
    return conditions


def run_condition(
    dataset: Dataset,
    *,
    worker_count: int,
    memory_limit: str,
    prefetch_pages: int = 15,
    measurement_pages: int | None = None,
    source_pages: int | None = None,
    warmups: int = 1,
    repeats: int = 5,
) -> dict:
    rss_start, _initial_peak = _process_memory_bytes()
    for _ in range(warmups):
        run_once(
            dataset,
            worker_count,
            memory_limit=memory_limit,
            prefetch_pages=prefetch_pages,
            measurement_pages=measurement_pages,
            source_pages=source_pages,
        )
    measured = [
        run_once(
            dataset,
            worker_count,
            memory_limit=memory_limit,
            prefetch_pages=prefetch_pages,
            measurement_pages=measurement_pages,
            source_pages=source_pages,
        )
        for _ in range(repeats)
    ]
    rss_end, rss_peak = _process_memory_bytes()
    result = aggregate_results(
        measured,
        rss_start_bytes=rss_start,
        rss_end_bytes=rss_end,
        rss_peak_bytes=rss_peak,
    )
    result["source_pages"] = source_pages
    result["measurement_pages"] = measurement_pages
    return result


def _condition_command(
    dataset: Dataset,
    *,
    worker_count: int,
    memory_limit: str,
    prefetch_pages: int,
    measurement_pages: int | None,
    source_pages: int | None,
    warmups: int,
    repeats: int,
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "tooling.image_loader_benchmark",
        "--condition-child",
        "--dataset-name",
        dataset.name,
        "--dataset-path",
        str(dataset.path),
        "--worker-count",
        str(worker_count),
        "--memory-limit",
        memory_limit,
        "--prefetch-pages",
        str(prefetch_pages),
        "--warmups",
        str(warmups),
        "--repeats",
        str(repeats),
    ]
    if measurement_pages is not None:
        command.extend(["--measurement-pages", str(measurement_pages)])
    if source_pages is not None:
        command.extend(["--source-pages", str(source_pages)])
    return command


def _subprocess_environment() -> dict[str, str]:
    root = Path(__file__).resolve().parent.parent
    paths = [str(root), str(root / "src")]
    existing = os.environ.get("PYTHONPATH")
    if existing:
        paths.append(existing)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    return environment


def run_condition_subprocess(
    dataset: Dataset,
    *,
    worker_count: int,
    memory_limit: str,
    prefetch_pages: int = 15,
    measurement_pages: int | None = None,
    source_pages: int | None = None,
    warmups: int = 1,
    repeats: int = 5,
) -> dict:
    completed = subprocess.run(
        _condition_command(
            dataset,
            worker_count=worker_count,
            memory_limit=memory_limit,
            prefetch_pages=prefetch_pages,
            measurement_pages=measurement_pages,
            source_pages=source_pages,
            warmups=warmups,
            repeats=repeats,
        ),
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_environment(),
    )
    return json.loads(completed.stdout)


def run_matrix(
    dataset: Dataset,
    *,
    prefetch_pages: int = 15,
    warmups: int = 1,
    repeats: int = 5,
    seed: int = DEFAULT_SEED,
) -> dict:
    order = matrix_conditions(seed)
    results = []
    for worker_count, memory_limit in order:
        results.append(
            run_condition_subprocess(
                dataset,
                worker_count=worker_count,
                memory_limit=memory_limit,
                prefetch_pages=prefetch_pages,
                warmups=warmups,
                repeats=repeats,
            )
        )
    decoded_total = max(
        (result["decoded_total_bytes"] for result in results),
        default=0,
    )
    decoded_average = max(
        (result["decoded_average_bytes_per_page"] for result in results),
        default=0.0,
    )
    decoded_max = max(
        (result["decoded_max_bytes_per_page"] for result in results),
        default=0,
    )
    return {
        "mode": "worker_cache_matrix",
        "conditions": {
            "condition_order": [
                {
                    "worker_count": worker_count,
                    "memory_limit": memory_limit,
                }
                for worker_count, memory_limit in order
            ],
            "prefetch_pages": prefetch_pages,
            "warmups": warmups,
            "measurement_runs": repeats,
            "os_file_cache_controlled": False,
            "logical_cpu_count": os.cpu_count(),
            "condition_process_isolated": True,
        },
        "dataset": {
            "name": dataset.name,
            "decoded_total_bytes": decoded_total,
            "decoded_average_bytes_per_page": decoded_average,
            "decoded_max_bytes_per_page": decoded_max,
        },
        "results": results,
    }


def cache_candidate_conditions(
    datasets: list[Dataset],
    seed: int = DEFAULT_SEED,
) -> list[tuple[Dataset, str]]:
    """通常2素材と高解像度素材を256/512MBで比較する条件を返す。"""
    conditions = [
        (dataset, memory_limit)
        for dataset in datasets
        for memory_limit in ("256MB", "512MB")
    ]
    random.Random(seed).shuffle(conditions)
    return conditions


def prefetch_window_conditions(
    datasets: list[Dataset],
    seed: int = DEFAULT_SEED,
) -> list[tuple[Dataset, int]]:
    """64ページZIP 2素材のprefetch窓8条件を返す。"""
    zip_datasets = [
        dataset
        for dataset in datasets
        if dataset.name in ("jpg_png_zip", "high_resolution_zip")
    ]
    conditions = [
        (dataset, prefetch_pages)
        for dataset in zip_datasets
        for prefetch_pages in (5, 10, 15, 20)
    ]
    random.Random(seed).shuffle(conditions)
    return conditions


def policy_matrix_conditions(
    datasets: list[Dataset],
    seed: int = DEFAULT_SEED,
) -> list[tuple[Dataset, str, int]]:
    """3素材 × cache 3種 × prefetch 3種の27条件を返す。"""
    conditions = [
        (dataset, memory_limit, prefetch_pages)
        for dataset in datasets
        for memory_limit in POLICY_MATRIX_MEMORY_LIMITS
        for prefetch_pages in POLICY_MATRIX_PREFETCH_PAGES
    ]
    random.Random(seed).shuffle(conditions)
    return conditions


def environment_metadata() -> dict:
    try:
        import PySide6

        qt_version = PySide6.__version__
    except ImportError:
        qt_version = None
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "pillow": PIL.__version__,
        "qt": qt_version,
        "logical_cpu_count": os.cpu_count(),
        "dataset_dimensions": {
            name: list(size) for name, size in DATASET_DIMENSIONS.items()
        },
    }


def run_policy_matrix(
    root: Path,
    *,
    warmups: int = 1,
    repeats: int = 5,
    seed: int = DEFAULT_SEED,
) -> dict:
    """推奨設定policy確定用の27条件を独立processで測る。"""
    batch_started = time.perf_counter()
    generation_started = time.perf_counter()
    datasets = generate_datasets(root, page_count=POLICY_MATRIX_SOURCE_PAGES)
    dataset_generation_seconds = time.perf_counter() - generation_started

    order = policy_matrix_conditions(datasets, seed)
    results = []
    for dataset, memory_limit, prefetch_pages in order:
        condition_started = time.perf_counter()
        result = run_condition_subprocess(
            dataset,
            worker_count=POLICY_MATRIX_WORKER_COUNT,
            memory_limit=memory_limit,
            prefetch_pages=prefetch_pages,
            measurement_pages=POLICY_MATRIX_MEASUREMENT_PAGES,
            source_pages=POLICY_MATRIX_SOURCE_PAGES,
            warmups=warmups,
            repeats=repeats,
        )
        result["condition_elapsed_seconds"] = time.perf_counter() - condition_started
        results.append(result)
    return {
        "schema_version": 1,
        "mode": "recommendation_policy_matrix",
        "environment": environment_metadata(),
        "conditions": {
            "worker_count": POLICY_MATRIX_WORKER_COUNT,
            "memory_limits": list(POLICY_MATRIX_MEMORY_LIMITS),
            "prefetch_values": list(POLICY_MATRIX_PREFETCH_PAGES),
            "source_pages": POLICY_MATRIX_SOURCE_PAGES,
            "measurement_pages": POLICY_MATRIX_MEASUREMENT_PAGES,
            "condition_count": len(order),
            "seed": seed,
            "warmups": warmups,
            "measurement_runs": repeats,
            "condition_process_isolated": True,
            "os_file_cache_controlled": False,
            "queue_sample_semantics": (
                "state-change event samples; not wall-clock time weighted"
            ),
            "elapsed_semantics": (
                "parent-side wall clock including subprocess startup; "
                "batch includes dataset generation"
            ),
            "condition_order": [
                {
                    "dataset": dataset.name,
                    "memory_limit": memory_limit,
                    "prefetch_pages": prefetch_pages,
                }
                for dataset, memory_limit, prefetch_pages in order
            ],
        },
        "dataset_generation_seconds": dataset_generation_seconds,
        "batch_elapsed_seconds": time.perf_counter() - batch_started,
        "results": results,
    }


def run_loader_experiment_batch(
    datasets: list[Dataset],
    *,
    warmups: int = 1,
    repeats: int = 5,
    seed: int = DEFAULT_SEED,
) -> dict:
    cache_results = []
    cache_order = cache_candidate_conditions(datasets, seed)
    for dataset, memory_limit in cache_order:
        cache_results.append(
            run_condition_subprocess(
                dataset,
                worker_count=4,
                memory_limit=memory_limit,
                prefetch_pages=15,
                measurement_pages=20,
                source_pages=20,
                warmups=warmups,
                repeats=repeats,
            )
        )

    prefetch_results = []
    prefetch_order = prefetch_window_conditions(datasets, seed)
    for dataset, prefetch_pages in prefetch_order:
        prefetch_results.append(
            run_condition_subprocess(
                dataset,
                worker_count=4,
                memory_limit="512MB",
                prefetch_pages=prefetch_pages,
                measurement_pages=20,
                source_pages=64,
                warmups=warmups,
                repeats=repeats,
            )
        )
    return {
        "mode": "cache_prefetch_batch",
        "environment": environment_metadata(),
        "conditions": {
            "seed": seed,
            "warmups": warmups,
            "measurement_runs": repeats,
            "condition_process_isolated": True,
            "queue_sample_semantics": (
                "state-change event samples; not wall-clock time weighted"
            ),
            "cache_candidate": {
                "worker_count": 4,
                "prefetch_pages": 15,
                "memory_limits": ["256MB", "512MB"],
                "source_pages": 20,
                "measurement_pages": 20,
                "condition_count": len(cache_order),
            },
            "prefetch_window": {
                "worker_count": 4,
                "memory_limit": "512MB",
                "source_pages": 64,
                "measurement_pages": 20,
                "prefetch_values": [5, 10, 15, 20],
                "condition_count": len(prefetch_order),
            },
        },
        "cache_candidate": cache_results,
        "prefetch_window": prefetch_results,
    }


def _foreground_summary(samples: list[dict]) -> dict:
    stalls = [sample["stall_ms"] for sample in samples]
    waits = [sample["wait_ms"] for sample in samples]
    decodes = [sample["decode_ms"] for sample in samples]
    return {
        "samples": len(samples),
        "owner_claim_count": sum(
            sample["claim"] == "owner" for sample in samples
        ),
        "wait_claim_count": sum(
            sample["claim"] == "wait" for sample in samples
        ),
        "synchronous_decode_count": sum(
            sample["synchronous_decode"] for sample in samples
        ),
        "completion_reuse_count": sum(
            sample["completion_reused"] for sample in samples
        ),
        "decode_ms_total": sum(decodes),
        "wait_ms_total": sum(waits),
        "stall_average_ms": statistics.fmean(stalls) if stalls else 0.0,
        "stall_p95_ms": percentile(stalls, 0.95),
        "stall_max_ms": max(stalls, default=0.0),
        "duplicate_decode_count": sum(
            sample["duplicate_decode_count"] for sample in samples
        ),
        "details": samples,
    }


def run_cold_jump_condition(
    dataset: Dataset,
    *,
    repeats: int = 5,
    jumps: tuple[int, ...] = (0, 32, 4, 48, 8, 56),
) -> dict:
    samples = []
    for run_index in range(repeats):
        handler = ForegroundBenchmarkFileHandler(
            _benchmark_config("512MB", 15),
            4,
        )
        try:
            if not handler.open_files([dataset.path]):
                raise RuntimeError(f"failed to open dataset: {dataset.path}")
            _wait_for_idle(handler)
            for target in jumps:
                handler.stop_all_loading()
                cache_key = handler._cache_key_for_file(
                    handler.current_files[target]
                )
                if handler._cache_get(cache_key) is not None:
                    raise AssertionError("cold jump target was cached")
                if handler._scheduler.cache_key_state(cache_key) is not None:
                    raise AssertionError(
                        "cold jump target was queued or in progress"
                    )
                event_start = len(handler.scheduler_events())
                perf_start = len(handler.performance_samples())
                started = time.perf_counter()
                image = handler.get_image_at(target)
                stall_ms = (time.perf_counter() - started) * 1000
                if image is None:
                    raise RuntimeError(f"cold jump failed: {target}")
                events = handler.scheduler_events()[event_start:]
                perf = handler.performance_samples()[perf_start:]
                foreground = next(
                    (
                        value
                        for value in reversed(perf)
                        if value.get("path") == "foreground"
                    ),
                    {},
                )
                claim = "wait" if any(
                    event["reason"] == "foreground_wait"
                    for event in events
                ) else "owner"
                samples.append(
                    {
                        "run": run_index,
                        "target": target,
                        "claim": claim,
                        "synchronous_decode": (
                            foreground.get("cache") == "miss"
                        ),
                        "completion_reused": (
                            foreground.get("cache") == "waited"
                        ),
                        "decode_ms": float(
                            foreground.get("decode_ms", 0.0)
                        ),
                        "wait_ms": float(
                            foreground.get("queue_wait_ms", 0.0)
                        ),
                        "stall_ms": stall_ms,
                        "cold_precondition_verified": True,
                        "duplicate_decode_count": 0,
                    }
                )
        finally:
            handler.close()
    result = _foreground_summary(samples)
    result.update(
        {
            "scenario": "cold_jump",
            "dataset": dataset.name,
            "worker_count": 4,
            "memory_limit": "512MB",
            "prefetch_pages": 15,
            "jump_sequence": list(jumps),
        }
    )
    return result


def _wait_for_scheduler_event(
    scheduler: BenchmarkImageLoadScheduler,
    reason: str,
    start_index: int,
    timeout: float = 30.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if any(
            event["reason"] == reason
            for event in scheduler.events()[start_index:]
        ):
            return
        time.sleep(0.001)
    raise TimeoutError(f"scheduler event did not occur: {reason}")


def _release_decode_after_wait_claim(
    handler: ForegroundBenchmarkFileHandler,
    event_start: int,
) -> None:
    try:
        _wait_for_scheduler_event(
            handler._scheduler,
            "foreground_wait",
            event_start,
        )
    finally:
        handler.release_background_decode()


def run_collision_condition(
    dataset: Dataset,
    *,
    repeats: int = 5,
    target: int = 32,
) -> dict:
    samples = []
    for run_index in range(repeats):
        handler = ForegroundBenchmarkFileHandler(
            _benchmark_config("512MB", 15),
            4,
        )
        release_thread = None
        try:
            if not handler.open_files([dataset.path]):
                raise RuntimeError(f"failed to open dataset: {dataset.path}")
            _wait_for_idle(handler)
            handler.stop_all_loading()
            cache_key = handler._cache_key_for_file(
                handler.current_files[target]
            )
            handler.block_background_decode(cache_key)
            handler.current_index = target - 1
            handler._prefetch_around(target - 1, direction=1)
            if not handler._blocked_decode_started.wait(timeout=30):
                raise TimeoutError("background decode did not start")
            event_start = len(handler.scheduler_events())
            perf_start = len(handler.performance_samples())

            release_thread = threading.Thread(
                target=_release_decode_after_wait_claim,
                args=(handler, event_start),
                name="EzCoBenchmarkCollisionRelease",
                daemon=True,
            )
            release_thread.start()
            started = time.perf_counter()
            image = handler.get_image_at(target)
            stall_ms = (time.perf_counter() - started) * 1000
            release_thread.join(timeout=30)
            if release_thread.is_alive():
                raise TimeoutError("collision release thread did not finish")
            if image is None:
                raise RuntimeError("collision foreground load failed")
            perf = handler.performance_samples()[perf_start:]
            foreground = next(
                (
                    value
                    for value in reversed(perf)
                    if value.get("path") == "foreground"
                ),
                {},
            )
            metrics = handler.benchmark_metrics()
            samples.append(
                {
                    "run": run_index,
                    "target": target,
                    "claim": "wait",
                    "synchronous_decode": False,
                    "completion_reused": (
                        foreground.get("cache") == "waited"
                        and handler._cache_get(cache_key) is image
                    ),
                    "decode_ms": 0.0,
                    "wait_ms": float(
                        foreground.get("queue_wait_ms", 0.0)
                    ),
                    "stall_ms": stall_ms,
                    "cold_precondition_verified": True,
                    "duplicate_decode_count": metrics[
                        "duplicate_decode_count"
                    ],
                }
            )
        finally:
            handler.release_background_decode()
            if release_thread is not None:
                release_thread.join(timeout=1)
            handler.close()
    result = _foreground_summary(samples)
    result.update(
        {
            "scenario": "in_progress_collision",
            "dataset": dataset.name,
            "worker_count": 4,
            "memory_limit": "512MB",
            "prefetch_pages": 15,
            "target": target,
        }
    )
    return result


def run_foreground_subprocess(
    dataset: Dataset,
    *,
    scenario: str,
    repeats: int = 5,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "tooling.image_loader_benchmark",
        "--foreground-child",
        "--foreground-scenario",
        scenario,
        "--dataset-name",
        dataset.name,
        "--dataset-path",
        str(dataset.path),
        "--repeats",
        str(repeats),
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_environment(),
    )
    return json.loads(completed.stdout)


def run_foreground_batch(
    datasets: list[Dataset],
    *,
    repeats: int = 5,
) -> dict:
    selected = {
        dataset.name: dataset
        for dataset in datasets
        if dataset.name in ("jpg_png_zip", "high_resolution_zip")
    }
    return {
        "mode": "foreground_stall",
        "environment": environment_metadata(),
        "conditions": {
            "worker_count": 4,
            "memory_limit": "512MB",
            "prefetch_pages": 15,
            "measurement_runs": repeats,
            "condition_process_isolated": True,
        },
        "cold_jump": [
            run_foreground_subprocess(
                selected[name],
                scenario="cold_jump",
                repeats=repeats,
            )
            for name in ("jpg_png_zip", "high_resolution_zip")
        ],
        "in_progress_collision": run_foreground_subprocess(
            selected["high_resolution_zip"],
            scenario="collision",
            repeats=repeats,
        ),
    }


def _handler_memory_totals(
    handlers: list[BenchmarkFileHandler],
) -> dict:
    cache_bytes = 0
    resident_pages = 0
    worker_count = 0
    alive_workers = 0
    for handler in handlers:
        with handler._cache_lock:
            cache_bytes += handler.cache_size
            resident_pages += len(handler.image_cache)
        snapshot = handler._scheduler.snapshot()
        worker_count += snapshot["worker_count"]
        alive_workers += snapshot["alive_workers"]
    return {
        "cache_bytes": cache_bytes,
        "resident_pages": resident_pages,
        "scheduler_workers": worker_count,
        "alive_workers": alive_workers,
    }


def run_multi_handler_condition(
    dataset: Dataset,
    *,
    scenario: str,
    handler_count: int,
    memory_limit: str,
) -> dict:
    if scenario not in ("realistic", "stress"):
        raise ValueError(f"unknown multi-handler scenario: {scenario}")
    rss_start, _ = _process_memory_bytes()
    handlers = []
    try:
        for _ in range(handler_count):
            handler = BenchmarkFileHandler(
                _benchmark_config(memory_limit, 15),
                4,
            )
            handlers.append(handler)
            if not handler.open_files([dataset.path]):
                raise RuntimeError(f"failed to open dataset: {dataset.path}")

        pages_to_visit = 5 if scenario == "realistic" else 20
        for handler in handlers:
            for index in range(
                min(pages_to_visit, handler.get_total_pages())
            ):
                if index:
                    handler.next_file()
                if handler.get_current_image() is None:
                    raise RuntimeError(
                        f"multi-handler page failed: {index}"
                    )
            _wait_for_idle(handler)

        before_close = _handler_memory_totals(handlers)
        rss_before_close, rss_peak = _process_memory_bytes()
    finally:
        for handler in handlers:
            handler.close()

    after_close = _handler_memory_totals(handlers)
    rss_after_close, _ = _process_memory_bytes()
    release_verified = (
        after_close["cache_bytes"] == 0
        and after_close["resident_pages"] == 0
        and after_close["alive_workers"] == 0
    )
    if not release_verified:
        raise AssertionError(
            f"multi-handler resources were not released: {after_close}"
        )
    return {
        "scenario": scenario,
        "dataset": dataset.name,
        "handler_count": handler_count,
        "worker_count_per_handler": 4,
        "prefetch_pages": 15,
        "memory_limit_per_handler": memory_limit,
        "pages_visited_per_handler": pages_to_visit,
        "rss_start_bytes": rss_start,
        "rss_peak_bytes": rss_peak,
        "rss_before_close_bytes": rss_before_close,
        "rss_after_close_bytes": rss_after_close,
        "before_close": before_close,
        "after_close": after_close,
        "release_verified": release_verified,
        "rss_return_required": False,
    }


def run_multi_handler_subprocess(
    dataset: Dataset,
    *,
    scenario: str,
    handler_count: int,
    memory_limit: str,
) -> dict:
    command = [
        sys.executable,
        "-m",
        "tooling.image_loader_benchmark",
        "--multi-handler-child",
        "--multi-handler-scenario",
        scenario,
        "--handler-count",
        str(handler_count),
        "--dataset-name",
        dataset.name,
        "--dataset-path",
        str(dataset.path),
        "--memory-limit",
        memory_limit,
    ]
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_environment(),
    )
    return json.loads(completed.stdout)


def multi_handler_conditions(
    seed: int = DEFAULT_SEED,
) -> list[tuple[str, int, str]]:
    conditions = [
        (scenario, handler_count, memory_limit)
        for scenario in ("realistic", "stress")
        for memory_limit in ("256MB", "512MB")
        for handler_count in (1, 2, 4)
    ]
    random.Random(seed).shuffle(conditions)
    return conditions


def run_multi_handler_batch(
    datasets: list[Dataset],
    *,
    seed: int = DEFAULT_SEED,
) -> dict:
    selected = {dataset.name: dataset for dataset in datasets}
    order = multi_handler_conditions(seed)
    results = []
    for scenario, handler_count, memory_limit in order:
        dataset = selected[
            "jpg_folder"
            if scenario == "realistic"
            else "high_resolution_zip"
        ]
        results.append(
            run_multi_handler_subprocess(
                dataset,
                scenario=scenario,
                handler_count=handler_count,
                memory_limit=memory_limit,
            )
        )
    return {
        "mode": "multi_handler_memory",
        "environment": environment_metadata(),
        "conditions": {
            "condition_process_isolated": True,
            "worker_count_per_handler": 4,
            "prefetch_pages": 15,
            "handler_counts": [1, 2, 4],
            "memory_limits": ["256MB", "512MB"],
            "seed": seed,
        },
        "results": results,
    }


def run_complete_performance_batch(
    datasets: list[Dataset],
    *,
    warmups: int = 1,
    repeats: int = 5,
    seed: int = DEFAULT_SEED,
) -> dict:
    from tooling.image_display_benchmark import run_batch as run_display_batch

    return {
        "schema_version": 1,
        "benchmark": "image_performance_batch",
        "environment": environment_metadata(),
        "cache_prefetch": run_loader_experiment_batch(
            datasets,
            warmups=warmups,
            repeats=repeats,
            seed=seed,
        ),
        "foreground_stall": run_foreground_batch(
            datasets,
            repeats=repeats,
        ),
        "display_preparation": run_display_batch(
            warmups=warmups,
            iterations=repeats,
        ),
        "multi_handler_memory": run_multi_handler_batch(
            datasets,
            seed=seed,
        ),
    }


def _markdown_value(value, digits: int = 2) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_matrix_markdown(report: dict) -> str:
    lines = [
        "| Cache | Worker | p95 ms | Hit rate | Duplicate | Redecode | "
        "Unused eviction | Unused bytes | RSS peak |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    memory_order = {value: index for index, value in enumerate(MATRIX_MEMORY_LIMITS)}
    results = sorted(
        report["results"],
        key=lambda result: (
            memory_order.get(result["memory_limit"], len(memory_order)),
            result["worker_count"],
        ),
    )
    for result in results:
        lines.append(
            "| {memory_limit} | {worker_count} | {p95} | {hit_rate}% | "
            "{duplicate} | {redecode} | {evicted} | {evicted_bytes} | {rss_peak} |".format(
                memory_limit=result["memory_limit"],
                worker_count=result["worker_count"],
                p95=_markdown_value(result["p95_latency_ms"]),
                hit_rate=_markdown_value(result["cache_hit_rate"] * 100),
                duplicate=result["duplicate_decode_count"],
                redecode=result["redecode_count"],
                evicted=result["prefetched_evicted_before_use"],
                evicted_bytes=result["prefetched_evicted_before_use_bytes"],
                rss_peak=_markdown_value(result["rss_peak_bytes"], 0),
            )
        )
    return "\n".join(lines) + "\n"


def render_policy_matrix_markdown(report: dict) -> str:
    conditions = report["conditions"]
    lines = [
        "# Recommendation policy matrix",
        "",
        "worker={worker} / source {source} pages / measured {measured} pages / "
        "warmup {warmups} + {runs} runs / isolated process per condition".format(
            worker=conditions["worker_count"],
            source=conditions["source_pages"],
            measured=conditions["measurement_pages"],
            warmups=conditions["warmups"],
            runs=conditions["measurement_runs"],
        ),
        "",
        "Queue values come from scheduler state-change event samples, "
        "not wall-clock time-weighted samples.",
        "",
        "Elapsed seconds are parent-side wall clock including subprocess "
        "startup. Batch elapsed includes dataset generation.",
        "",
        "| Dataset | Cache | Prefetch | p50 ms | p95 ms | Max ms | Hit rate | "
        "Unused eviction | Unused bytes | Redecode | Queue max | "
        "Queue event p95 | Decoded avg/page | Decoded max/page | RSS peak | "
        "Elapsed s |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | "
        "---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    memory_order = {
        value: index
        for index, value in enumerate(POLICY_MATRIX_MEMORY_LIMITS)
    }
    results = sorted(
        report["results"],
        key=lambda result: (
            result["dataset"],
            memory_order.get(result["memory_limit"], len(memory_order)),
            result["prefetch_pages"],
        ),
    )
    for result in results:
        lines.append(
            "| {dataset} | {cache} | {prefetch} | {p50} | {p95} | {maximum} | "
            "{hit_rate}% | {evicted} | {evicted_bytes} | {redecode} | "
            "{queue_max} | {queue_p95} | {decoded_avg} | {decoded_max} | "
            "{rss_peak} | {elapsed} |".format(
                dataset=result["dataset"],
                cache=result["memory_limit"],
                prefetch=result["prefetch_pages"],
                p50=_markdown_value(result["p50_latency_ms"]),
                p95=_markdown_value(result["p95_latency_ms"]),
                maximum=_markdown_value(result["max_latency_ms"]),
                hit_rate=_markdown_value(result["cache_hit_rate"] * 100),
                evicted=result["prefetched_evicted_before_use"],
                evicted_bytes=result["prefetched_evicted_before_use_bytes"],
                redecode=result["redecode_count"],
                queue_max=result["queue_depth_max"],
                queue_p95=_markdown_value(
                    result["queue_depth_event_sample_p95"]
                ),
                decoded_avg=_markdown_value(
                    result["decoded_average_bytes_per_page"],
                    0,
                ),
                decoded_max=_markdown_value(
                    result["decoded_max_bytes_per_page"],
                    0,
                ),
                rss_peak=_markdown_value(result["rss_peak_bytes"], 0),
                elapsed=_markdown_value(result["condition_elapsed_seconds"]),
            )
        )
    lines.extend(
        [
            "",
            "Dataset generation: {generation} s / batch total: {batch} s".format(
                generation=_markdown_value(
                    report["dataset_generation_seconds"]
                ),
                batch=_markdown_value(report["batch_elapsed_seconds"]),
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def render_loader_batch_markdown(report: dict) -> str:
    lines = [
        "# Image loading cache/prefetch benchmark",
        "",
        "Queue p95 is calculated from scheduler state-change event samples, "
        "not wall-clock time-weighted samples.",
    ]
    for title, key in (
        ("Cache default candidates", "cache_candidate"),
        ("Prefetch window", "prefetch_window"),
    ):
        lines.extend(
            [
                "",
                f"## {title}",
                "",
                "| Dataset | Cache | Prefetch | p95 ms | Hit rate | "
                "Queue max | Queue event p95 | Active max | RSS peak |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for result in report[key]:
            lines.append(
                "| {dataset} | {cache} | {prefetch} | {p95} | {hit_rate}% | "
                "{queue_max} | {queue_p95} | {active_max} | {rss_peak} |".format(
                    dataset=result["dataset"],
                    cache=result["memory_limit"],
                    prefetch=result["prefetch_pages"],
                    p95=_markdown_value(result["p95_latency_ms"]),
                    hit_rate=_markdown_value(result["cache_hit_rate"] * 100),
                    queue_max=result["queue_depth_max"],
                    queue_p95=_markdown_value(
                        result["queue_depth_event_sample_p95"]
                    ),
                    active_max=result["active_workers_max"],
                    rss_peak=_markdown_value(result["rss_peak_bytes"], 0),
                )
            )
    return "\n".join(lines) + "\n"


def render_complete_batch_markdown(report: dict) -> str:
    from tooling.image_display_benchmark import render_markdown as render_display

    lines = [
        "# Image performance batch",
        "",
        "Primary data: `image_performance_batch.json`",
        "",
        render_loader_batch_markdown(report["cache_prefetch"]).rstrip(),
        "",
        "## Foreground stall",
        "",
        "| Scenario | Dataset | Samples | Owner | Wait | Decode | "
        "Average ms | p95 ms | Max ms | Duplicate |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    foreground = [
        *report["foreground_stall"]["cold_jump"],
        report["foreground_stall"]["in_progress_collision"],
    ]
    for result in foreground:
        lines.append(
            "| {scenario} | {dataset} | {samples} | {owner} | {wait} | "
            "{decode} | {average} | {p95} | {maximum} | {duplicate} |".format(
                scenario=result["scenario"],
                dataset=result["dataset"],
                samples=result["samples"],
                owner=result["owner_claim_count"],
                wait=result["wait_claim_count"],
                decode=result["synchronous_decode_count"],
                average=_markdown_value(result["stall_average_ms"]),
                p95=_markdown_value(result["stall_p95_ms"]),
                maximum=_markdown_value(result["stall_max_ms"]),
                duplicate=result["duplicate_decode_count"],
            )
        )
    lines.extend(
        [
            "",
            render_display(report["display_preparation"]).rstrip(),
            "",
            "## Multi-handler memory",
            "",
            "| Scenario | Cache/handler | Handlers | Cache bytes | Pages | "
            "Workers | RSS peak | Released |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for result in report["multi_handler_memory"]["results"]:
        before = result["before_close"]
        lines.append(
            "| {scenario} | {cache} | {handlers} | {bytes} | {pages} | "
            "{workers} | {rss} | {released} |".format(
                scenario=result["scenario"],
                cache=result["memory_limit_per_handler"],
                handlers=result["handler_count"],
                bytes=before["cache_bytes"],
                pages=before["resident_pages"],
                workers=before["scheduler_workers"],
                rss=_markdown_value(result["rss_peak_bytes"], 0),
                released=result["release_verified"],
            )
        )
    lines.extend(
        [
            "",
            "RSS returning immediately after close is observational only; "
            "cache pages and worker shutdown are the release verdict.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", action="store_true")
    parser.add_argument("--performance-batch", action="store_true")
    parser.add_argument("--foreground-batch", action="store_true")
    parser.add_argument("--multi-handler-batch", action="store_true")
    parser.add_argument("--full-batch", action="store_true")
    parser.add_argument("--policy-matrix", action="store_true")
    parser.add_argument("--pages", type=int, default=20)
    parser.add_argument("--warmups", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--condition-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--foreground-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--foreground-scenario", help=argparse.SUPPRESS)
    parser.add_argument("--multi-handler-child", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--multi-handler-scenario", help=argparse.SUPPRESS)
    parser.add_argument("--handler-count", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--dataset-name", help=argparse.SUPPRESS)
    parser.add_argument("--dataset-path", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--worker-count", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--memory-limit", help=argparse.SUPPRESS)
    parser.add_argument("--prefetch-pages", type=int, default=15, help=argparse.SUPPRESS)
    parser.add_argument("--measurement-pages", type=int, help=argparse.SUPPRESS)
    parser.add_argument("--source-pages", type=int, help=argparse.SUPPRESS)
    return parser


def _markdown_renderer(args):
    """mode別のMarkdown rendererを返す。対象外modeはNone。"""
    if args.full_batch:
        return render_complete_batch_markdown
    if args.performance_batch:
        return render_loader_batch_markdown
    if args.policy_matrix:
        return render_policy_matrix_markdown
    if args.matrix:
        return render_matrix_markdown
    return None


def _write_report(args, report: dict) -> int:
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    if args.markdown_output:
        renderer = _markdown_renderer(args)
        if renderer is None:
            raise SystemExit(
                "--markdown-output requires --matrix, --performance-batch, "
                "--policy-matrix, or --full-batch"
            )
        args.markdown_output.write_text(renderer(report), encoding="utf-8")
    print(text)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.pages < 1 or args.warmups < 0 or args.repeats < 1:
        raise SystemExit("pages/repeats must be positive and warmups must be non-negative")
    logging.getLogger().setLevel(logging.WARNING)
    if args.condition_child:
        if (
            not args.dataset_name
            or args.dataset_path is None
            or args.worker_count is None
            or args.memory_limit is None
        ):
            raise SystemExit("condition child requires dataset, worker, and memory arguments")
        result = run_condition(
            Dataset(args.dataset_name, args.dataset_path),
            worker_count=args.worker_count,
            memory_limit=args.memory_limit,
            prefetch_pages=args.prefetch_pages,
            measurement_pages=args.measurement_pages,
            source_pages=args.source_pages,
            warmups=args.warmups,
            repeats=args.repeats,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.foreground_child:
        if (
            not args.dataset_name
            or args.dataset_path is None
            or args.foreground_scenario not in ("cold_jump", "collision")
        ):
            raise SystemExit(
                "foreground child requires dataset and valid scenario"
            )
        dataset = Dataset(args.dataset_name, args.dataset_path)
        result = (
            run_cold_jump_condition(dataset, repeats=args.repeats)
            if args.foreground_scenario == "cold_jump"
            else run_collision_condition(dataset, repeats=args.repeats)
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.multi_handler_child:
        if (
            not args.dataset_name
            or args.dataset_path is None
            or args.multi_handler_scenario not in ("realistic", "stress")
            or args.handler_count not in (1, 2, 4)
            or args.memory_limit not in ("256MB", "512MB")
        ):
            raise SystemExit(
                "multi-handler child requires valid scenario/count/cache"
            )
        result = run_multi_handler_condition(
            Dataset(args.dataset_name, args.dataset_path),
            scenario=args.multi_handler_scenario,
            handler_count=args.handler_count,
            memory_limit=args.memory_limit,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.policy_matrix:
        # policy matrixは64ページ素材を自分で作り、--pagesには依存しない。
        with tempfile.TemporaryDirectory(prefix="ezco-policy-matrix-") as temp:
            report = run_policy_matrix(
                Path(temp),
                warmups=args.warmups,
                repeats=args.repeats,
                seed=args.seed,
            )
        return _write_report(args, report)
    with tempfile.TemporaryDirectory(prefix="ezco-image-benchmark-") as temp:
        page_count = (
            max(args.pages, 64)
            if (
                args.performance_batch
                or args.foreground_batch
                or args.multi_handler_batch
                or args.full_batch
            )
            else args.pages
        )
        datasets = generate_datasets(Path(temp), page_count=page_count)
        if args.full_batch:
            report = run_complete_performance_batch(
                datasets,
                warmups=args.warmups,
                repeats=args.repeats,
                seed=args.seed,
            )
        elif args.multi_handler_batch:
            report = run_multi_handler_batch(
                datasets,
                seed=args.seed,
            )
        elif args.foreground_batch:
            report = run_foreground_batch(
                datasets,
                repeats=args.repeats,
            )
        elif args.performance_batch:
            report = run_loader_experiment_batch(
                datasets,
                warmups=args.warmups,
                repeats=args.repeats,
                seed=args.seed,
            )
        elif args.matrix:
            high_resolution = next(
                dataset
                for dataset in datasets
                if dataset.name == "high_resolution_zip"
            )
            report = run_matrix(
                high_resolution,
                prefetch_pages=args.prefetch_pages,
                warmups=args.warmups,
                repeats=args.repeats,
                seed=args.seed,
            )
        else:
            report = run_benchmark(
                datasets,
                warmups=args.warmups,
                repeats=args.repeats,
                seed=args.seed,
            )
    return _write_report(args, report)


if __name__ == "__main__":
    raise SystemExit(main())
