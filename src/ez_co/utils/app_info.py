"""本体の表示用情報。src/ez_co/resources/about から読む。"""
from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_app_info() -> dict[str, Any]:
    """アプリ名・バージョン・制作者などを辞書で返す。説明は言語を分けない。"""
    raw = (
        resources.files("ez_co.resources")
        .joinpath("about", "info.json")
        .read_text(encoding="utf-8")
    )
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("about info must be an object")
    return {
        "name": str(data.get("name") or "").strip(),
        "version": str(data.get("version") or "").strip(),
        "author": str(data.get("author") or "").strip(),
        "years": str(data.get("years") or "").strip(),
        "license": str(data.get("license") or "").strip(),
        "homepage": str(data.get("homepage") or "").strip(),
        "description": str(data.get("description") or "").strip(),
    }
