"""Python codecs の正規名一覧。プラグインは import しない。"""
from __future__ import annotations

import codecs
from encodings.aliases import aliases

_HEAD = ("utf-8", "cp932", "shift_jis", "latin_1")
_cached: tuple[str, ...] | None = None


def charset_names() -> tuple[str, ...]:
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
            try:
                found.add(codecs.lookup(str(alias)).name)
            except LookupError:
                continue
    head: list[str] = []
    seen: set[str] = set()
    for name in _HEAD:
        try:
            codecs.lookup(name)
        except LookupError:
            continue
        if name in seen:
            continue
        seen.add(name)
        head.append(name)
    rest = sorted(item for item in found if item not in seen)
    _cached = tuple(head + rest)
    return _cached


def charset_choices() -> tuple[tuple[str, str], ...]:
    return tuple((name, name) for name in charset_names())
