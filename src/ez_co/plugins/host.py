"""プラグインからホストのダイアログ／アクションを呼ぶ口。

プラグインは ez_co を import せず、注入された入口を使う。
各プラグインには plugin_id 固定の ScopedPluginHost が渡る。
"""
from __future__ import annotations

import copy
import json
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any, Callable, Optional

from ez_co.filters.registry import FilterRecord, get_filter_registry
from ez_co.plugins.api import FormatSpec, normalize_formats
from ez_co.plugins.config_schema import parse_config_json
from ez_co.plugins.i18n import expand_plugin_text
from ez_co.plugins.manifest import parse_permissions
from ez_co.plugins.root import resource_relative
from ez_co.utils.language_manager import get_log_text, get_text, language_manager

logger = logging.getLogger(__name__)

# プラグインへ読ませるアプリ設定のセクション。
_APP_CONFIG_ALLOW = ("language", "viewer", "cache", "ui_font")
# プラグイン設定として受け付ける型名。
_CONFIG_TYPES = (
    "bool",
    "string",
    "int",
    "float",
    "int_range",
    "float_range",
    "color",
    "date",
    "datetime",
    "choice",
    "font",
    "path",
    "password",
    "charset",
    "language",
    "country",
)
# 設定ダイアログで即時保存できる数値型。
_SYNC_CONFIG_TYPES = ("int", "float", "int_range", "float_range")
# ドロップダウンで出す設定型。
_DROPDOWN_CONFIG_TYPES = ("choice", "charset", "language", "country")
# 数値として扱う設定型。
_NUMERIC_CONFIG_TYPES = ("int", "float", "int_range", "float_range")
# 色が解釈できないときの黒。
_COLOR_FALLBACK = "#000000"


# インスタンス生成中の phase。
_PHASE_INIT = "init"
# load 実行中の phase。
_PHASE_LOAD = "load"
# 読み込み後、setup 前の phase。
_PHASE_IDLE = "idle"
# setup 実行中の phase。
_PHASE_SETUP = "setup"
# 有効化後の phase。
_PHASE_ACTIVE = "active"
# 言語変更コールバック中の phase。
_PHASE_LANGUAGE = "language"
# setup 中にだけ呼べる登録メソッド。
_UI_REGISTER = frozenset(
    {
        "register_sidebar",
        "unregister_sidebar",
        "register_config_sidebar",
        "required_setting_sidebar",
        "register_action",
        "unregister_action",
        "register_filter",
        "unregister_filter",
        "on",
        "off",
    }
)


class PluginRegistrationDenied(Exception):
    """マニフェストに無い register、または phase 違いの register。このプラグインは使わない。"""

    def __init__(self, plugin_id: str, log_key: str, ui_key: str = "ui.plugin_register_not_permitted"):
        """拒否理由のキーと画面用の文言を保持する。

        Args:
            plugin_id: 拒否されたプラグイン ID。
            log_key: ログ用の文言キー。
            ui_key: 例外メッセージに使う画面文言キー。
        """
        self.plugin_id = plugin_id
        self.log_key = log_key
        super().__init__(get_text(ui_key))


def make_plugin_action_id(plugin_id: str, action_id: str) -> str:
    """プラグインアクションの公開 ID を作る。

    Args:
        plugin_id: プラグイン ID。
        action_id: プラグイン内のアクション ID。

    Returns:
        plugin:{plugin_id}:{action_id}。
    """
    return f"plugin:{plugin_id}:{action_id}"


def make_plugin_filter_id(plugin_id: str, filter_id: str) -> str:
    """プラグインフィルターの公開 ID を作る。

    Args:
        plugin_id: プラグイン ID。
        filter_id: プラグイン内のフィルター ID。

    Returns:
        plugin:{plugin_id}:{filter_id}。
    """
    return f"plugin:{plugin_id}:{filter_id}"


def normalize_local_filter_id(filter_id) -> str:
    """フィルターのローカル ID を空または使える名前にする。

    Args:
        filter_id: 検査する ID。

    Returns:
        空白を除いた名前。空、またはコロンを含むなら空文字。
    """
    name = str(filter_id or "").strip()
    if not name or ":" in name:
        return ""
    return name


def make_sidebar_action_id(plugin_id: str, sidebar_id: str) -> str:
    """サイドバー表示切替アクションの公開 ID を作る。

    Args:
        plugin_id: プラグイン ID。
        sidebar_id: サイドバー ID。

    Returns:
        plugin:{plugin_id}:sidebar:{sidebar_id}。
    """
    return f"plugin:{plugin_id}:sidebar:{sidebar_id}"


def normalize_action_aliases(aliases) -> tuple[str, ...]:
    """エイリアスを空でない重複なしの組にする。

    Args:
        aliases: 文字列、または文字列の列。None なら空。

    Returns:
        順序を保ったエイリアスの組。
    """
    if aliases is None:
        return ()
    if isinstance(aliases, str):
        aliases = (aliases,)
    seen = []
    for item in aliases:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        seen.append(name)
    return tuple(seen)


# 引用符でまとめると langs missing がキー名とみなす。
_TITLE_PLACEHOLDER = "{" + "title" + "}"


def _sidebar_toggle_template(file_path) -> str:
    """言語ファイルからサイドバー切替ラベルの雛形を読む。

    Args:
        file_path: 言語 JSON のパス。

    Returns:
        ui.plugin_sidebar_toggle の文字列。無ければ空文字。
    """
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, TypeError, ValueError, AttributeError):
        # 言語ファイルを読めなければ空文字を返す。
        return ""
    ui = data.get("ui") if isinstance(data, dict) else None
    if not isinstance(ui, dict):
        return ""
    template = ui.get("plugin_sidebar_toggle")
    return template if isinstance(template, str) else ""


def _sidebar_toggle_affixes() -> tuple[tuple[str, str], ...]:
    """言語ファイルにある切替ラベルの前後の文言を集める。

    Returns:
        長いものから順の (接頭辞, 接尾辞)。system は除く。
    """
    affixes: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for code, info in language_manager.available_languages.items():
        if code == "system":
            continue
        file_path = info.get("file")
        if file_path is None:
            continue
        template = _sidebar_toggle_template(file_path)
        if template.count(_TITLE_PLACEHOLDER) != 1:
            continue
        prefix, suffix = template.split(_TITLE_PLACEHOLDER, 1)
        if not prefix and not suffix:
            continue
        key = (prefix.casefold(), suffix.casefold())
        if key in seen:
            continue
        seen.add(key)
        affixes.append((prefix, suffix))
    affixes.sort(key=lambda item: len(item[0]) + len(item[1]), reverse=True)
    return tuple(affixes)


def _strip_folded_edge(name: str, edge: str, *, prefix: bool) -> str:
    """名前の端が edge と大文字小文字を無視して一致すれば、その部分を外す。

    Args:
        name: 対象の文字列。
        edge: 外す端の文字列。
        prefix: True なら先頭、False なら末尾。

    Returns:
        外したあとの文字列。一致しなければ name のまま。
    """
    if not edge or len(name) <= len(edge):
        return name
    piece = name[: len(edge)] if prefix else name[-len(edge) :]
    if piece.casefold() != edge.casefold():
        return name
    return name[len(edge) :] if prefix else name[: -len(edge)]


def sidebar_title_stem(title: str) -> str:
    """切替ラベルの前後を除いたサイドバー名にする。

    Args:
        title: 表示タイトル。

    Returns:
        接頭辞と接尾辞を除いた名前。
    """
    name = str(title or "").strip()
    affixes = _sidebar_toggle_affixes()
    changed = True
    while changed and name:
        changed = False
        for prefix, suffix in affixes:
            updated = _strip_folded_edge(name, suffix, prefix=False)
            updated = _strip_folded_edge(updated, prefix, prefix=True).strip()
            if updated != name:
                name = updated
                changed = True
                break
    return name


def sidebar_toggle_label(title: str) -> str:
    """サイドバー名から切替アクションのラベルを作る。

    Args:
        title: 表示タイトル。

    Returns:
        ui.plugin_sidebar_toggle に渡したラベル。空なら sidebar。
    """
    stem = sidebar_title_stem(title) or str(title or "").strip() or "sidebar"
    return get_text("ui.plugin_sidebar_toggle", title=stem)


def normalize_local_action_id(action_id) -> str:
    """アクションのローカル ID を空または使える名前にする。

    Args:
        action_id: 検査する ID。

    Returns:
        空白を除いた名前。空、sidebar、またはコロンを含むなら空文字。
    """
    name = str(action_id or "").strip()
    if not name or name == "sidebar" or ":" in name:
        return ""
    return name


@dataclass(frozen=True)
class PluginAction:
    """登録済みアクションの公開 ID、ラベル、コールバック。"""

    plugin_id: str
    local_id: str
    public_id: str
    label: str
    callback: Callable
    kind: str = "custom"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfigField:
    """プラグイン設定の1項目。"""

    key: str
    value_type: str
    default: Any = None
    label: str = ""
    description: str = ""
    choices: tuple[tuple[str, str], ...] = ()
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: Optional[float] = None
    path_kind: str = "file"
    path_filter: str = ""
    sync: bool = False
    reload: bool = False
    multiple: bool = False
    suffix: str = ""
    required: bool = False
    enum_type: Optional[type] = None


def normalize_config_type(value_type) -> str:
    """設定の型名を既知の種別に揃える。

    Args:
        value_type: プラグインが渡した型名。

    Returns:
        既知の種別名。未知は string。
    """
    name = str(value_type or "string").strip().lower()
    if name in ("bool", "boolean"):
        return "bool"
    if name in ("int_range", "integer_range"):
        return "int_range"
    if name in ("float_range", "double_range"):
        return "float_range"
    if name in ("int", "integer"):
        return "int"
    if name in ("float", "double", "number"):
        return "float"
    if name in ("color", "colour"):
        return "color"
    if name == "date":
        return "date"
    if name in ("datetime", "timestamp"):
        return "datetime"
    if name in ("choice", "enum", "select"):
        return "choice"
    if name in ("font", "font_family"):
        return "font"
    if name in ("path", "filepath", "file_path"):
        return "path"
    if name in ("password", "secret"):
        return "password"
    if name == "charset":
        return "charset"
    if name == "language":
        return "language"
    if name == "country":
        return "country"
    return "string"


