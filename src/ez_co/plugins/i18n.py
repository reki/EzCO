"""プラグイン向け get_text。プラグイン langs を優先し、無ければアプリの langs を使う。"""
from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ez_co.plugins.root import ZipPluginRoot
from ez_co.utils.language_manager import language_manager


def _lookup(data: Any, key: str) -> Optional[str]:
    """ドット区切りキーで文字列を取り出す。

    Args:
        data: 探索するオブジェクト。
        key: ドット区切りのキー。

    Returns:
        改行を戻した文字列。途中が無い、または文字列でなければ None。
    """
    value = data
    try:
        for part in key.split("."):
            value = value[part]
    except (KeyError, TypeError):
        # 途中のキーが無ければ None を返す。
        return None
    if not isinstance(value, str):
        return None
    return value.replace("\\n", "\n")


def _format_text(value: str, kwargs: dict) -> str:
    """kwargs があれば format し、失敗したら元の文字列を返す。

    Args:
        value: 整形する文字列。
        kwargs: format に渡す対応。

    Returns:
        整形後の文字列。kwargs が空、または失敗時は value。
    """
    if not kwargs:
        return value
    try:
        return value.format(**kwargs)
    except (KeyError, ValueError):
        # 整形できなければ元の文字列を返す。
        return value


def _resolved_language_codes() -> list[str]:
    """現在の言語コードに ja と en を足した探索順を返す。

    Returns:
        重複のない言語コード。system は実コードに置き換える。
    """
    current = language_manager.get_current_language()
    if current == "system":
        info = language_manager.available_languages.get("system") or {}
        current = str(info.get("code") or "ja")
    codes = [current]
    for fallback in ("ja", "en"):
        if fallback not in codes:
            codes.append(fallback)
    return codes


def expand_plugin_text(value, get_text: Callable[..., str]) -> str:
    """文字列全体が {key} のときだけ get_text し、それ以外はそのままにし、キーは trim しない。

    Args:
        value: 展開する値。None は空文字。
        get_text: キーから文字列を取る関数。

    Returns:
        展開後、または元の文字列。
    """
    text = "" if value is None else str(value)
    if len(text) < 3 or not text.startswith("{") or not text.endswith("}"):
        return text
    inner = text[1:-1]
    if not inner or "{" in inner or "}" in inner:
        return text
    return get_text(inner)


def _load_plugin_lang(root: ZipPluginRoot, lang_code: str) -> dict:
    """プラグインの言語 JSON を読み、root にキャッシュする。

    Args:
        root: プラグインルート。
        lang_code: 言語コード。

    Returns:
        読めた dict。無ければ空。
    """
    cache = root._lang_cache
    if lang_code in cache:
        return cache[lang_code]
    data: dict = {}
    for candidate in (
        f"resources/langs/{lang_code}.json",
        f"langs/{lang_code}.json",
        f"src/langs/{lang_code}.json",
    ):
        if not root.exists(candidate):
            continue
        try:
            loaded = json.loads(root.read_bytes(candidate).decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            # 言語ファイルを読めなければ次の候補へ進む。
            continue
        if isinstance(loaded, dict):
            data = loaded
            break
    cache[lang_code] = data
    return data


def make_plugin_get_text(root: ZipPluginRoot) -> Callable[..., str]:
    """プラグイン言語を優先し、無ければアプリ文言を使う get_text を作る。

    Args:
        root: プラグインルート。

    Returns:
        key と kwargs を受ける関数。
    """
    def get_text(key: str, **kwargs) -> str:
        """キーをプラグイン言語から探し、無ければアプリ文言を返す。

        Args:
            key: 文言キー。
            kwargs: format に渡す値。

        Returns:
            見つかった文字列。
        """
        for lang_code in _resolved_language_codes():
            plugin_value = _lookup(_load_plugin_lang(root, lang_code), key)
            if plugin_value is not None:
                return _format_text(plugin_value, kwargs)
        return language_manager.get_text(key, **kwargs)

    return get_text
