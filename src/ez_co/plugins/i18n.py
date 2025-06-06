"""プラグイン向け get_text。プラグイン langs を優先し、無ければアプリの langs を使う。"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ez_co.plugins.root import ZipPluginRoot
from ez_co.utils.language_manager import language_manager


def _lookup(data: Any, key: str) -> Optional[str]:
    value = data
    try:
        for part in key.split("."):
            value = value[part]
    except (KeyError, TypeError):
        return None
    if not isinstance(value, str):
        return None
    return value.replace("\\n", "\n")


def _format_text(value: str, kwargs: dict) -> str:
    if not kwargs:
        return value
    try:
        return value.format(**kwargs)
    except (KeyError, ValueError):
        return value


def _resolved_language_codes() -> list[str]:
    current = language_manager.get_current_language()
    if current == "system":
        info = language_manager.available_languages.get("system") or {}
        current = str(info.get("code") or "ja")
    codes = [current]
    for fallback in ("ja", "en"):
        if fallback not in codes:
            codes.append(fallback)
    return codes


def _load_plugin_lang(root: ZipPluginRoot, lang_code: str) -> dict:
    cache = root._lang_cache
    if lang_code in cache:
        return cache[lang_code]
    data: dict = {}
    for candidate in (f"langs/{lang_code}.json", f"src/langs/{lang_code}.json"):
        if not root.exists(candidate):
            continue
        try:
            loaded = json.loads(root.read_bytes(candidate).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(loaded, dict):
            data = loaded
            break
    cache[lang_code] = data
    return data


def make_plugin_get_text(root: ZipPluginRoot) -> Callable[..., str]:
    def get_text(key: str, **kwargs) -> str:
        for lang_code in _resolved_language_codes():
            plugin_value = _lookup(_load_plugin_lang(root, lang_code), key)
            if plugin_value is not None:
                return _format_text(plugin_value, kwargs)
        return language_manager.get_text(key, **kwargs)

    return get_text