def normalize_path_kind(path_kind) -> str:
    """パス項目がファイルかディレクトリかを揃える。

    Args:
        path_kind: file または directory 系の名前。

    Returns:
        directory または file。
    """
    name = str(path_kind or "file").strip().lower()
    if name in ("directory", "folder", "dir"):
        return "directory"
    return "file"


def config_field_syncs(field: ConfigField) -> bool:
    """sync が有効な数値項目なら True。

    Args:
        field: 判定する項目。

    Returns:
        sync が立っていて int、float、int_range、float_range なら True。
    """
    return bool(field.sync) and field.value_type in _SYNC_CONFIG_TYPES


def config_field_reloads(field: ConfigField) -> bool:
    """sync 付きの数値項目で reload が有効なら True。

    Args:
        field: 判定する項目。

    Returns:
        即時保存かつ再読み込み対象なら True。
    """
    return config_field_syncs(field) and bool(field.reload)


def config_should_reload(fields) -> bool:
    """項目のどれかが再読み込み対象なら True。

    Args:
        fields: 判定する項目の列。

    Returns:
        1つでも reload 対象なら True。
    """
    return any(config_field_reloads(field) for field in fields)


def _parse_bound_number(value, as_int: bool):
    """範囲の端や刻みを数値にする。

    Args:
        value: 解釈する値。空や bool は対象外。
        as_int: True なら整数、False なら浮動小数。

    Returns:
        解釈した数値。できなければ None。
    """
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        if as_int:
            if isinstance(value, int):
                return int(value)
            return int(float(value))
        return float(value)
    except (TypeError, ValueError):
        # 数値にできなければ None を返す。
        return None


def normalize_range_bounds(value_type, minimum=None, maximum=None, step=None):
    """範囲の下限、上限、刻みを補完して大小を揃える。

    Args:
        value_type: int_range か float_range。
        minimum: 下限。無ければ型ごとの既定。
        maximum: 上限。無ければ型ごとの既定。
        step: 刻み。0 以下や欠ければ型ごとの既定。

    Returns:
        下限、上限、刻み。
    """
    kind = normalize_config_type(value_type)
    as_int = kind == "int_range"
    lo = _parse_bound_number(minimum, as_int)
    hi = _parse_bound_number(maximum, as_int)
    if lo is None and hi is None:
        lo, hi = (0, 100) if as_int else (0.0, 1.0)
    elif lo is None:
        lo = 0 if as_int else 0.0
    elif hi is None:
        hi = 100 if as_int else 1.0
    if lo > hi:
        lo, hi = hi, lo
    st = _parse_bound_number(step, as_int)
    if st is None or st <= 0:
        st = 1 if as_int else 0.01
    if as_int:
        return int(lo), int(hi), max(1, int(st))
    return float(lo), float(hi), float(st)


def validate_range_bounds(value_type, minimum, maximum, step, plugin_id="", key=""):
    """範囲の下限、上限、刻みが揃っているか検査する。

    Args:
        value_type: int_range か float_range。
        minimum: 下限。
        maximum: 上限。
        step: 刻み。
        plugin_id: エラー文言に載せるプラグイン ID。
        key: エラー文言に載せる項目キー。

    Returns:
        下限、上限、刻み。

    Raises:
        ValueError: 端や刻みが欠ける、下限が上限より大きい、または刻みが 0 以下のとき。
    """
    kind = normalize_config_type(value_type)
    as_int = kind == "int_range"
    lo = _parse_bound_number(minimum, as_int)
    hi = _parse_bound_number(maximum, as_int)
    st = _parse_bound_number(step, as_int)
    if lo is None or hi is None or st is None or lo > hi or st <= 0:
        raise ValueError(
            get_log_text(
                "plugin_config_range_invalid",
                plugin_id=plugin_id,
                field_key=key,
                value_type=kind,
            )
        )
    if as_int:
        return int(lo), int(hi), int(st)
    return float(lo), float(hi), float(st)


def _range_step_decimals(step) -> int:
    """浮動小数の刻みから丸め桁数を決める。

    Args:
        step: 刻み。

    Returns:
        小数桁。整数刻みなら 0。最大 6。
    """
    text = f"{float(step):.10f}".rstrip("0").rstrip(".")
    if "." in text:
        return min(6, max(1, len(text.split(".", 1)[1])))
    return 0


def snap_range_value(value, minimum, maximum, step, as_int: bool):
    """値を範囲に収め、刻みに合わせる。

    Args:
        value: 合わせる値。
        minimum: 下限。
        maximum: 上限。
        step: 刻み。
        as_int: True なら整数として扱う。

    Returns:
        範囲内で刻みに合わせた値。
    """
    number = int(value) if as_int else float(value)
    lo = int(minimum) if as_int else float(minimum)
    hi = int(maximum) if as_int else float(maximum)
    st = int(step) if as_int else float(step)
    if number < lo:
        number = lo
    elif number > hi:
        number = hi
    if st <= 0:
        return int(number) if as_int else float(number)
    ticks = round((number - lo) / st)
    snapped = lo + ticks * st
    if not as_int:
        snapped = round(snapped, _range_step_decimals(st))
    if snapped < lo:
        snapped = lo
    elif snapped > hi:
        snapped = hi
    if as_int:
        return int(round(snapped))
    return float(snapped)


def _is_enum_class(value) -> bool:
    """Enum のクラスなら True。

    Args:
        value: 検査するオブジェクト。

    Returns:
        Enum のサブクラスなら True。
    """
    return isinstance(value, type) and issubclass(value, Enum)


def _enum_name(enum_type: type, value) -> Optional[str]:
    """値がその Enum のメンバー名なら名前を返す。

    Args:
        enum_type: 対象の Enum クラス。
        value: メンバー、またはメンバー名。

    Returns:
        メンバー名。該当しなければ None。
    """
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value.name
    text = str(value)
    member = enum_type.__members__.get(text)
    if member is None:
        return None
    return member.name


def _enum_member(enum_type: type, value):
    """名前またはメンバーをその Enum のメンバーにする。

    Args:
        enum_type: 対象の Enum クラス。
        value: メンバー、またはメンバー名。

    Returns:
        メンバー。該当しなければ None。
    """
    name = _enum_name(enum_type, value)
    if name is None:
        return None
    return enum_type[name]


def config_choice_key(value) -> str:
    """choice の保存キーにする。

    Args:
        value: Enum、None、またはその他。

    Returns:
        Enum なら name、None なら空文字、それ以外は文字列。
    """
    if isinstance(value, Enum):
        return value.name
    if value is None:
        return ""
    return str(value)


def normalize_config_choices(choices) -> tuple[tuple[str, str], ...]:
    """choice の候補を値とラベルの組だけにする。

    Args:
        choices: Enum、メンバー列、または値とラベルの列。

    Returns:
        値とラベルの組。
    """
    rows, _enum_type = parse_config_choices(choices)
    return rows


def parse_config_choices(choices, plugin_id: str = "", key: str = "") -> tuple[tuple[tuple[str, str], ...], Optional[type]]:
    """choice の候補を正規化し、Enum ならそのクラスも返す。

    Args:
        choices: Enum クラス、メンバー列、組の列、または値の列。
        plugin_id: エラー文言に載せるプラグイン ID。
        key: エラー文言に載せる項目キー。

    Returns:
        (値, ラベル) の組と、Enum ならそのクラス。Enum でなければ None。

    Raises:
        ValueError: Enum のメンバーが空、または混在しているとき。
    """
    if choices is None:
        return (), None
    if _is_enum_class(choices):
        members = list(choices)
        if not members:
            raise ValueError(
                get_log_text(
                    "plugin_config_enum_invalid",
                    plugin_id=plugin_id,
                    field_key=key,
                )
            )
        return tuple((item.name, item.name) for item in members), choices
    if not choices:
        return (), None
    items = list(choices)
    first = items[0]
    if isinstance(first, Enum):
        enum_type = type(first)
        rows = []
        seen = set()
        for item in items:
            if not isinstance(item, enum_type):
                raise ValueError(
                    get_log_text(
                        "plugin_config_enum_invalid",
                        plugin_id=plugin_id,
                        field_key=key,
                    )
                )
            if item.name in seen:
                continue
            seen.add(item.name)
            rows.append((item.name, item.name))
        if not rows:
            raise ValueError(
                get_log_text(
                    "plugin_config_enum_invalid",
                    plugin_id=plugin_id,
                    field_key=key,
                )
            )
        return tuple(rows), enum_type
    if isinstance(first, (list, tuple)) and first and isinstance(first[0], Enum):
        enum_type = type(first[0])
        rows = []
        seen = set()
        for item in items:
            if not isinstance(item, (list, tuple)) or not item or not isinstance(item[0], enum_type):
                raise ValueError(
                    get_log_text(
                        "plugin_config_enum_invalid",
                        plugin_id=plugin_id,
                        field_key=key,
                    )
                )
            member = item[0]
            label = str(item[1]) if len(item) > 1 else member.name
            if member.name in seen:
                continue
            seen.add(member.name)
            rows.append((member.name, label))
        if not rows:
            raise ValueError(
                get_log_text(
                    "plugin_config_enum_invalid",
                    plugin_id=plugin_id,
                    field_key=key,
                )
            )
        return tuple(rows), enum_type
    rows = []
    seen = set()
    for item in items:
        if isinstance(item, (list, tuple)) and item:
            value = str(item[0])
            label = str(item[1]) if len(item) > 1 else value
        else:
            value = str(item)
            label = value
        if value in seen:
            continue
        seen.add(value)
        rows.append((value, label))
    return tuple(rows), None


def _builtin_choices(kind: str) -> tuple[tuple[str, str], ...]:
    """charset、language、country の組み込み候補を返す。

    Args:
        kind: charset、language、country のいずれか。

    Returns:
        値とラベルの組。それ以外は空。
    """
    if kind == "charset":
        from ez_co.plugins.charset import charset_choices

        return charset_choices()
    if kind == "language":
        from ez_co.plugins.locale_codes import language_choices

        return language_choices()
    if kind == "country":
        from ez_co.plugins.locale_codes import country_choices

        return country_choices()
    return ()


