"""プラグイン ZIP のマニフェスト。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    api_version: int
    entry: str
    description: str = ""
    author: str = ""

    @property
    def entry_module(self) -> str:
        module, _sep, _cls = self.entry.partition(":")
        module = module.strip().replace("\\", "/")
        if module.endswith(".py"):
            module = module[: -len(".py")]
        return module.replace("/", ".")

    @property
    def entry_class(self) -> Optional[str]:
        _module, sep, cls = self.entry.partition(":")
        if not sep:
            return None
        return cls.strip() or None


def parse_manifest(data: Any) -> PluginManifest:
    if not isinstance(data, dict):
        raise ValueError("manifest must be an object")
    plugin_id = str(data.get("id") or "").strip()
    name = str(data.get("name") or "").strip()
    version = str(data.get("version") or "").strip()
    entry = str(data.get("entry") or "").strip()
    if not plugin_id:
        raise ValueError("manifest.id is required")
    if not name:
        raise ValueError("manifest.name is required")
    if not version:
        raise ValueError("manifest.version is required")
    if not entry:
        raise ValueError("manifest.entry is required")
    _module, _sep, cls = entry.partition(":")
    if not _sep or not cls.strip():
        raise ValueError("manifest.entry must be module:Class")
    try:
        api_version = int(data.get("api_version"))
    except (TypeError, ValueError) as exc:
        raise ValueError("manifest.api_version is required") from exc
    return PluginManifest(
        plugin_id=plugin_id,
        name=name,
        version=version,
        api_version=api_version,
        entry=entry,
        description=str(data.get("description") or ""),
        author=str(data.get("author") or ""),
    )
