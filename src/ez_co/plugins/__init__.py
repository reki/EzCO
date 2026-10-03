"""プラグイン契約の公開名とマネージャ取得をまとめる。"""
from ez_co.plugins.api import (
    BUILTIN_PROVIDER_ID,
    SKIP_PROVIDER_ID,
    FileKind,
    FormatSpec,
    make_provider_id,
    parse_provider_id,
)
from ez_co.plugins.manager import get_plugin_manager

__all__ = [
    "BUILTIN_PROVIDER_ID",
    "SKIP_PROVIDER_ID",
    "FileKind",
    "FormatSpec",
    "get_plugin_manager",
    "make_provider_id",
    "parse_provider_id",
]