def _validate_enum_default(enum_type: type, default, multiple: bool, plugin_id: str, key: str):
    """Enum 項目の初期値をメンバーにする。

    Args:
        enum_type: 対象の Enum クラス。
        default: 初期値。multiple なら列でもよい。
        multiple: True なら複数選択。
        plugin_id: エラー文言に載せるプラグイン ID。
        key: エラー文言に載せる項目キー。

    Returns:
        単一ならメンバー、複数ならメンバーの列。未指定の単一は先頭メンバー。

    Raises:
        ValueError: メンバーにない初期値のとき。
    """
    if multiple:
        if default is None:
            return []
        items = list(default) if isinstance(default, (list, tuple)) else [default]
        resolved = []
        for item in items:
            member = _enum_member(enum_type, item)
            if member is None:
                raise ValueError(
                    get_log_text(
                        "plugin_config_enum_invalid",
                        plugin_id=plugin_id,
                        field_key=key,
                    )
                )
            resolved.append(member)
        return resolved
    if default is None:
        return list(enum_type)[0]
    member = _enum_member(enum_type, default)
    if member is None:
        raise ValueError(
            get_log_text(
                "plugin_config_enum_invalid",
                plugin_id=plugin_id,
                field_key=key,
            )
        )
    return member


def _normalize_multiple_default(default):
    """複数選択の初期値をリストにする。

    Args:
        default: None、列、または単一値。

    Returns:
        リスト。None なら空。
    """
    if default is None:
        return []
    if isinstance(default, (list, tuple)):
        return list(default)
    return [default]


def _choice_fallback(options, value, default):
    """候補に含まれる値を選び、無ければ初期値、それも無ければ先頭を返す。

    Args:
        options: 値とラベルの組。
        value: 優先する値。
        default: 次点の値。

    Returns:
        候補にある値。
    """
    text = config_choice_key(value)
    allowed = {item[0] for item in options}
    if text in allowed:
        return text
    fallback = config_choice_key(default)
    if fallback in allowed:
        return fallback
    return options[0][0]


