"""プラグイン ZIP のマニフェスト。"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Optional

from ez_co.plugins.api import FormatSpec, normalize_formats

_EMPTY_PERMISSIONS: Mapping[str, bool] = MappingProxyType({})
_KNOWN_PERMISSIONS = frozenset({"inactive_callback"})


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    api_version: int
    entry: str
    description: str = ""
    author: str = ""
    permissions: Mapping[str, bool] = field(default=_EMPTY_PERMISSIONS, hash=False)
    formats: tuple[FormatSpec, ...] = ()
    sidebar: bool = False

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


def parse_permissions(raw: Any) -> Mapping[str, bool]:
    """本体が読む既知のマニフェスト権限。未知キーは権限にならない。"""
    if not isinstance(raw, Mapping):
        return _EMPTY_PERMISSIONS
    granted = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if name not in _KNOWN_PERMISSIONS:
            continue
        granted[name] = bool(value)
    if not granted:
        return _EMPTY_PERMISSIONS
    return MappingProxyType(granted)


def parse_formats(raw: Any) -> tuple[FormatSpec, ...]:
    """本体が読む担当形式。解釈できない要素だけなら失敗。"""
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("manifest.formats must be an array")
    specs = tuple(normalize_formats(raw))
    if raw and not specs:
        raise ValueError("manifest.formats has no valid entries")
    return specs


def parse_sidebar(raw: Any) -> bool:
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise ValueError("manifest.sidebar must be a bool")
    return raw


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
        permissions=parse_permissions(data.get("permissions")),
        formats=parse_formats(data.get("formats")),
        sidebar=parse_sidebar(data.get("sidebar")),
    )
