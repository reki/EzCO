"""Inno Setup 7 でインストーラを作る。`poetry run installer`（collect とは別）。"""
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


def _find_iscc() -> Path:
    for name in ("ISCC", "ISCC.exe"):
        found = shutil.which(name)
        if found:
            return Path(found)
    print(
        "Error: Inno Setup 7 の ISCC が PATH にありません。\n"
        "  winget install --id JRSoftware.InnoSetup.7\n"
        "インストール後、新しいターミナルで PATH を通してから再実行してください。",
        file=sys.stderr,
    )
    raise SystemExit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="リリース用 EzCo.exe から Inno Setup インストーラを作る（zip は作らない）"
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="ビルドを省略し、既にある EzCo.exe を使う",
    )
    args = parser.parse_args()

    root = _project_root()
    version = _read_version(root)
    start = time.time()

    print("=== EzCO インストーラ ===")
    print(f"開始: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project root: {root}")
    print(f"Version: {version}")

    iscc = _find_iscc()
    print(f"ISCC: {iscc}")

    try:
        if not args.skip_build:
            print("--- Nuitka ビルド（release） ---")
            run_build(safe_mode=False)
        else:
            print("--- ビルド省略（--skip-build） ---")

        print("--- 配置 ---")
        with tempfile.TemporaryDirectory() as td:
            inner = Path(td) / BUNDLE_NAME
            stage_release_dir(inner, root, consume_exe=False)
            output_name = f"EzCo-v{version}-setup"
            iss = root / "tooling" / "ezco.iss"
            icon = root / "src" / "ez_co" / "resources" / "icon.ico"
            if not icon.is_file():
                icon = root / "resources" / "icon.ico"
            cmd = [
                str(iscc),
                f"/DMyAppVersion={version}",
                f"/DSourceDir={inner.resolve().as_posix()}",
                f"/DOutputDir={root.resolve().as_posix()}",
                f"/DOutputBaseName={output_name}",
                str(iss),
            ]
            if icon.is_file():
                cmd.insert(-1, f"/DSetupIcon={icon.resolve().as_posix()}")
            print("--- Inno Setup ---")
            print(" ".join(cmd))
            subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e

    elapsed = int(time.time() - start)
    minutes, seconds = elapsed // 60, elapsed % 60
    print(f"終了: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"所要時間: {minutes}分 {seconds}秒")
    print("")
    print(f"✅ Installer ready: EzCo-v{version}-setup.exe")


if __name__ == "__main__":
    main()
