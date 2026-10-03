"""プラグイン設定を DB に紐づけるときの plugin_id ハッシュ。"""
from __future__ import annotations

import hashlib

# プラグイン ID をハッシュするときのソルト。
PLUGIN_SETTINGS_SALT = b"ezco.plugin_settings.v1"


def hash_plugin_id(plugin_id: str) -> str:
    """プラグイン ID を設定 DB 用の SHA-256 十六進にする。

    Args:
        plugin_id: ハッシュする ID。

    Returns:
        ソルト付き SHA-256 の十六進。
    """
    raw = str(plugin_id or "").encode("utf-8")
    return hashlib.sha256(PLUGIN_SETTINGS_SALT + b"\0" + raw).hexdigest()
