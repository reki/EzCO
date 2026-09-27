"""本体の表示用情報。src/ez_co/resources/about から読む。"""
from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

# src/ からの相対パス。このファイル自身は識別子に入れない。
INFO_JSON_RELATIVE = "ez_co/resources/about/info.json"
BUILD_ID_DISPLAY_LENGTH = 16


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
        "hash": str(data.get("hash") or "").strip(),
    }


def source_tree_hash(src_root: Path) -> str:
    """src 配下の通常ファイルを、パス順の1本の SHA-256 にする。"""
    files = []
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts:
            continue
        relative = path.relative_to(src_root).as_posix()
        if relative == INFO_JSON_RELATIVE:
            continue
        files.append((relative, path))
    aggregate = hashlib.sha256()
    for relative, path in sorted(files, key=lambda item: item[0]):
        digest = hashlib.sha256(path.read_bytes()).digest()
        aggregate.update(relative.encode("utf-8"))
        aggregate.update(b"\0")
        aggregate.update(digest)
    return aggregate.hexdigest()


def short_build_id(build_id: str) -> str:
    """ダイアログに出す先頭だけ。元の64桁は呼び出し側が持つ。"""
    return build_id[:BUILD_ID_DISPLAY_LENGTH]


def current_build_id() -> str:
    """Nuitka 版は保存値、ソース起動はその場の計算。info.json には書かない。"""
    from ez_co.utils.path_utils import get_project_root, is_nuitka

    if is_nuitka():
        return load_app_info().get("hash") or "unknown"
    src_root = get_project_root() / "src"
    if not src_root.is_dir():
        return "unknown"
    return source_tree_hash(src_root)


def build_id_error_header() -> str:
    """未処理例外ログの先頭。計算は current_build_id に任せる。"""
    info = load_app_info()
    version = info.get("version") or ""
    return f"EzCo version={version}\nBuild id={current_build_id()}"


@contextmanager
def stamped_info_json(info_path: Path, build_id: str):
    """hash だけを書き、抜けるとき（Ctrl+C を含む）に元のバイト列へ戻す。"""
    original = info_path.read_bytes()
    data = json.loads(original.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("about info must be an object")
    data["hash"] = build_id
    info_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        yield
    finally:
        info_path.write_bytes(original)
