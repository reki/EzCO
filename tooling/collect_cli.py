"""
リリースビルド後に UserManual・言語サンプルなどを同梱した zip を生成する。`poetry run collect`
（旧 release.sh 相当）
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from tooling.build_cli import run_build

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _read_version(root: Path) -> str:
    with open(root / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    ver = data.get("project", {}).get("version")
    return str(ver) if ver else "0.0.0"


def _make_release_zip(root: Path, *, skip_build: bool) -> Path:
    exe = root / "EzCo.exe"
    if not exe.is_file():
        print(
            f"Error: {exe} が見つかりません（ビルドが成功しているか確認してください）",
            file=sys.stderr,
        )
        raise SystemExit(1)

    version = _read_version(root)
    bundle_name = "EzCO"
    zip_stem = f"EzCo-v{version}-release"
    zip_path = root / f"{zip_stem}.zip"

    if zip_path.is_file():
        print("Removing existing release zip file...")
        zip_path.unlink()

    user_manual = root / "resources" / "UserManual"
    lang_dir = root / "src" / "ez_co" / "resources" / "langs"

    with tempfile.TemporaryDirectory() as td:
        inner = Path(td) / bundle_name
        inner.mkdir(parents=True)
        (inner / "langs" / "sample").mkdir(parents=True)
        (inner / "fonts").mkdir(parents=True)
        (inner / "plugins").mkdir(parents=True)

        if skip_build:
            print("Copying EzCo.exe to release directory (preserving original)...")
            shutil.copy2(exe, inner / "EzCo.exe")
        else:
            print("Moving EzCo.exe to release directory...")
            shutil.copy2(exe, inner / "EzCo.exe")
            exe.unlink()

        if user_manual.is_dir():
            print("Copying resources/UserManual directory...")
            shutil.copytree(user_manual, inner / "UserManual")
        else:
            print("Warning: resources/UserManual directory not found")

        ja = lang_dir / "ja.json"
        en = lang_dir / "en.json"
        if ja.is_file() and en.is_file():
            print("Copying language files to langs/sample...")
            shutil.copy2(ja, inner / "langs" / "sample" / "ja.json")
            shutil.copy2(en, inner / "langs" / "sample" / "en.json")
        else:
            print(f"Warning: Language files (ja.json, en.json) not found in {lang_dir}")

        exe_size = (inner / "EzCo.exe").stat().st_size
        print(f"Executable size: {exe_size} bytes")

        archive_path = shutil.make_archive(
            str(root / zip_stem),
            "zip",
            root_dir=td,
            base_dir=bundle_name,
        )

    out = Path(archive_path)
    print(f"作成した zip: {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(
        description="リリース用 EzCo.exe と UserManual・言語サンプルを zip にまとめる（先に release ビルドを実行）"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="ビルドを省略し、既にある EzCo.exe を同梱する（zip 内容の試行用）",
    )
    args = parser.parse_args()

    root = _project_root()
    start = time.time()

    print("=== EzCO 頒布用 zip ===")
    print(f"開始: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project root: {root}")
    print(f"Version: {_read_version(root)}")

    try:
        if not args.skip_build:
            print("--- Nuitka ビルド（release） ---")
            run_build(safe_mode=False)
        else:
            print("--- ビルド省略（--skip-build） ---")

        print("--- zip 作成 ---")
        out = _make_release_zip(root, skip_build=args.skip_build)
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e

    elapsed = int(time.time() - start)
    minutes, seconds = elapsed // 60, elapsed % 60
    print(f"終了: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"所要時間: {minutes}分 {seconds}秒")
    print("")
    print(f"✅ Release archive ready: {out.name}")
    if args.skip_build:
        print("✅ Build skipped - original EzCo.exe preserved in project root")
    print("✅ Ready for GitHub release!")


if __name__ == "__main__":
    main()
