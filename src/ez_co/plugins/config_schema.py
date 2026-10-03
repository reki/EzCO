"""プラグイン設定 JSON を register_config の引数へ直す。{key} 展開は持たない。"""
from __future__ import annotations

import json

from ez_co.utils.language_manager import get_log_text

# 設定 JSON のフィールドで受け付けるキー。
_FIELD_KEYS = frozenset(
    {
        "key",
        "value_type",
        "default",
        "label",
        "description",
        "choices",
        "minimum",
        "maximum",
        "step",
        "path_kind",
        "path_filter",
        "sync",
        "reload",
        "multiple",
        "suffix",
        "required",
    }
)
# 設定 JSON で拒否する Enum 指定のキー。
_ENUM_KEYS = frozenset({"enum", "enum_type"})


def parse_config_json(raw, plugin_id: str = "") -> list[dict]:
    """UTF-8 JSON または list をフィールド dict の列にし、未知キーと Enum 指定はエラーにする。

    Args:
        raw: JSON の bytes、str、または list。
        plugin_id: エラー文言に載せるプラグイン ID。

    Returns:
        既知キーだけのフィールド dict の列。

    Raises:
        ValueError: JSON でない、list でない、要素がオブジェクトでない、未知キーがある、または Enum 指定のとき。
    """
    if isinstance(raw, (bytes, bytearray)):
        try:
            data = json.loads(bytes(raw).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            # UTF-8 の JSON でなければ ValueError にして返す。
            raise ValueError(
                get_log_text("plugin_config_json_invalid", plugin_id=plugin_id, error=exc)
            ) from exc
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            # JSON でなければ ValueError にして返す。
            raise ValueError(
                get_log_text("plugin_config_json_invalid", plugin_id=plugin_id, error=exc)
            ) from exc
    else:
        data = raw
    if not isinstance(data, list):
        raise ValueError(
            get_log_text("plugin_config_json_invalid", plugin_id=plugin_id, error="not a list")
        )
    rows = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(
                get_log_text("plugin_config_json_invalid", plugin_id=plugin_id, error="not an object")
            )
        extra = set(item) - _FIELD_KEYS
        if extra & _ENUM_KEYS or extra:
            raise ValueError(
                get_log_text(
                    "plugin_config_enum_invalid" if extra & _ENUM_KEYS else "plugin_config_json_invalid",
                    plugin_id=plugin_id,
                    field_key=str(item.get("key") or ""),
                    error=", ".join(sorted(extra)),
                )
            )
        choices = item.get("choices")
        if isinstance(choices, str):
            raise ValueError(
                get_log_text(
                    "plugin_config_enum_invalid",
                    plugin_id=plugin_id,
                    field_key=str(item.get("key") or ""),
                )
            )
        rows.append(dict(item))
    return rows