def _parse_hex_color(value) -> str:
    """色を #rrggbb にする。

    Args:
        value: #rgb、#rrggbb、またはその前後の空白。

    Returns:
        小文字の #rrggbb。解釈できなければ空文字。
    """
    text = str(value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return "#" + "".join(ch.lower() * 2 for ch in text)
    if len(text) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return "#" + text.lower()
    return ""


def _unix_seconds(value) -> Optional[int]:
    """日時を UTC の UNIX 秒にする。

    Args:
        value: datetime、数値、または ISO 形式の文字列。

    Returns:
        秒。bool や解釈できない値は None。
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        moment = value
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        return int(moment.timestamp())
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        # 数値文字列でなければ日付の解釈へ進む。
        pass
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if "T" in text or " " in text:
            moment = datetime.fromisoformat(text.replace(" ", "T", 1))
        else:
            moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        return int(moment.timestamp())
    except ValueError:
        # 日付として解釈できなければ None を返す。
        return None


def _date_seconds(value) -> Optional[int]:
    """日付を UTC のその日 0 時の UNIX 秒にする。

    Args:
        value: _unix_seconds が解釈できる値。

    Returns:
        その日の 0 時の秒。解釈できなければ None。
    """
    parsed = _unix_seconds(value)
    if parsed is None:
        return None
    moment = datetime.fromtimestamp(parsed, tz=timezone.utc)
    midnight = datetime(moment.year, moment.month, moment.day, tzinfo=timezone.utc)
    return int(midnight.timestamp())


def _parse_config_int(value):
    """設定値を整数にする。

    Args:
        value: 整数、または数値として読める値。

    Returns:
        整数。

    Raises:
        TypeError: bool のとき。
    """
    if isinstance(value, bool):
        raise TypeError
    if isinstance(value, int):
        return int(value)
    return int(float(value))


def _parse_config_float(value):
    """設定値を浮動小数にする。

    Args:
        value: 数値として読める値。

    Returns:
        浮動小数。

    Raises:
        TypeError: bool のとき。
    """
    if isinstance(value, bool):
        raise TypeError
    return float(value)


def coerce_config_value(
    value_type: str,
    value,
    default=None,
    choices=None,
    minimum=None,
    maximum=None,
    step=None,
):
    """設定値を種別に合わせ、変換できなければ初期値か種ごとの既定にする。

    Args:
        value_type: 設定の種別。
        value: 変換する値。
        default: 変換できないときの初期値。
        choices: choice 系の候補。
        minimum: 範囲の下限。
        maximum: 範囲の上限。
        step: 範囲の刻み。

    Returns:
        種別に合わせた値。
    """
    kind = normalize_config_type(value_type)
    options = normalize_config_choices(choices)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "yes", "on", "1"):
                return True
            if lowered in ("false", "no", "off", "0"):
                return False
        return bool(default) if default is not None else False
    if kind == "int":
        try:
            return _parse_config_int(value)
        except (TypeError, ValueError):
            # 整数にできなければ初期値を試す。
            try:
                return _parse_config_int(default)
            except (TypeError, ValueError):
                # 初期値も整数にできなければ 0 を返す。
                return 0
    if kind == "float":
        try:
            return _parse_config_float(value)
        except (TypeError, ValueError):
            # 浮動小数にできなければ初期値を試す。
            try:
                return _parse_config_float(default)
            except (TypeError, ValueError):
                # 初期値も浮動小数にできなければ 0.0 を返す。
                return 0.0
    if kind in ("int_range", "float_range"):
        as_int = kind == "int_range"
        lo, hi, st = normalize_range_bounds(kind, minimum, maximum, step)
        parse = _parse_config_int if as_int else _parse_config_float
        try:
            raw = parse(value)
        except (TypeError, ValueError):
            # 範囲の値にできなければ初期値を試す。
            try:
                raw = parse(default)
            except (TypeError, ValueError):
                # 初期値も範囲の値にできなければ下限を使う。
                raw = lo
        return snap_range_value(raw, lo, hi, st, as_int)
    if kind == "color":
        return _parse_hex_color(value) or _parse_hex_color(default) or _COLOR_FALLBACK
    if kind == "date":
        parsed = _date_seconds(value)
        if parsed is not None:
            return parsed
        parsed = _date_seconds(default)
        return 0 if parsed is None else parsed
    if kind == "datetime":
        parsed = _unix_seconds(value)
        if parsed is not None:
            return parsed
        parsed = _unix_seconds(default)
        return 0 if parsed is None else parsed
    if kind in ("choice", "charset", "language", "country") and options:
        return _choice_fallback(options, value, default)
    if kind == "font":
        if value is None:
            return "" if default is None else str(default)
        return str(value)
    if kind in ("path", "password"):
        if value is None:
            return "" if default is None else str(default)
        return str(value)
    if value is None:
        return "" if default is None else str(default)
    return str(value)


def _coerce_one(field: ConfigField, value):
    """1件の値を項目の種別に合わせる。Enum ならメンバーにする。

    Args:
        field: 対象項目。
        value: 変換する値。

    Returns:
        メンバー、または coerce_config_value の結果。
    """
    if field.enum_type is not None:
        member = _enum_member(field.enum_type, value)
        if member is not None:
            return member
        member = _enum_member(field.enum_type, field.default)
        if member is not None:
            return member
        members = list(field.enum_type)
        return members[0] if members else value
    return coerce_config_value(
        field.value_type,
        value,
        default=field.default,
        choices=field.choices,
        minimum=field.minimum,
        maximum=field.maximum,
        step=field.step,
    )


def coerce_field_value(field: ConfigField, value):
    """項目の値を1件または複数件として種別に合わせる。

    Args:
        field: 対象項目。
        value: 変換する値。複数なら列。

    Returns:
        単一値、または値の列。空の複数は空リスト。
    """
    if not field.multiple:
        return _coerce_one(field, value)
    if value is None:
        value = field.default
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        value = [value]
    if field.enum_type is not None:
        members = []
        for item in value:
            member = _enum_member(field.enum_type, item)
            if member is None:
                default = field.default
                if default is None:
                    return []
                if not isinstance(default, (list, tuple)):
                    default = [default]
                resolved = []
                for raw in default:
                    found = _enum_member(field.enum_type, raw)
                    if found is None:
                        return []
                    resolved.append(found)
                return resolved
            members.append(member)
        return members
    if len(value) == 0:
        return []
    one = ConfigField(
        key=field.key,
        value_type=field.value_type,
        default=None,
        choices=field.choices,
        minimum=field.minimum,
        maximum=field.maximum,
        step=field.step,
        path_kind=field.path_kind,
        path_filter=field.path_filter,
        enum_type=field.enum_type,
    )
    return [_coerce_one(one, item) for item in value]


def config_value_for_storage(field: ConfigField, plain):
    """保存用に Enum を名前へ戻す。

    Args:
        field: 対象項目。
        plain: 変換済みの値。

    Returns:
        Enum でなければそのまま。Enum なら名前、複数なら名前の列。
    """
    if field.enum_type is None:
        return plain
    if field.multiple:
        if not isinstance(plain, (list, tuple)):
            return [] if plain is None else [config_choice_key(plain)]
        return [config_choice_key(item) for item in plain]
    return config_choice_key(plain)


def is_config_empty(field: ConfigField, value) -> bool:
    """必須判定のため、値が空か返す。

    Args:
        field: 対象項目。
        value: 判定する値。

    Returns:
        空とみなすなら True。
    """
    if field.multiple:
        if value is None:
            return True
        return list(value) == [] if isinstance(value, (list, tuple)) else False
    kind = field.value_type
    if kind in ("string", "path"):
        return str(value or "").strip() == ""
    if kind == "password":
        return value == ""
    if kind in _DROPDOWN_CONFIG_TYPES:
        if isinstance(value, Enum):
            return False
        text = config_choice_key(value)
        if text == "":
            return True
        if field.choices and text not in {item[0] for item in field.choices}:
            return True
        return False
    return False


def _password_to_stored(plain: str) -> Optional[str]:
    """平文を保存用トークンにする。

    Args:
        plain: 平文。

    Returns:
        トークン。暗号化に失敗したら None。
    """
    from ez_co.utils.password_protect import encrypt_secret

    try:
        return encrypt_secret(str(plain or ""))
    except Exception as exc:
        # 暗号化に失敗したら記録して None を返す。
        logger.debug(get_log_text("plugin_event_failed", event="password", error=exc))
        return None


def _password_from_stored(token, default="") -> str:
    """保存トークンを平文に戻す。

    Args:
        token: 保存トークン。空なら初期値。
        default: 復号できないときの文字列。

    Returns:
        平文。失敗時は default の文字列。
    """
    if not token:
        return "" if default is None else str(default)
    from ez_co.utils.password_protect import decrypt_secret

    try:
        plain = decrypt_secret(str(token))
    except Exception as exc:
        # 復号に失敗したら記録して初期値を返す。
        logger.debug(get_log_text("plugin_event_failed", event="password", error=exc))
        return "" if default is None else str(default)
    if plain is None:
        return "" if default is None else str(default)
    return plain


class _UiBridge:
    """ワーカーから UI スレッドへ処理を渡す。"""

    def __init__(self):
        """UI スレッドへキュー接続する発信器を作る。"""
        from PySide6.QtCore import QObject, Qt, Signal

        class _Emitter(QObject):
            """要求をキュー接続で UI スレッドへ渡す QObject。"""

            requested = Signal(object)

            def __init__(self):
                """要求シグナルを自身の処理へキュー接続する。"""
                super().__init__()
                self.requested.connect(self._dispatch, Qt.QueuedConnection)

            def _dispatch(self, payload):
                """UI スレッドで関数を実行し、結果か例外を入れて完了を知らせる。

                Args:
                    payload: 関数、結果を入れるリスト、完了イベントの組。
                """
                func, box, done = payload
                try:
                    box.append(func())
                except Exception as exc:
                    # UI スレッドの実行に失敗したら例外を結果へ入れて呼び出し側へ返す。
                    box.append(exc)
                finally:
                    done.set()

        self._emitter = _Emitter()

    def invoke(self, func):
        """UI スレッドで関数を実行し、その戻りを返す。

        Args:
            func: 実行する関数。

        Returns:
            関数の戻り。UI が無いか既に UI スレッドならその場で実行する。

        Raises:
            Exception: UI スレッド側の実行が例外のとき、その例外を送出する。
        """
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or QThread.currentThread() == app.thread():
            return func()
        box = []
        done = threading.Event()
        self._emitter.requested.emit((func, box, done))
        done.wait()
        if box and isinstance(box[0], Exception):
            raise box[0]
        return box[0] if box else None


class SidebarRegistration:
    """登録済みサイドバーの ID、タイトル、ウィジェット。"""

    def __init__(self, plugin_id: str, sidebar_id: str, title: str, widget):
        """サイドバー登録の内容を保持する。

        Args:
            plugin_id: プラグイン ID。
            sidebar_id: サイドバー ID。
            title: 表示タイトル。
            widget: 載せるウィジェット。
        """
        self.plugin_id = plugin_id
        self.sidebar_id = sidebar_id
        self.title = title
        self.widget = widget


class PluginHost:
    """プラグイン全体の登録台帳と、本体が束ねた UI 呼び出し。"""

    def __init__(self):
        """台帳と、本体から束ねるコールバックの入れ物を空で作る。"""
        self._parent = None
        self._db = None
        self._run_action = None
        self._bridge = None
        self._get_current = None
        self._reload_current = None
        self._get_app_config = None
        self._mount_sidebar = None
        self._unmount_sidebar = None
        self._toggle_sidebar = None
        self._sidebar_visible = None
        self._after_plugin_config = None
        self._formats: dict[str, list[FormatSpec]] = {}
        self._sidebars: dict[tuple[str, str], SidebarRegistration] = {}
        self._actions: dict[str, PluginAction] = {}
        self._listeners: dict[str, list[tuple[str, Callable]]] = {}
        self._scoped: dict[str, "ScopedPluginHost"] = {}
        self._config_fields: dict[str, list[ConfigField]] = {}
        self._permissions: dict[str, MappingProxyType] = {}
        self._declared_sidebar: dict[str, bool] = {}
        self._phases: dict[str, str] = {}

    def scoped(self, plugin_id: str) -> "ScopedPluginHost":
        """plugin_id に閉じたホストを返す。無ければ作る。

        Args:
            plugin_id: 対象のプラグイン ID。

        Returns:
            その ID 用の ScopedPluginHost。
        """
        key = str(plugin_id or "")
        existing = self._scoped.get(key)
        if existing is None:
            existing = ScopedPluginHost(self, key)
            self._scoped[key] = existing
        return existing

    def bind(
        self,
        parent,
        db_manager=None,
        run_action: Optional[Callable] = None,
        get_current: Optional[Callable] = None,
        reload_current: Optional[Callable] = None,
        get_app_config: Optional[Callable] = None,
        mount_sidebar: Optional[Callable] = None,
        unmount_sidebar: Optional[Callable] = None,
        toggle_sidebar: Optional[Callable] = None,
        sidebar_visible: Optional[Callable] = None,
        after_plugin_config: Optional[Callable] = None,
    ) -> None:
        """本体のウィンドウ、DB、アクション、サイドバー操作を束ねる。

        Args:
            parent: ダイアログの親。
            db_manager: プラグイン設定を読む DB。
            run_action: 本体アクションを実行する関数。
            get_current: 現在のページやパスを返す関数。
            reload_current: 現在の表示を読み直す関数。
            get_app_config: アプリ設定の読み取り関数。
            mount_sidebar: サイドバーを載せる関数。
            unmount_sidebar: サイドバーを外す関数。
            toggle_sidebar: サイドバーの表示を切り替える関数。
            sidebar_visible: サイドバーが見えているか返す関数。
            after_plugin_config: 設定保存後に呼ぶ関数。
        """
        self._parent = parent
        self._db = db_manager
        self._run_action = run_action
        self._get_current = get_current
        self._reload_current = reload_current
        self._get_app_config = get_app_config
        self._mount_sidebar = mount_sidebar
        self._unmount_sidebar = unmount_sidebar
        self._toggle_sidebar = toggle_sidebar
        self._sidebar_visible = sidebar_visible
        self._after_plugin_config = after_plugin_config
        self._ensure_bridge()
        if mount_sidebar:
            for record in list(self._sidebars.values()):
                try:
                    mount_sidebar(
                        record.plugin_id,
                        record.sidebar_id,
                        self.expand_text(record.plugin_id, record.title),
                        record.widget,
                    )
                except Exception as exc:
                    # サイドバーの取り付けに失敗したら警告を残して続ける。
                    logger.warning(get_log_text("plugin_sidebar_mount_failed", error=exc))

    def formats_for(self, plugin_id: str) -> list[FormatSpec]:
        """プラグインが宣言した担当形式を返す。

        Args:
            plugin_id: プラグイン ID。

        Returns:
            FormatSpec のリスト。無ければ空。
        """
        return list(self._formats.get(plugin_id, []))

    def sidebars_for(self, plugin_id: str) -> list[SidebarRegistration]:
        """プラグインが登録したサイドバーを返す。

        Args:
            plugin_id: プラグイン ID。

        Returns:
            その ID の登録一覧。
        """
        return [item for key, item in self._sidebars.items() if key[0] == plugin_id]

    def ask_password(self, file_path: str, mismatch: bool = False, verify=None) -> Optional[str]:
        """UI スレッドでアーカイブパスワードを尋ねる。

        Args:
            file_path: 対象ファイル。
            mismatch: True なら不一致としてダイアログを開く。
            verify: パスワードを検証する関数。無ければ検証しない。

        Returns:
            採用したパスワード。取消なら None。
        """
        return self._call_on_ui(lambda: self._ask_password_ui(file_path, mismatch, verify))

    def show_dialog(self, name: str, **kwargs):
        """名前がパスワード系ならパスワードを尋ね、それ以外は未対応として何も返さない。

        Args:
            name: ダイアログ名。
            kwargs: file_path、path、mismatch、verify。

        Returns:
            パスワードダイアログの結果。未対応なら None。
        """
        key = str(name or "").strip().lower()
        if key in ("password", "archive_password", "ask_password"):
            return self.ask_password(
                kwargs.get("file_path") or kwargs.get("path") or "",
                mismatch=bool(kwargs.get("mismatch", False)),
                verify=kwargs.get("verify"),
            )
        logger.warning(get_log_text("plugin_dialog_unsupported", name=name))
        return None

    def run_action(self, action_id: str, **kwargs) -> bool:
        """UI スレッドでアクションを実行する。

        Args:
            action_id: 公開 ID またはエイリアス。
            kwargs: 本体アクションへ渡す追加引数。

        Returns:
            実行できれば True。
        """
        return bool(self._call_on_ui(lambda: self._run_action_ui(action_id, kwargs)))

    def load_ui(self, data_or_path):
        """UI スレッドで .ui のバイト列またはパスからウィジェットを作る。

        Args:
            data_or_path: .ui のバイト列、またはファイルパス。

        Returns:
            読み込んだウィジェット。
        """
        return self._call_on_ui(lambda: self._load_ui(data_or_path))

    def report_error(self, where, exc, plugin_id: Optional[str] = None) -> None:
        """エラーを本体の記録へ渡す。

        Args:
            where: 発生箇所の名前。
            exc: 例外。
            plugin_id: 対象プラグイン。省略時は記録側の既定。
        """
        from ez_co.utils.error_logger import report_error
        report_error(where, exc, plugin_id=plugin_id)

    def set_manifest_permissions(self, plugin_id: str, permissions) -> None:
        """本体のロード経路だけが呼び、プラグイン API には出さない。

        Args:
            plugin_id: 対象のプラグイン ID。空なら何もしない。
            permissions: マニフェストの permissions。dict 以外は dict にできるものだけ読む。
        """
        key = str(plugin_id or "")
        if not key:
            return
        if isinstance(permissions, dict):
            raw = permissions
        elif permissions is None:
            raw = {}
        else:
            try:
                raw = dict(permissions)
            except (TypeError, ValueError):
                # 権限を dict にできなければ空として扱う。
                raw = {}
        self._permissions[key] = parse_permissions(raw)

    def set_manifest_provides(self, plugin_id: str, formats=(), sidebar: bool = False) -> None:
        """本体のロード経路だけが呼び、プラグイン API には出さない。

        Args:
            plugin_id: 対象のプラグイン ID。空なら何もしない。
            formats: FormatSpec の列、または正規化前の形式指定。
            sidebar: サイドバーを宣言しているか。
        """
        key = str(plugin_id or "")
        if not key:
            return
        if formats and isinstance(formats[0], FormatSpec):
            specs = tuple(formats)
        else:
            specs = tuple(normalize_formats(formats))
        self._declared_sidebar[key] = bool(sidebar)
        self._formats[key] = list(specs)

    def enter_phase(self, plugin_id: str, phase: str) -> None:
        """本体のロード経路だけが呼び、プラグイン API には出さない。

        Args:
            plugin_id: 対象のプラグイン ID。空なら何もしない。
            phase: 設定する phase。空なら idle。
        """
        key = str(plugin_id or "")
        if not key:
            return
        self._phases[key] = str(phase or _PHASE_IDLE)

    def phase_of(self, plugin_id: str) -> str:
        """プラグインの現在の phase を返す。

        Args:
            plugin_id: 対象のプラグイン ID。

        Returns:
            記録された phase。無ければ idle。
        """
        return self._phases.get(str(plugin_id or ""), _PHASE_IDLE)

    def abort_load(self, plugin_id: str) -> None:
        """__init__ / load 失敗時に、UI 台帳と設定スキーマをその plugin_id だけ捨てる。

        Args:
            plugin_id: 対象のプラグイン ID。空なら何もしない。
        """
        key = str(plugin_id or "")
        if not key:
            return
        self.clear_plugin(key)
        self._config_fields.pop(key, None)
        self.enter_phase(key, _PHASE_IDLE)

    def _deny_wrong_phase(self, plugin_id: str, action: str) -> None:
        """phase に合わない登録なら拒否する。

        Args:
            plugin_id: 対象のプラグイン ID。
            action: 行おうとした登録名。

        Raises:
            PluginRegistrationDenied: language、init、または load 中の UI 登録のとき。
        """
        phase = self.phase_of(plugin_id)
        if phase == _PHASE_LANGUAGE:
            raise PluginRegistrationDenied(
                plugin_id,
                "plugin_register_during_language",
                ui_key="ui.plugin_register_wrong_phase",
            )
        if phase == _PHASE_INIT:
            raise PluginRegistrationDenied(
                plugin_id,
                "plugin_register_during_init",
                ui_key="ui.plugin_register_wrong_phase",
            )
        if phase == _PHASE_LOAD and action in _UI_REGISTER:
            raise PluginRegistrationDenied(
                plugin_id,
                "plugin_register_ui_during_load",
                ui_key="ui.plugin_register_wrong_phase",
            )

    def has_manifest_permission(self, plugin_id: str, name: str) -> bool:
        """マニフェストでその権限が true なら True。

        Args:
            plugin_id: プラグイン ID。
            name: 権限名。

        Returns:
            付与されていれば True。
        """
        granted = self._permissions.get(str(plugin_id))
        if not granted:
            return False
        return bool(granted.get(str(name or "")))

    def _delivers_current_changed(self, plugin_id: str) -> bool:
        """current_changed をこのプラグインへ届けるなら True。

        Args:
            plugin_id: プラグイン ID。

        Returns:
            サイドバーが無い、inactive_callback がある、またはサイドバーが見えていれば True。
        """
        if not self.sidebars_for(plugin_id):
            return True
        if self.has_manifest_permission(plugin_id, "inactive_callback"):
            return True
        checker = self._sidebar_visible
        if checker is None:
            return False
        try:
            return bool(checker(plugin_id))
        except Exception:
            # 表示判定に失敗したら current_changed を届けない。
            return False

    def emit(self, event: str, payload=None, plugin_id: Optional[str] = None) -> None:
        """購読者へイベントを渡す。失敗は report_error に残す。

        Args:
            event: イベント名。空なら何もしない。
            payload: コールバックへ渡す値。
            plugin_id: 指定時はそのプラグインの購読だけ。
        """
        name = str(event or "").strip()
        if not name:
            return
        target = str(plugin_id) if plugin_id else None
        gate_inactive = name == "current_changed"
        for owner, callback in list(self._listeners.get(name, [])):
            if target is not None and owner != target:
                continue
            if gate_inactive and not self._delivers_current_changed(owner):
                continue
            try:
                callback(payload)
            except TypeError:
                # 引数を受け取れない購読なら引数なしで呼び直す。
                try:
                    callback()
                except Exception as exc:
                    # 引数なしの呼び出しも失敗したら記録して次の購読へ進む。
                    self.report_error(name, exc, plugin_id=owner)
            except Exception as exc:
                # 購読の実行に失敗したら記録して次へ進む。
                self.report_error(name, exc, plugin_id=owner)

    def expand_text(self, plugin_id: str, value) -> str:
        """プラグインの get_text で {key} 全体だけ展開する。

        Args:
            plugin_id: 対象のプラグイン ID。
            value: 展開する値。

        Returns:
            展開後の文字列。
        """
        return self.scoped(plugin_id).expand_text(value)

    def refresh_display_titles(self) -> None:
        """アプリ言語変更後、既存ドックのタイトルと設定フォームのラベルを差し替える。unmount しない。"""
        if self._mount_sidebar is None:
            return
        for record in list(self._sidebars.values()):
            refresh = getattr(record.widget, "refresh_labels", None)
            if callable(refresh):
                try:
                    refresh()
                except Exception as exc:
                    # ラベル更新に失敗したら記録してタイトル差し替えへ進む。
                    logger.debug(get_log_text("plugin_event_failed", event="refresh_labels", error=exc))
            title = self.expand_text(record.plugin_id, record.title)
            try:
                self._mount_sidebar(record.plugin_id, record.sidebar_id, title, record.widget)
            except Exception as exc:
                # タイトル差し替えの取り付けに失敗したら警告を残して続ける。
                logger.warning(get_log_text("plugin_sidebar_mount_failed", error=exc))

    def configs_for(self, plugin_id: str) -> list[ConfigField]:
        """プラグインが登録した設定項目を返す。

        Args:
            plugin_id: プラグイン ID。

        Returns:
            ConfigField のリスト。無ければ空。
        """
        return list(self._config_fields.get(plugin_id, []))

    def list_actions(self) -> list[PluginAction]:
        """登録済みアクションを返す。

        Returns:
            PluginAction のリスト。
        """
        return list(self._actions.values())

    def resolve_action(self, action_id: str) -> Optional[PluginAction]:
        """公開 ID またはエイリアスからアクションを探す。

        Args:
            action_id: 公開 ID またはエイリアス。

        Returns:
            見つかったアクション。無ければ None。
        """
        key = str(action_id or "")
        if not key:
            return None
        record = self._actions.get(key)
        if record is not None:
            return record
        for item in self._actions.values():
            if key in item.aliases:
                return item
        return None

    def action_label(self, action_id: str) -> Optional[str]:
        """アクションの表示ラベルを言語展開して返す。

        Args:
            action_id: 公開 ID またはエイリアス。

        Returns:
            展開したラベル。サイドバーなら切替ラベル。無ければ None。
        """
        record = self.resolve_action(action_id)
        if record is None:
            return None
        label = self.expand_text(record.plugin_id, record.label)
        if record.kind == "sidebar":
            return sidebar_toggle_label(label)
        return label

    def action_ids_for(self, public_id: str) -> list[str]:
        """公開 ID とエイリアスをまとめて返す。

        Args:
            public_id: 公開 ID またはエイリアス。

        Returns:
            公開 ID とエイリアス。見つからなければ public_id だけ。空なら空。
        """
        record = self.resolve_action(public_id)
        if record is None:
            return [public_id] if public_id else []
        return [record.public_id, *record.aliases]

    def invoke_registered(self, action_id: str) -> bool:
        """登録済みアクションのコールバックを実行する。

        Args:
            action_id: 公開 ID またはエイリアス。

        Returns:
            戻りが None なら True、それ以外はその真偽。失敗や未登録は False。
        """
        record = self.resolve_action(action_id)
        if record is None:
            return False
        try:
            result = record.callback()
        except TypeError:
            # 引数を取らないコールバックなら引数なしで実行する。
            try:
                record.callback()
                return True
            except Exception as exc:
                # 引数なしの実行も失敗したら記録して False を返す。
                self.report_error(action_id, exc, plugin_id=record.plugin_id)
                return False
        except Exception as exc:
            # アクション実行に失敗したら記録して False を返す。
            self.report_error(action_id, exc, plugin_id=record.plugin_id)
            return False
        return True if result is None else bool(result)

    def clear_plugin(self, plugin_id: str) -> None:
        """sidebar / action / listener / filter 台帳を外し、teardown の off / unregister には頼らない。

        Args:
            plugin_id: 外すプラグイン ID。
        """
        for key in [item for item in self._sidebars if item[0] == plugin_id]:
            self._unmount_sidebar_record(key)
        for public_id in [item for item, record in self._actions.items() if record.plugin_id == plugin_id]:
            self._actions.pop(public_id, None)
        for event, rows in list(self._listeners.items()):
            self._listeners[event] = [item for item in rows if item[0] != plugin_id]
        get_filter_registry().unregister_plugin(plugin_id)

    def _register_sidebar(self, plugin_id: str, sidebar_id: str, title: str, widget_or_layout, aliases=None) -> None:
        """サイドバーと切替アクションを台帳へ載せ、可能ならマウントする。

        Args:
            plugin_id: プラグイン ID。
            sidebar_id: サイドバー ID。空なら main。
            title: 表示タイトル。空なら sidebar_id。
            widget_or_layout: ウィジェット、またはレイアウト。
            aliases: 切替アクションのエイリアス。

        Raises:
            PluginRegistrationDenied: phase が違う、または sidebar 未宣言のとき。
        """
        self._deny_wrong_phase(plugin_id, "register_sidebar")
        if not self._declared_sidebar.get(plugin_id):
            raise PluginRegistrationDenied(plugin_id, "plugin_sidebar_not_declared")
        sidebar_id = str(sidebar_id or "").strip() or "main"
        widget = self._as_widget(widget_or_layout)
        record = SidebarRegistration(plugin_id, sidebar_id, str(title or sidebar_id), widget)
        self._sidebars[(plugin_id, sidebar_id)] = record
        self._register_sidebar_action(plugin_id, sidebar_id, record.title, aliases)
        if self._mount_sidebar is not None:
            try:
                self._mount_sidebar(
                    plugin_id,
                    sidebar_id,
                    self.expand_text(plugin_id, record.title),
                    widget,
                )
            except Exception as exc:
                # サイドバーの取り付けに失敗したら警告を残して台帳の登録は続ける。
                logger.warning(get_log_text("plugin_sidebar_mount_failed", error=exc))

    def _required_setting_sidebar(self, plugin_id: str):
        """登録済み設定から必須の設定フォームを作る。

        Args:
            plugin_id: プラグイン ID。

        Returns:
            そのプラグインの PluginConfigForm。

        Raises:
            PluginRegistrationDenied: phase が違う、または sidebar 未宣言のとき。
            ValueError: 設定項目が無いとき。
        """
        self._deny_wrong_phase(plugin_id, "required_setting_sidebar")
        if not self._declared_sidebar.get(plugin_id):
            raise PluginRegistrationDenied(plugin_id, "plugin_sidebar_not_declared")
        fields = self.configs_for(plugin_id)
        if not fields:
            raise ValueError(get_log_text("plugin_config_sidebar_empty", plugin_id=plugin_id))
        from ez_co.ui.plugins.config_form import PluginConfigForm

        return PluginConfigForm(self, plugin_id)

    def _register_config_sidebar(self, plugin_id: str, sidebar_id: str, title: str, aliases=None) -> None:
        """設定フォームをサイドバーとして登録する。

        Args:
            plugin_id: プラグイン ID。
            sidebar_id: サイドバー ID。
            title: 表示タイトル。
            aliases: 切替アクションのエイリアス。
        """
        self._deny_wrong_phase(plugin_id, "register_config_sidebar")
        widget = self._required_setting_sidebar(plugin_id)
        self._register_sidebar(plugin_id, sidebar_id, title, widget, aliases)

    def _unregister_sidebar(self, plugin_id: str, sidebar_id: str) -> None:
        """サイドバー登録を台帳から外す。

        Args:
            plugin_id: プラグイン ID。
            sidebar_id: サイドバー ID。空なら main。
        """
        self._deny_wrong_phase(plugin_id, "unregister_sidebar")
        self._unmount_sidebar_record((plugin_id, str(sidebar_id or "").strip() or "main"))

    def _unmount_sidebar_record(self, key: tuple[str, str]) -> None:
        """台帳からサイドバーを外し、切替アクションも消してアンマウントする。

        Args:
            key: plugin_id と sidebar_id の組。
        """
        record = self._sidebars.pop(key, None)
        if record is None:
            return
        self._actions.pop(make_sidebar_action_id(record.plugin_id, record.sidebar_id), None)
        if self._unmount_sidebar is not None:
            try:
                self._unmount_sidebar(record.plugin_id, record.sidebar_id)
            except Exception as exc:
                # 取り外しに失敗したら記録して台帳からの削除は維持する。
                logger.debug(get_log_text("plugin_sidebar_unmount_failed", error=exc))

    def _register_sidebar_action(self, plugin_id: str, sidebar_id: str, title: str, aliases=None) -> None:
        """サイドバー表示切替のアクションを台帳へ載せる。

        Args:
            plugin_id: プラグイン ID。
            sidebar_id: サイドバー ID。
            title: 表示タイトル。
            aliases: エイリアス。
        """
        public_id = make_sidebar_action_id(plugin_id, sidebar_id)
        self._actions[public_id] = PluginAction(
            plugin_id=plugin_id,
            local_id=f"sidebar:{sidebar_id}",
            public_id=public_id,
            label=str(title or sidebar_id),
            callback=lambda pid=plugin_id, sid=sidebar_id: self._toggle_sidebar_ui(pid, sid),
            kind="sidebar",
            aliases=normalize_action_aliases(aliases),
        )

    def _toggle_sidebar_ui(self, plugin_id: str, sidebar_id: str) -> bool:
        """本体の切替関数でサイドバー表示を切り替える。

        Args:
            plugin_id: プラグイン ID。
            sidebar_id: サイドバー ID。

        Returns:
            切り替え結果。未接続や失敗は False。
        """
        if self._toggle_sidebar is None:
            return False
        try:
            return bool(self._toggle_sidebar(plugin_id, sidebar_id))
        except Exception as exc:
            # 表示切替に失敗したら記録して False を返す。
            logger.debug(get_log_text("plugin_event_failed", event=f"toggle_sidebar:{sidebar_id}", error=exc))
            return False

    def _register_filter(self, plugin_id: str, filter_id: str, title: str, process) -> None:
        """フィルターを台帳へ載せる。

        Args:
            plugin_id: プラグイン ID。
            filter_id: ローカル ID。
            title: 表示名。空ならローカル ID。
            process: 画像を加工する関数。

        Raises:
            PluginRegistrationDenied: phase が違う、または filter 権限が無いとき。
            ValueError: ID が不正、または process が呼べないとき。
        """
        self._deny_wrong_phase(plugin_id, "register_filter")
        if not self.has_manifest_permission(plugin_id, "filter"):
            raise PluginRegistrationDenied(plugin_id, "plugin_filter_not_permitted")
        local_id = normalize_local_filter_id(filter_id)
        if not local_id or not callable(process):
            raise ValueError(get_log_text("plugin_filter_invalid", plugin_id=plugin_id, filter_id=filter_id))
        public_id = make_plugin_filter_id(plugin_id, local_id)
        get_filter_registry().register(
            FilterRecord(
                public_id=public_id,
                plugin_id=plugin_id,
                local_id=local_id,
                title=str(title or local_id),
                process=process,
                has_settings=bool(self.configs_for(plugin_id)),
            )
        )

    def _unregister_filter(self, plugin_id: str, filter_id: str) -> None:
        """フィルターを台帳から外す。

        Args:
            plugin_id: プラグイン ID。
            filter_id: ローカル ID。不正なら何もしない。
        """
        self._deny_wrong_phase(plugin_id, "unregister_filter")
        local_id = normalize_local_filter_id(filter_id)
        if not local_id:
            return
        get_filter_registry().unregister(make_plugin_filter_id(plugin_id, local_id))

    def _register_action(self, plugin_id: str, action_id, label, callback, aliases=None) -> None:
        """カスタムアクションを台帳へ載せる。

        Args:
            plugin_id: プラグイン ID。
            action_id: ローカル ID。不正なら何もしない。
            label: 表示ラベル。空ならローカル ID。
            callback: 実行する関数。None なら登録しない。
            aliases: エイリアス。
        """
        self._deny_wrong_phase(plugin_id, "register_action")
        local_id = normalize_local_action_id(action_id)
        if not local_id or callback is None:
            return
        public_id = make_plugin_action_id(plugin_id, local_id)
        self._actions[public_id] = PluginAction(
            plugin_id=plugin_id,
            local_id=local_id,
            public_id=public_id,
            label=str(label or local_id),
            callback=callback,
            kind="custom",
            aliases=normalize_action_aliases(aliases),
        )

    def _unregister_action(self, plugin_id: str, action_id) -> None:
        """カスタムアクションを台帳から外す。

        Args:
            plugin_id: プラグイン ID。
            action_id: ローカル ID。不正なら何もしない。
        """
        self._deny_wrong_phase(plugin_id, "unregister_action")
        local_id = normalize_local_action_id(action_id)
        if not local_id:
            return
        self._actions.pop(make_plugin_action_id(plugin_id, local_id), None)

    def _as_widget(self, widget_or_layout):
        """レイアウトならウィジェットに載せて返す。

        Args:
            widget_or_layout: ウィジェット、またはレイアウト。

        Returns:
            ウィジェット。レイアウトでなければそのまま。
        """
        from PySide6.QtWidgets import QLayout, QWidget

        if isinstance(widget_or_layout, QLayout):
            widget = QWidget()
            widget.setLayout(widget_or_layout)
            return widget
        return widget_or_layout

    def _on(self, plugin_id: str, event: str, callback: Callable) -> None:
        """イベント購読を足す。

        Args:
            plugin_id: プラグイン ID。
            event: イベント名。空なら何もしない。
            callback: 呼ぶ関数。None なら何もしない。
        """
        self._deny_wrong_phase(plugin_id, "on")
        name = str(event or "").strip()
        if not name or callback is None:
            return
        self._listeners.setdefault(name, []).append((plugin_id, callback))

    def _off(self, plugin_id: str, event: str, callback: Optional[Callable] = None) -> None:
        """イベント購読を外す。

        Args:
            plugin_id: プラグイン ID。
            event: イベント名。
            callback: 外す関数。None ならそのプラグインの購読を全部外す。
        """
        self._deny_wrong_phase(plugin_id, "off")
        name = str(event or "").strip()
        rows = self._listeners.get(name) or []
        if callback is None:
            self._listeners[name] = [item for item in rows if item[0] != plugin_id]
            return
        self._listeners[name] = [item for item in rows if item != (plugin_id, callback)]

    def _load_ui(self, data_or_path):
        """.ui のバイト列またはパスからウィジェットを作る。

        Args:
            data_or_path: .ui のバイト列、またはファイルパス。

        Returns:
            読み込んだウィジェット。

        Raises:
            FileNotFoundError: パスを開けないとき。
        """
        from PySide6.QtCore import QBuffer, QByteArray, QFile, QIODevice
        from PySide6.QtUiTools import QUiLoader

        loader = QUiLoader()
        if isinstance(data_or_path, (bytes, bytearray)):
            buffer = QBuffer()
            buffer.setData(QByteArray(bytes(data_or_path)))
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            widget = loader.load(buffer)
            buffer.close()
            return widget
        path = str(data_or_path or "")
        handle = QFile(path)
        if not handle.open(QFile.OpenModeFlag.ReadOnly):
            raise FileNotFoundError(path)
        widget = loader.load(handle)
        handle.close()
        return widget

    def _register_config(
        self,
        plugin_id: str,
        key: str,
        value_type,
        default=None,
        label=None,
        description=None,
        choices=None,
        minimum=None,
        maximum=None,
        step=None,
        path_kind=None,
        path_filter=None,
        sync=False,
        reload=False,
        multiple=False,
        suffix=None,
        required=False,
    ) -> None:
        """設定項目を正規化して、台帳の同じキーを置き換える。

        Args:
            plugin_id: プラグイン ID。
            key: 項目キー。空なら何もしない。
            value_type: 設定の種別。
            default: 初期値。
            label: 表示名。
            description: 説明。
            choices: choice の候補。
            minimum: 範囲の下限。
            maximum: 範囲の上限。
            step: 範囲の刻み。
            path_kind: file または directory。
            path_filter: パス選択のフィルタ。
            sync: 数値の即時保存。
            reload: 保存後の再読み込み。
            multiple: 複数選択。
            suffix: 数値の接尾辞。数値以外は空にする。
            required: 空の保存を拒むか。
        """
        self._deny_wrong_phase(plugin_id, "register_config")
        field_key = str(key or "").strip()
        if not field_key:
            return
        kind = normalize_config_type(value_type)
        lo = hi = st = None
        if kind in ("int_range", "float_range"):
            lo, hi, st = validate_range_bounds(
                kind, minimum, maximum, step, plugin_id=plugin_id, key=field_key
            )
        enum_type = None
        if kind == "choice":
            choice_rows, enum_type = parse_config_choices(choices, plugin_id=plugin_id, key=field_key)
        elif kind in ("charset", "language", "country"):
            choice_rows = _builtin_choices(kind)
        else:
            choice_rows = ()
        many = bool(multiple)
        if enum_type is not None:
            default = _validate_enum_default(enum_type, default, many, plugin_id, field_key)
        elif many:
            default = _normalize_multiple_default(default)
        suffix_text = str(suffix or "") if kind in _NUMERIC_CONFIG_TYPES else ""
        field = ConfigField(
            key=field_key,
            value_type=kind,
            default=default,
            label=str(label or ""),
            description=str(description or ""),
            choices=choice_rows,
            minimum=lo,
            maximum=hi,
            step=st,
            path_kind=normalize_path_kind(path_kind),
            path_filter=str(path_filter or ""),
            sync=bool(sync),
            reload=bool(reload),
            multiple=many,
            suffix=suffix_text,
            required=bool(required),
            enum_type=enum_type,
        )
        rows = [item for item in self._config_fields.get(plugin_id, []) if item.key != field_key]
        rows.append(field)
        self._config_fields[plugin_id] = rows

    def _register_config_json(self, plugin_id: str, name: str, root) -> None:
        """resources/config の JSON から設定項目を登録する。

        Args:
            plugin_id: プラグイン ID。
            name: config ディレクトリ内のファイル名。
            root: プラグインルート。None なら失敗。

        Raises:
            KeyError: root が None のとき。
        """
        self._deny_wrong_phase(plugin_id, "register_config")
        if root is None:
            raise KeyError(name)
        raw = root.read_bytes(resource_relative("config", name))
        for item in parse_config_json(raw, plugin_id=plugin_id):
            payload = dict(item)
            field_key = payload.pop("key", "")
            value_type = payload.pop("value_type", "string")
            self._register_config(plugin_id, field_key, value_type, **payload)

    def _field_for(self, plugin_id: str, key: str) -> Optional[ConfigField]:
        """キーに一致する設定項目を返す。

        Args:
            plugin_id: プラグイン ID。
            key: 項目キー。

        Returns:
            一致した項目。無ければ None。
        """
        for field in self._config_fields.get(plugin_id, []):
            if field.key == key:
                return field
        return None

    def _get_plugin_config(self, plugin_id: str, key: str, default=None):
        """保存値を項目の種別に合わせて返す。無ければ初期値。

        Args:
            plugin_id: プラグイン ID。
            key: 項目キー。
            default: 保存が無いときの値。None なら項目の初期値。

        Returns:
            変換後の値。項目が無ければ保存値か default。
        """
        field = self._field_for(plugin_id, key)
        if default is None and field is not None:
            default = field.default
        if self._db is None:
            value = default
        else:
            value = self._db.get_plugin_setting(plugin_id, key, None)
            if value is None:
                value = default
            elif field is not None and field.value_type == "password":
                fallback = "" if default is None else str(default)
                value = _password_from_stored(value, fallback)
        if field is not None:
            return coerce_field_value(field, value)
        return value

    def _set_plugin_config(self, plugin_id: str, key: str, value, notify: bool = True) -> bool:
        """値を種別に合わせて保存し、必要なら config_changed を出す。

        Args:
            plugin_id: プラグイン ID。
            key: 項目キー。
            value: 保存する値。
            notify: True なら変更を通知する。

        Returns:
            保存できれば True。必須が空、暗号化失敗、DB 無しは False。
        """
        field = self._field_for(plugin_id, key)
        plain = coerce_field_value(field, value) if field is not None else value
        if field is not None and field.required and is_config_empty(field, plain):
            logger.debug(
                get_log_text(
                    "plugin_config_required_empty",
                    plugin_id=plugin_id,
                    field_key=str(key or ""),
                )
            )
            return False
        stored = config_value_for_storage(field, plain) if field is not None else plain
        if field is not None and field.value_type == "password":
            token = _password_to_stored(plain)
            if token is None:
                return False
            stored = token
        if self._db is None:
            ok = False
        else:
            ok = bool(self._db.set_plugin_setting(plugin_id, key, stored))
        if notify:
            self.emit("config_changed", {"key": str(key or ""), "value": plain}, plugin_id=plugin_id)
            self._notify_after_plugin_config(plugin_id)
        return ok

    def _notify_after_plugin_config(self, plugin_id: str) -> None:
        """設定保存後の本体コールバックを呼ぶ。

        Args:
            plugin_id: プラグイン ID。
        """
        callback = self._after_plugin_config
        if callback is None:
            return
        try:
            callback(plugin_id)
        except Exception as exc:
            # 設定保存後の通知に失敗したら記録して続ける。
            logger.debug(get_log_text("plugin_event_failed", event="after_plugin_config", error=exc))

    def _delete_plugin_config(self, plugin_id: str, key: str) -> bool:
        """保存済みの設定値を消す。

        Args:
            plugin_id: プラグイン ID。
            key: 項目キー。

        Returns:
            削除できれば True。DB が無ければ False。
        """
        if self._db is None:
            return False
        return bool(self._db.delete_plugin_setting(plugin_id, key))

    def _reset_plugin_config(self, plugin_id: str, key: str) -> bool:
        """保存値を消して初期値へ戻し、変更を通知する。

        Args:
            plugin_id: プラグイン ID。
            key: 項目キー。

        Returns:
            削除できれば True。
        """
        if not self._delete_plugin_config(plugin_id, key):
            return False
        field = self._field_for(plugin_id, key)
        default = field.default if field is not None else None
        value = self._get_plugin_config(plugin_id, key, default)
        self.emit(
            "config_changed",
            {"key": str(key or ""), "value": value},
            plugin_id=plugin_id,
        )
        self._notify_after_plugin_config(plugin_id)
        return True

    def _app_config_snapshot(self):
        """アプリ設定のうち language、viewer、cache、ui_font だけを読み取り専用で返す。

        Returns:
            セクションごとの読み取り専用 dict。
        """
        raw = {}
        if self._get_app_config is not None:
            try:
                raw = self._get_app_config() or {}
            except Exception as exc:
                # アプリ設定を読めなければ記録して空として続ける。
                logger.debug(get_log_text("plugin_app_config_failed", error=exc))
                raw = {}
        allowed = {}
        for section in _APP_CONFIG_ALLOW:
            value = raw.get(section)
            if isinstance(value, dict):
                allowed[section] = copy.deepcopy(dict(value))
        return MappingProxyType({key: MappingProxyType(val) for key, val in allowed.items()})

    def _current_value(self, key: str):
        """本体から現在値を読む。

        Args:
            key: 現在値のキー。

        Returns:
            読めた値。未接続や失敗は None。
        """
        if self._get_current is None:
            return None
        try:
            return self._get_current(str(key or ""))
        except Exception as exc:
            # 現在値を読めなければ記録して None を返す。
            logger.debug(get_log_text("plugin_current_failed", key=key, error=exc))
            return None

    def reload_current(self, page=None) -> bool:
        """UI スレッドで現在の表示を読み直す。

        Args:
            page: 読み直すページ。整数にできなければ指定なし。

        Returns:
            読み直せれば True。
        """
        target = None
        if page is not None:
            try:
                target = int(page)
            except (TypeError, ValueError):
                # ページ番号にできなければ指定なしにする。
                target = None
        return bool(self._call_on_ui(lambda: self._reload_current_ui(target)))

    def _reload_current_ui(self, page) -> bool:
        """現在の表示を読み直す。

        Args:
            page: 読み直すページ。None なら指定なし。

        Returns:
            読み直せれば True。未接続や失敗は False。
        """
        if self._reload_current is None:
            return False
        try:
            return bool(self._reload_current(page))
        except Exception as exc:
            # 再読み込みに失敗したら記録して False を返す。
            logger.debug(get_log_text("plugin_event_failed", event="reload_current", error=exc))
            return False

    def _run_action_ui(self, action_id: str, kwargs: dict) -> bool:
        """登録済みアクションを優先し、無ければ本体のアクションを実行する。

        Args:
            action_id: アクション ID。
            kwargs: 本体アクションへ渡す引数。

        Returns:
            実行できれば True。未接続は False。
        """
        if self.invoke_registered(action_id):
            return True
        if self._run_action is None:
            logger.info(get_log_text("plugin_action_not_bound", action_id=action_id))
            return False
        return bool(self._run_action(action_id, kwargs))

    def _ask_password_ui(self, file_path: str, mismatch: bool, verify) -> Optional[str]:
        """セッション、保存済み、ダイアログの順でパスワードを決める。

        Args:
            file_path: 対象ファイル。
            mismatch: True なら不一致としてダイアログを開く。
            verify: パスワードを検証する関数。

        Returns:
            採用したパスワード。取消やアプリ終了は None。
        """
        from PySide6.QtWidgets import QApplication, QDialog
        from ez_co.handlers.archive_password import get_session_password, set_session_password
        from ez_co.ui.dialogs.pdf_password_dialog import CLOSE_APP_RESULT, ArchivePasswordDialog

        cached = get_session_password(file_path)
        if cached is not None:
            if self._verify_password(cached, verify):
                return cached

        stored = None
        if self._db is not None:
            try:
                stored = self._db.get_stored_archive_password(file_path)
            except Exception as exc:
                # 保存済みパスワードを読めなければ記録してダイアログへ進む。
                logger.debug(get_log_text("plugin_stored_password_failed", error=exc))
        if stored is not None:
            if self._verify_password(stored, verify):
                set_session_password(file_path, stored)
                return stored
            mismatch = True

        while True:
            dialog = ArchivePasswordDialog(self._parent, mismatch=mismatch)
            result = dialog.exec()
            if result == CLOSE_APP_RESULT:
                app = QApplication.instance()
                if app is not None:
                    app.quit()
                return None
            if result != QDialog.DialogCode.Accepted:
                return None
            password = dialog.password()
            if self._verify_password(password, verify):
                set_session_password(file_path, password)
                return password
            mismatch = True

    def _verify_password(self, password: str, verify) -> bool:
        """検証関数が無ければ通し、あればその結果を返す。

        Args:
            password: 検証するパスワード。
            verify: 検証関数。None なら常に成功。

        Returns:
            検証結果。例外なら False。
        """
        if verify is None:
            return True
        try:
            return bool(verify(password))
        except Exception:
            # 検証に失敗したら不一致として False を返す。
            return False

    def _ensure_bridge(self) -> None:
        """UI があるときだけ、UI スレッドへ渡す橋を作る。"""
        from PySide6.QtWidgets import QApplication

        if self._bridge is not None:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._bridge = _UiBridge()
        self._bridge._emitter.moveToThread(app.thread())

    def _call_on_ui(self, func):
        """UI スレッドで関数を実行する。UI が無ければその場で実行する。

        Args:
            func: 実行する関数。

        Returns:
            関数の戻り。
        """
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or QThread.currentThread() == app.thread():
            return func()
        self._ensure_bridge()
        if self._bridge is None:
            return func()
        return self._bridge.invoke(func)


class ScopedPluginHost:
    """呼び出し元 plugin_id に閉じたホスト。他プラグインの設定は触れない。"""

    def __init__(self, host: PluginHost, plugin_id: str):
        """親ホストと plugin_id を固定する。

        Args:
            host: 親の PluginHost。
            plugin_id: このスコープのプラグイン ID。
        """
        self._host = host
        self._plugin_id = plugin_id
        self._root = None
        self._get_text = None

    def bind_plugin(self, root, get_text) -> None:
        """プラグインルートと get_text を後から結ぶ。

        Args:
            root: プラグインルート。
            get_text: 文言取得関数。
        """
        self._root = root
        self._get_text = get_text

    def get_text(self, key: str, **kwargs) -> str:
        """結ばれた get_text で文言を取り、無ければアプリの文言を使う。

        Args:
            key: 文言キー。
            kwargs: format に渡す値。

        Returns:
            取得した文字列。
        """
        if self._get_text is not None:
            return self._get_text(key, **kwargs)
        return language_manager.get_text(key, **kwargs)

    def expand_text(self, value) -> str:
        """文字列全体が {key} のときだけ文言にする。

        Args:
            value: 展開する値。

        Returns:
            展開後の文字列。
        """
        return expand_plugin_text(value, self.get_text)

    def register_config_json(self, name: str) -> None:
        """このプラグインの config JSON から設定項目を登録する。

        Args:
            name: config ディレクトリ内のファイル名。
        """
        self._host._register_config_json(self._plugin_id, name, self._root)

    def register_sidebar(self, sidebar_id: str, title: str, widget_or_layout, aliases=None) -> None:
        """このプラグインのサイドバーを登録する。

        Args:
            sidebar_id: サイドバー ID。
            title: 表示タイトル。
            widget_or_layout: ウィジェット、またはレイアウト。
            aliases: 切替アクションのエイリアス。
        """
        self._host._register_sidebar(self._plugin_id, sidebar_id, title, widget_or_layout, aliases)

    def required_setting_sidebar(self):
        """このプラグインの必須設定フォームを作る。

        Returns:
            PluginConfigForm。
        """
        return self._host._required_setting_sidebar(self._plugin_id)

    def register_config_sidebar(self, sidebar_id: str, title: str, aliases=None) -> None:
        """このプラグインの設定フォームをサイドバーとして登録する。

        Args:
            sidebar_id: サイドバー ID。
            title: 表示タイトル。
            aliases: 切替アクションのエイリアス。
        """
        self._host._register_config_sidebar(self._plugin_id, sidebar_id, title, aliases)

    def unregister_sidebar(self, sidebar_id: str) -> None:
        """このプラグインのサイドバー登録を外す。

        Args:
            sidebar_id: サイドバー ID。
        """
        self._host._unregister_sidebar(self._plugin_id, sidebar_id)

    def register_action(self, action_id, label, callback, aliases=None) -> None:
        """このプラグインのアクションを登録する。

        Args:
            action_id: ローカル ID。
            label: 表示ラベル。
            callback: 実行する関数。
            aliases: エイリアス。
        """
        self._host._register_action(self._plugin_id, action_id, label, callback, aliases)

    def unregister_action(self, action_id) -> None:
        """このプラグインのアクションを外す。

        Args:
            action_id: ローカル ID。
        """
        self._host._unregister_action(self._plugin_id, action_id)

    def register_filter(self, filter_id: str, title: str, process) -> None:
        """このプラグインのフィルターを登録する。

        Args:
            filter_id: ローカル ID。
            title: 表示名。
            process: 画像を加工する関数。
        """
        self._host._register_filter(self._plugin_id, filter_id, title, process)

    def unregister_filter(self, filter_id: str) -> None:
        """このプラグインのフィルターを外す。

        Args:
            filter_id: ローカル ID。
        """
        self._host._unregister_filter(self._plugin_id, filter_id)

    def load_ui(self, data_or_path):
        """.ui のバイト列またはパスからウィジェットを作る。

        Args:
            data_or_path: .ui のバイト列、またはファイルパス。

        Returns:
            読み込んだウィジェット。
        """
        return self._host.load_ui(data_or_path)

    def register_config(
        self,
        key: str,
        value_type,
        default=None,
        label=None,
        description=None,
        choices=None,
        minimum=None,
        maximum=None,
        step=None,
        path_kind=None,
        path_filter=None,
        sync=False,
        reload=False,
        multiple=False,
        suffix=None,
        required=False,
    ) -> None:
        """このプラグインの設定項目を登録する。

        Args:
            key: 項目キー。
            value_type: 設定の種別。
            default: 初期値。
            label: 表示名。
            description: 説明。
            choices: choice の候補。
            minimum: 範囲の下限。
            maximum: 範囲の上限。
            step: 範囲の刻み。
            path_kind: file または directory。
            path_filter: パス選択のフィルタ。
            sync: 数値の即時保存。
            reload: 保存後の再読み込み。
            multiple: 複数選択。
            suffix: 数値の接尾辞。
            required: 空の保存を拒むか。
        """
        self._host._register_config(
            self._plugin_id,
            key,
            value_type,
            default,
            label,
            description,
            choices,
            minimum,
            maximum,
            step,
            path_kind,
            path_filter,
            sync,
            reload,
            multiple,
            suffix,
            required,
        )

    def get_config(self, key: str, default: Any = None):
        """このプラグインの設定値を返す。

        Args:
            key: 項目キー。
            default: 保存が無いときの値。

        Returns:
            変換後の値。
        """
        return self._host._get_plugin_config(self._plugin_id, key, default)

    def set_config(self, key: str, value) -> bool:
        """このプラグインの設定値を保存する。

        Args:
            key: 項目キー。
            value: 保存する値。

        Returns:
            保存できれば True。
        """
        return self._host._set_plugin_config(self._plugin_id, key, value)

    def delete_config(self, key: str) -> bool:
        """このプラグインの保存値を消す。

        Args:
            key: 項目キー。

        Returns:
            削除できれば True。
        """
        return self._host._delete_plugin_config(self._plugin_id, key)

    def reset_config(self, key: str) -> bool:
        """保存済みoverrideを削除し、schema defaultへ戻して通知する。

        Args:
            key: 項目キー。

        Returns:
            削除できれば True。
        """
        return self._host._reset_plugin_config(self._plugin_id, key)

    def get_app_config(self):
        """アプリ設定の language、viewer、cache、ui_font を読み取り専用で返す。

        Returns:
            読み取り専用の設定。
        """
        return self._host._app_config_snapshot()

    def get_current(self, key: str):
        """本体の現在値を読む。

        Args:
            key: 現在値のキー。

        Returns:
            読めた値。失敗時は None。
        """
        return self._host._current_value(key)

    def reload_current(self, page=None) -> bool:
        """現在の表示を読み直す。

        Args:
            page: 読み直すページ。

        Returns:
            読み直せれば True。
        """
        return bool(self._host.reload_current(page))

    def on(self, event: str, callback: Callable) -> None:
        """このプラグインのイベント購読を足す。

        Args:
            event: イベント名。
            callback: 呼ぶ関数。
        """
        self._host._on(self._plugin_id, event, callback)

    def off(self, event: str, callback: Optional[Callable] = None) -> None:
        """このプラグインのイベント購読を外す。

        Args:
            event: イベント名。
            callback: 外す関数。None ならそのイベントを全部外す。
        """
        self._host._off(self._plugin_id, event, callback)

    def ask_password(self, file_path: str, mismatch: bool = False, verify=None):
        """アーカイブパスワードを尋ねる。

        Args:
            file_path: 対象ファイル。
            mismatch: True なら不一致として開く。
            verify: 検証する関数。

        Returns:
            採用したパスワード。取消なら None。
        """
        return self._host.ask_password(file_path, mismatch=mismatch, verify=verify)

    def show_dialog(self, name: str, **kwargs):
        """名前に応じたダイアログを開く。

        Args:
            name: ダイアログ名。
            kwargs: ダイアログへ渡す引数。

        Returns:
            ダイアログの結果。未対応なら None。
        """
        return self._host.show_dialog(name, **kwargs)

    def run_action(self, action_id: str, **kwargs) -> bool:
        """アクションを実行する。

        Args:
            action_id: アクション ID。
            kwargs: 追加引数。

        Returns:
            実行できれば True。
        """
        return self._host.run_action(action_id, **kwargs)

    def report_error(self, where, exc) -> None:
        """このプラグインのエラーを記録する。

        Args:
            where: 発生箇所の名前。
            exc: 例外。
        """
        self._host.report_error(where, exc, plugin_id=self._plugin_id)

    def registered_formats(self) -> list[FormatSpec]:
        """このプラグインが宣言した担当形式を返す。

        Returns:
            FormatSpec のリスト。
        """
        return self._host.formats_for(self._plugin_id)

    def has_pending_sidebars(self) -> bool:
        """サイドバー登録が1件でもあれば True。

        Returns:
            登録があれば True。
        """
        return bool(self._host.sidebars_for(self._plugin_id))
