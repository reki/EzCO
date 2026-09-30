"""タブ状態ファイル（.ezs）の読み書き。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SESSION_SUFFIX = ".ezs"
SESSION_FORMAT = "ezco-session"
SESSION_VERSION = 1


def is_session_file(path: str | Path) -> bool:
    return Path(path).suffix.lower() == SESSION_SUFFIX


def load_session(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or data.get("format") != SESSION_FORMAT:
        raise ValueError("invalid session format")
    raw_tabs = data.get("tabs")
    if not isinstance(raw_tabs, list):
        raise ValueError("invalid session tabs")
    tabs = []
    for item in raw_tabs:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("path") or "").strip()
        if not file_path:
            continue
        try:
            page = int(item.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        tabs.append({
            "path": file_path,
            "page": max(page, 1),
            "pinned": item.get("pinned") is True,
        })
    try:
        current = int(data.get("current") or 0)
    except (TypeError, ValueError):
        current = 0
    return {"tabs": tabs, "current": max(current, 0)}


def save_session(path: str | Path, tabs: list[dict], current: int) -> None:
    payload = {
        "format": SESSION_FORMAT,
        "version": SESSION_VERSION,
        "current": max(int(current), 0),
        "tabs": tabs,
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
