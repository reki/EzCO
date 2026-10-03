"""画像読込worker設定を正規化し、実worker数へ解決する。"""
from __future__ import annotations


# ワーカー数を自動にする設定値
AUTO_IMAGE_LOADER_WORKERS = "auto"
# ワーカー数の下限
MIN_IMAGE_LOADER_WORKERS = 1
# ワーカー数の上限
MAX_IMAGE_LOADER_WORKERS = 8


def normalize_image_loader_workers(value) -> str | int:
    """保存値を ``"auto"`` または1～8の整数へ正規化する。

    Args:
        value: 保存されている worker 設定

    Returns:
        auto、または 1 から 8 の整数。解釈できなければ auto
    """
    if isinstance(value, str):
        stripped = value.strip().lower()
        if stripped == AUTO_IMAGE_LOADER_WORKERS:
            return AUTO_IMAGE_LOADER_WORKERS
        try:
            value = int(stripped)
        except ValueError:
            # 整数にできなければ自動設定を返す
            return AUTO_IMAGE_LOADER_WORKERS
    if isinstance(value, bool):
        return AUTO_IMAGE_LOADER_WORKERS
    if isinstance(value, int) and MIN_IMAGE_LOADER_WORKERS <= value <= MAX_IMAGE_LOADER_WORKERS:
        return value
    return AUTO_IMAGE_LOADER_WORKERS


def resolve_image_loader_workers(value, logical_cpu_count: int | None) -> int:
    """設定値と論理CPU数から、このprocessで使うworker数を返す。

    Args:
        value: 保存されている worker 設定
        logical_cpu_count: 論理CPU数

    Returns:
        このプロセスで使う worker 数
    """
    normalized = normalize_image_loader_workers(value)
    if isinstance(normalized, int):
        return normalized
    if logical_cpu_count is None:
        return 3
    try:
        cpu_count = max(1, int(logical_cpu_count))
    except (TypeError, ValueError):
        # CPU 数を整数にできなければ 3 を返す
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
