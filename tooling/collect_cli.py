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
from tooling.release_layout import BUNDLE_NAME, stage_release_dir

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
    zip_stem = f"EzCo-v{version}-release"
    zip_path = root / f"{zip_stem}.zip"

    if zip_path.is_file():
        print("Removing existing release zip file...")
        zip_path.unlink()

    with tempfile.TemporaryDirectory() as td:
        inner = Path(td) / BUNDLE_NAME
        stage_release_dir(inner, root, consume_exe=not skip_build)

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
