"""頒布 zip / インストーラ共通の配置。"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path


BUNDLE_NAME = "EzCO"


def stage_release_dir(dest: Path, root: Path, *, consume_exe: bool = False) -> Path:
    """EzCo.exe と UserManual などを dest（EzCO フォルダ）に置く。"""
    exe = root / "EzCo.exe"
    if not exe.is_file():
        print(
            f"Error: {exe} が見つかりません（ビルドが成功しているか確認してください）",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / "langs" / "sample").mkdir(parents=True)
    (dest / "fonts").mkdir(parents=True)
    (dest / "plugins").mkdir(parents=True)

    print("Copying EzCo.exe to release directory...")
    shutil.copy2(exe, dest / "EzCo.exe")
    if consume_exe:
        print("Removing EzCo.exe from project root...")
        exe.unlink()

    user_manual = root / "resources" / "UserManual"
    if user_manual.is_dir():
        print("Copying resources/UserManual directory...")
        shutil.copytree(user_manual, dest / "UserManual")
    else:
        print("Warning: resources/UserManual directory not found")

    lang_dir = root / "src" / "ez_co" / "resources" / "langs"
    ja = lang_dir / "ja.json"
    en = lang_dir / "en.json"
    if ja.is_file() and en.is_file():
        print("Copying language files to langs/sample...")
        shutil.copy2(ja, dest / "langs" / "sample" / "ja.json")
        shutil.copy2(en, dest / "langs" / "sample" / "en.json")
    else:
        print(f"Warning: Language files (ja.json, en.json) not found in {lang_dir}")

    print(f"Executable size: {(dest / 'EzCo.exe').stat().st_size} bytes")
    return dest
