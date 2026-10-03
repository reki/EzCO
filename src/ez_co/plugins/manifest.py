"""プラグイン ZIP のマニフェスト。"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Optional

from ez_co.plugins.api import FormatSpec, normalize_formats

# 権限が空のときの読み取り専用 dict。
_EMPTY_PERMISSIONS: Mapping[str, bool] = MappingProxyType({})
# マニフェストで受け付ける権限名。
KNOWN_PERMISSIONS = frozenset({"inactive_callback", "filter"})
# 既知の権限名。公開定数と同じ集合。
_KNOWN_PERMISSIONS = KNOWN_PERMISSIONS


@dataclass(frozen=True)
class PluginManifest:
    """manifest.json から読んだプラグインの宣言。"""

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
        """entry のモジュール部分をドット区切りで返す。

        Returns:
            コロンより前のモジュール名。末尾の .py は除く。
        """
        module, _sep, _cls = self.entry.partition(":")
        module = module.strip().replace("\\", "/")
        if module.endswith(".py"):
            module = module[: -len(".py")]
        return module.replace("/", ".")

    @property
    def entry_class(self) -> Optional[str]:
        """entry のクラス名を返す。

        Returns:
            コロンより後のクラス名。無ければ None。
        """
        _module, sep, cls = self.entry.partition(":")
        if not sep:
            return None
        return cls.strip() or None


def parse_permissions(raw: Any) -> Mapping[str, bool]:
    """本体が読む既知のマニフェスト権限だけを残し、未知キーは権限にせず、既知キーの値は JSON bool のみとする。

    Args:
        raw: permissions オブジェクト。None なら空。

    Returns:
        既知キーだけの読み取り専用対応。空なら空の対応。

    Raises:
        ValueError: オブジェクトでない、または既知キーの値が bool でないとき。
    """
    if raw is None:
        return _EMPTY_PERMISSIONS
    if not isinstance(raw, Mapping):
        raise ValueError("manifest.permissions must be an object")
    granted = {}
    for key, value in raw.items():
        name = str(key or "").strip()
        if name not in _KNOWN_PERMISSIONS:
            continue
        if not isinstance(value, bool):
            raise ValueError(f"manifest.permissions.{name} must be a bool")
        granted[name] = value
    if not granted:
        return _EMPTY_PERMISSIONS
    return MappingProxyType(granted)


def parse_formats(raw: Any) -> tuple[FormatSpec, ...]:
    """本体が読む担当形式を返し、解釈できない要素だけなら失敗する。

    Args:
        raw: formats の配列。None なら空。

    Returns:
        正規化した FormatSpec。

    Raises:
        ValueError: 配列でない、または有効な要素が無いとき。
    """
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ValueError("manifest.formats must be an array")
    specs = tuple(normalize_formats(raw))
    if raw and not specs:
        raise ValueError("manifest.formats has no valid entries")
    return specs


def parse_sidebar(raw: Any) -> bool:
    """sidebar 宣言を bool として読む。

    Args:
        raw: 宣言値。None なら False。

    Returns:
        宣言された bool。

    Raises:
        ValueError: bool でないとき。
    """
    if raw is None:
        return False
    if not isinstance(raw, bool):
        raise ValueError("manifest.sidebar must be a bool")
    return raw


def parse_manifest(data: Any) -> PluginManifest:
    """manifest の必須項目を PluginManifest にする。

    Args:
        data: manifest のオブジェクト。

    Returns:
        検証済みの PluginManifest。

    Raises:
        ValueError: オブジェクトでない、必須が空、entry が module:Class でない、または api_version が整数でないとき。
    """
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
        # api_version を整数にできなければ ValueError にして返す。
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
