"""言語・国コードと母語表示名。プラグインは import しない。アプリ言語には合わせない。"""
from __future__ import annotations

_LANGUAGE_HEAD = ("ja", "en")
_COUNTRY_HEAD = ("JP",)
_language_rows: tuple[tuple[str, str], ...] | None = None
_country_rows: tuple[tuple[str, str], ...] | None = None


def language_choices() -> tuple[tuple[str, str], ...]:
    global _language_rows
    if _language_rows is not None:
        return _language_rows
    from PySide6.QtCore import QLocale

    rows: dict[str, tuple[str, str]] = {}
    to_code = getattr(QLocale, "languageToCode", None)
    for language in QLocale.Language:
        if language in (QLocale.Language.AnyLanguage, getattr(QLocale.Language, "C", None)):
            continue
        if to_code is not None:
            code = str(to_code(language) or "").strip()
        else:
            code = str((QLocale(language).name() or "").split("_")[0]).strip()
        if not code or code in ("C", "und"):
            continue
        lowered = code.casefold()
        if lowered in rows:
            continue
        loc = QLocale(language)
        native = str(loc.nativeLanguageName() or "").strip()
        label = f"{code} - {native}" if native else code
        rows[lowered] = (code, label)
    ordered = _head_then_az(rows, _LANGUAGE_HEAD, key_is_lower=True)
    _language_rows = tuple(ordered)
    return _language_rows


def country_choices() -> tuple[tuple[str, str], ...]:
    global _country_rows
    if _country_rows is not None:
        return _country_rows
    from PySide6.QtCore import QLocale

    enum = getattr(QLocale, "Territory", None) or QLocale.Country
    any_value = getattr(enum, "AnyTerritory", None) or getattr(enum, "AnyCountry", None)
    to_code = getattr(QLocale, "territoryToCode", None) or getattr(QLocale, "countryToCode", None)
    rows: dict[str, tuple[str, str]] = {}
    for territory in enum:
        if any_value is not None and territory == any_value:
            continue
        if to_code is not None:
            code = str(to_code(territory) or "").strip()
        else:
            continue
        if not code or len(code) != 2:
            continue
        key = code.upper()
        if key in rows:
            continue
        loc = QLocale(QLocale.Language.AnyLanguage, QLocale.Script.AnyScript, territory)
        native = _native_country(loc)
        label = f"{key} - {native}" if native else key
        rows[key] = (key, label)
    ordered = _head_then_az(rows, _COUNTRY_HEAD, key_is_lower=False)
    _country_rows = tuple(ordered)
    return _country_rows


def _native_country(locale) -> str:
    for name in ("nativeTerritoryName", "nativeCountryName"):
        getter = getattr(locale, name, None)
        if getter is None:
            continue
        text = str(getter() or "").strip()
        if text:
            return text
    return ""


def _head_then_az(rows: dict, head: tuple[str, ...], key_is_lower: bool) -> list[tuple[str, str]]:
    used: set[str] = set()
    ordered: list[tuple[str, str]] = []
    for item in head:
        key = item.casefold() if key_is_lower else item.upper()
        pair = rows.get(key)
        if pair is None:
            continue
        ordered.append(pair)
        used.add(key)
    rest = sorted(
        ((key, pair) for key, pair in rows.items() if key not in used),
        key=lambda item: item[0].casefold(),
    )
    ordered.extend(pair for _key, pair in rest)
    return ordered
