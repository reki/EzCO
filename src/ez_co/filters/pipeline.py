"""公開 ID の pipe だけを順に適用する。台帳への一斉配布はしない。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

from PIL.Image import Image

from ez_co.filters.builtin import BUILTIN_FILTER_ID, is_basic_identity
from ez_co.filters.registry import FilterRegistry, get_filter_registry
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FilterContext:
    path: str
    page: int
    size: tuple[int, int]
    settings: Mapping[str, Any] = field(default_factory=dict)


def apply_pipe(
    image: Optional[Image],
    pipe: Optional[Sequence[str]],
    *,
    path: str = "",
    page: int = 1,
    builtin_settings: Optional[Mapping[str, Any]] = None,
    registry: Optional[FilterRegistry] = None,
) -> Optional[Image]:
    """pipe の公開 ID を台帳で引き、載っているものだけ process する。

    台帳にヒットしなければ同一オブジェクト。builtin:basic の identity だけでも copy しない。
    実効フィルターがあるときだけ working copy を1回作る。
    """
    if image is None:
        return None
    registry = registry or get_filter_registry()
    settings = dict(builtin_settings or {})
    records = []
    for item in pipe or ():
        public_id = str(item or "").strip()
        if not public_id:
            continue
        record = registry.get(public_id)
        if record is None:
            continue
        records.append(record)
    if not records:
        return image
    if len(records) == 1 and records[0].public_id == BUILTIN_FILTER_ID and is_basic_identity(settings):
        return image
    working = image.copy()
    for record in records:
        if record.public_id == BUILTIN_FILTER_ID and is_basic_identity(settings):
            continue
        context = FilterContext(
            path=str(path or ""),
            page=int(page or 1),
            size=working.size,
            settings=settings if record.public_id == BUILTIN_FILTER_ID else {},
        )
        try:
            result = record.process(working, context)
        except Exception as exc:
            logger.warning(get_log_text("filter_process_failed", filter_id=record.public_id, error=exc))
            continue
        if result is not None:
            working = result
    return working
