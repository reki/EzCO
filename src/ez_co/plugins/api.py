"""ホストが定義するプラグイン契約。プラグイン側はこのモジュールを import しない。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union


# ホスト API の版。
HOST_API_VERSION = 1
# 本体が担当するときの提供元 ID。
BUILTIN_PROVIDER_ID = "builtin"
# 担当プラグインを使わないときの提供元 ID。
SKIP_PROVIDER_ID = "none"


def make_provider_id(plugin_id: str, version: str) -> str:
    """設定・解決用のキーで、形式は id(ver:version)。

    Args:
        plugin_id: プラグイン ID。
        version: バージョン文字列。

    Returns:
        id(ver:version) 形式の文字列。
    """
    return f"{plugin_id}(ver:{version})"


def parse_provider_id(value: str) -> tuple[str, Optional[str]]:
    """'com.example(ver:1.0.0)' を plugin_id と version に分け、旧形式も読む。

    Args:
        value: 分解するキー。

    Returns:
        plugin_id と version。version が無ければ None。空、builtin、none は ID のまま。
    """
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
    """バージョン文字列を並び替え用のキーにする。

    Args:
        version: 比較するバージョン。

    Returns:
        packaging で解釈できれば (0, Version)、できなければ (1, 文字列)。
    """
    try:
        from packaging.version import Version
        return (0, Version(str(version)))
    except Exception:
        # packaging で解釈できなければ文字列のまま並べる。
        return (1, str(version or ""))


class FileKind(Enum):
    """ファイルの種別。"""

    # 画像ファイルの種別。
    IMAGE = "image"
    # アーカイブファイルの種別。
    ARCHIVE = "archive"


@dataclass(frozen=True)
class FormatSpec:
    """担当する拡張子と種別の組。"""

    extension: str
    kind: FileKind


@dataclass(frozen=True)
class EntryData:
    """アーカイブ内エントリの名前とバイト列。"""

    name: str
    data: bytes


def normalize_extension(extension: str) -> str:
    """拡張子を小文字のドット付きに揃える。

    Args:
        extension: 揃える拡張子。

    Returns:
        先頭にドットを付けた小文字。空なら空文字。
    """
    ext = (extension or "").strip().lower()
    if not ext:
        return ""
    if not ext.startswith("."):
        ext = "." + ext
    return ext


def parse_file_kind(value: Union[str, FileKind]) -> Optional[FileKind]:
    """文字列または FileKind を FileKind にする。

    Args:
        value: image、img、archive、arch、または FileKind。

    Returns:
        対応する FileKind。解釈できなければ None。
    """
    if isinstance(value, FileKind):
        return value
    text = str(value or "").strip().lower()
    if text in ("image", "img"):
        return FileKind.IMAGE
    if text in ("archive", "arch"):
        return FileKind.ARCHIVE
    return None


def _ext_list(raw) -> list:
    """拡張子指定をリストにする。

    Args:
        raw: 単一値、list、tuple、または None。

    Returns:
        要素のリスト。None なら空。
    """
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if raw is None:
        return []
    return [raw]


def normalize_formats(raw) -> list[FormatSpec]:
    """担当形式の指定を、重複しない FormatSpec の列にする。

    Args:
        raw: FormatSpec、組、dict の列。空なら空の列。

    Returns:
        拡張子と種別の組が重複しない FormatSpec。
    """
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
