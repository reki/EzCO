"""Python codecs の正規名一覧。プラグインは import しない。"""
from __future__ import annotations

import codecs
from encodings.aliases import aliases

# 文字コード一覧の先頭に置く正規名。
_HEAD = ("utf-8", "cp932", "shift_jis", "latin_1")
# 解決済み文字コード名のキャッシュ。未構築は None。
_cached: tuple[str, ...] | None = None


def charset_names() -> tuple[str, ...]:
    """codecs が解決できる文字コードの正規名を、utf-8 などを先にして返す。

    Returns:
        正規名のタプル。二度目以降はキャッシュ。
    """
    global _cached
    if _cached is not None:
        return _cached
    found: set[str] = set()
    candidates = set(aliases)
    candidates.update(aliases.values())
    candidates.update(_HEAD)
    for alias in candidates:
        try:
            found.add(codecs.lookup(str(alias).replace("_", "-")).name)
        except LookupError:
            # ハイフン名で解決できなければ、区切りを戻して試す。
            try:
                found.add(codecs.lookup(str(alias)).name)
            except LookupError:
                # どちらでも解決できなければその候補を捨てる。
                continue
    head: list[str] = []
    seen: set[str] = set()
    for name in _HEAD:
        try:
            codecs.lookup(name)
        except LookupError:
            # 先頭候補が解決できなければ一覧に入れない。
            continue
        if name in seen:
            continue
        seen.add(name)
        head.append(name)
    rest = sorted(item for item in found if item not in seen)
    _cached = tuple(head + rest)
    return _cached


def charset_choices() -> tuple[tuple[str, str], ...]:
    """文字コード名を choice 用の値とラベルにする。

    Returns:
        値とラベルが同じ組のタプル。
    """
    return tuple((name, name) for name in charset_names())
