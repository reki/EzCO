"""論理CPU数と物理メモリ量から画像読み込み設定の推奨値を決める。"""
from __future__ import annotations

from dataclasses import dataclass

from ez_co.utils.image_loader_workers import (
    AUTO_IMAGE_LOADER_WORKERS,
    resolve_image_loader_workers,
)

# 27条件matrixで通常素材・高解像度素材とも最小latencyだった窓。
RECOMMENDED_PREFETCH_PAGES = 5
# 性能境界ではなく、複数タブでcacheが線形に増えることへの安全境界。
MEMORY_LIMIT_RAM_THRESHOLD_BYTES = 16 * 1024**3
SAFE_MEMORY_LIMIT = "256MB"
LARGE_MEMORY_LIMIT = "512MB"


@dataclass(frozen=True)
class ImageLoadingRecommendation:
    """このPCへ勧める画像読み込み設定。"""

    memory_limit: str
    prefetch_pages: int
    image_loader_workers: str


def recommend_image_loading_settings(
    logical_cpu_count: int | None,
    physical_memory_bytes: int | None,
) -> ImageLoadingRecommendation:
    """RAM量から安全側のcache上限を選ぶ。1GBは自動では勧めない。"""
    if (
        physical_memory_bytes is not None
        and physical_memory_bytes >= MEMORY_LIMIT_RAM_THRESHOLD_BYTES
    ):
        memory_limit = LARGE_MEMORY_LIMIT
    else:
        memory_limit = SAFE_MEMORY_LIMIT
    return ImageLoadingRecommendation(
        memory_limit=memory_limit,
        prefetch_pages=RECOMMENDED_PREFETCH_PAGES,
        image_loader_workers=AUTO_IMAGE_LOADER_WORKERS,
    )


def auto_effective_workers(logical_cpu_count: int | None) -> int:
    """autoを選んだときの実worker数。推奨labelとbenchmarkで基準を揃える。"""
    return resolve_image_loader_workers(
        AUTO_IMAGE_LOADER_WORKERS,
        logical_cpu_count,
    )


def apply_recommendation(config, recommendation=None) -> ImageLoadingRecommendation:
    """新規設定を作るときだけ、cacheの3キーを推奨値で埋める。"""
    if recommendation is None:
        from ez_co.utils.system_resources import (
            logical_cpu_count,
            physical_memory_bytes,
        )

        recommendation = recommend_image_loading_settings(
            logical_cpu_count(),
            physical_memory_bytes(),
        )
    config.cache["memory_limit"] = recommendation.memory_limit
    config.cache["prefetch_pages"] = recommendation.prefetch_pages
    config.cache["image_loader_workers"] = recommendation.image_loader_workers
    return recommendation
