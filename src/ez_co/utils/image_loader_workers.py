"""画像読込worker設定を正規化し、実worker数へ解決する。"""
from __future__ import annotations


AUTO_IMAGE_LOADER_WORKERS = "auto"
MIN_IMAGE_LOADER_WORKERS = 1
MAX_IMAGE_LOADER_WORKERS = 8


def normalize_image_loader_workers(value) -> str | int:
    """保存値を ``"auto"`` または1～8の整数へ正規化する。"""
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped == AUTO_IMAGE_LOADER_WORKERS:
            return AUTO_IMAGE_LOADER_WORKERS
        try:
            value = int(stripped)
        except ValueError:
            return AUTO_IMAGE_LOADER_WORKERS
    if isinstance(value, bool):
        return AUTO_IMAGE_LOADER_WORKERS
    if isinstance(value, int) and MIN_IMAGE_LOADER_WORKERS <= value <= MAX_IMAGE_LOADER_WORKERS:
        return value
    return AUTO_IMAGE_LOADER_WORKERS


def resolve_image_loader_workers(value, logical_cpu_count: int | None) -> int:
    """設定値と論理CPU数から、このprocessで使うworker数を返す。"""
    normalized = normalize_image_loader_workers(value)
    if isinstance(normalized, int):
        return normalized
    if logical_cpu_count is None:
        return 3
    try:
        cpu_count = max(1, int(logical_cpu_count))
    except (TypeError, ValueError):
        return 3
    if cpu_count <= 4:
        return 1
    if cpu_count <= 8:
        return 2
    if cpu_count <= 16:
        return 3
    if cpu_count <= 24:
        return 4
    if cpu_count <= 32:
        return 5
    return 6
