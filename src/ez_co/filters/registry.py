"""表示フィルターの台帳。登録の有無だけを持つ。画素処理は apply_pipe が呼ぶ。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from PIL.Image import Image


@dataclass(frozen=True)
class FilterRecord:
    public_id: str
    plugin_id: str
    local_id: str
    title: str
    process: Callable[[Image, object], Image]
    has_settings: bool = False


class FilterRegistry:
    def __init__(self) -> None:
        self._records: dict[str, FilterRecord] = {}

    def register(self, record: FilterRecord) -> None:
        public_id = str(record.public_id or "").strip()
        if not public_id:
            return
        self._records[public_id] = record

    def unregister(self, public_id: str) -> None:
        self._records.pop(str(public_id or "").strip(), None)

    def unregister_plugin(self, plugin_id: str) -> None:
        key = str(plugin_id or "")
        if not key:
            return
        for public_id in [item for item, record in self._records.items() if record.plugin_id == key]:
            self._records.pop(public_id, None)

    def get(self, public_id: str) -> Optional[FilterRecord]:
        return self._records.get(str(public_id or "").strip())

    def iter(self) -> Iterator[FilterRecord]:
        return iter(self._records.values())


_REGISTRY = FilterRegistry()


def get_filter_registry() -> FilterRegistry:
    return _REGISTRY


def reset_filter_registry() -> None:
    global _REGISTRY
    _REGISTRY = FilterRegistry()
