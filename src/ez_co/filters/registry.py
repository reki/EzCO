"""表示フィルターの台帳。登録の有無だけを持つ。画素処理は apply_pipe が呼ぶ。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Optional

from PIL.Image import Image


@dataclass(frozen=True)
class FilterRecord:
    """台帳に載る表示フィルター1件。"""
    public_id: str
    plugin_id: str
    local_id: str
    title: str
    process: Callable[[Image, object], Image]
    has_settings: bool = False


class FilterRegistry:
    """公開 ID から表示フィルターを引く台帳。"""

    def __init__(self) -> None:
        """空の台帳を作る。"""
        self._records: dict[str, FilterRecord] = {}

    def register(self, record: FilterRecord) -> None:
        """公開 ID が空でなければ、フィルターをその ID で登録する。

        Args:
            record: 台帳へ載せるフィルター。
        """
        public_id = str(record.public_id or "").strip()
        if not public_id:
            return
        self._records[public_id] = record

    def unregister(self, public_id: str) -> None:
        """公開 ID の登録を外す。

        Args:
            public_id: 外す公開 ID。
        """
        self._records.pop(str(public_id or "").strip(), None)

    def unregister_plugin(self, plugin_id: str) -> None:
        """プラグイン ID が空でなければ、一致する登録を外す。

        Args:
            plugin_id: 外すプラグイン ID。
        """
        key = str(plugin_id or "")
        if not key:
            return
        for public_id in [item for item, record in self._records.items() if record.plugin_id == key]:
            self._records.pop(public_id, None)

    def get(self, public_id: str) -> Optional[FilterRecord]:
        """公開 ID の登録を返す。

        Args:
            public_id: 引く公開 ID。

        Returns:
            登録。無ければ None。
        """
        return self._records.get(str(public_id or "").strip())

    def iter(self) -> Iterator[FilterRecord]:
        """登録を順に返す。

        Returns:
            台帳に入っているフィルター。
        """
        return iter(self._records.values())


# プロセスで共有するフィルター台帳
_REGISTRY = FilterRegistry()


def get_filter_registry() -> FilterRegistry:
    """共有のフィルター台帳を返す。

    Returns:
        プロセス内で共有している台帳。
    """
    return _REGISTRY


def reset_filter_registry() -> None:
    """共有のフィルター台帳を空の台帳に差し替える。"""
    global _REGISTRY
    _REGISTRY = FilterRegistry()
