"""ホストが定義するプラグイン契約。プラグイン側はこのモジュールを import しない。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


HOST_API_VERSION = 1
BUILTIN_PROVIDER_ID = "builtin"
SKIP_PROVIDER_ID = "none"


def make_provider_id(plugin_id: str, version: str) -> str:
    """設定・解決用のキー。形式は id(ver:version)。"""
    return f"{plugin_id}(ver:{version})"


def parse_provider_id(value: str) -> tuple[str, Optional[str]]:
    """'com.example(ver:1.0.0)' → ('com.example', '1.0.0')。旧形式も読む。"""
    text = str(value or "").strip()
    if not text or text in (BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID):
        return text, None
    for separator in ("(ver:", "+("):
        if separator in text and text.endswith(")"):
            plugin_id, version = text.rsplit(separator, 1)
            plugin_id = plugin_id.strip()
            version = version[:-1].strip()
            if plugin_id:
                return plugin_id, version or None
    return text, None


def version_sort_key(version: str):
    try:
        from packaging.version import Version
        return (0, Version(str(version)))
    except Exception:
        return (1, str(version or ""))


class FileKind(Enum):
    IMAGE = "image"
    ARCHIVE = "archive"


@dataclass(frozen=True)
class FormatSpec:
    extension: str
    kind: FileKind


@dataclass(frozen=True)
class EntryData:
    name: str
    data: bytes


def normalize_extension(extension: str) -> str:
    ext = (extension or "").strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def parse_file_kind(value: Union[str, FileKind]) -> Optional[FileKind]:
    if isinstance(value, FileKind):
        return value
    text = str(value or "").strip().lower()
    if text in ("image", "img"):
        return FileKind.IMAGE
    if text in ("archive", "arch"):
        return FileKind.ARCHIVE
    return None


def _ext_list(raw) -> list:
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if raw is None:
        return []
    return [raw]


def normalize_formats(raw) -> list[FormatSpec]:
    formats: list[FormatSpec] = []
    seen: set[tuple[str, FileKind]] = set()
    if not raw:
        return formats
    for item in raw:
        extensions = []
        kind = None
        if isinstance(item, FormatSpec):
            extensions = [item.extension]
            kind = item.kind
        elif isinstance(item, (tuple, list)) and len(item) >= 2:
            first = item[0]
            kind = parse_file_kind(item[1])
            if isinstance(first, (list, tuple)):
                extensions = list(first)
            else:
                extensions = [first]
        elif isinstance(item, dict):
            extensions = _ext_list(item.get("ext"))
            kind = parse_file_kind(item.get("kind"))
        if kind is None:
            continue
        for extension in extensions:
            normalized = normalize_extension(str(extension) if extension is not None else "")
            if not normalized:
                continue
            key = (normalized, kind)
            if key in seen:
                continue
            seen.add(key)
            formats.append(FormatSpec(normalized, kind))
    return formats
