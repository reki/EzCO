"""
Nuitka ビルド（旧 build.sh 相当）。`poetry run build` または `poetry run build -- --safe-mode`。
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ez_co.utils.app_info import source_tree_hash, stamped_info_json


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _nix_path(p: Path) -> str:
    """Nuitka に渡すパス（Windows の \\b などの誤解釈を避けるため POSIX 形式）。"""
    return str(p.resolve().as_posix())


def _prep_env(project_root: Path, env: dict[str, str]) -> dict[str, str]:
    mingw_bin = project_root / "bin" / "mingw64" / "bin"
    out = dict(env)
    if mingw_bin.is_dir():
        sep = os.pathsep
        out["PATH"] = str(mingw_bin) + sep + out.get("PATH", "")
        gcc = shutil.which("gcc.exe", path=out["PATH"]) or shutil.which(
            "gcc", path=out["PATH"]
        )
        print(f"Adding MinGW-w64 compiler to PATH...\nCompiler: {gcc or 'gcc not found in PATH'}")
    elif (project_root / "bin").is_dir():
        print(
            "binディレクトリが存在しますが、mingw64/binが見つかりません\n"
            "Note: bin directory exists but mingw64/bin not found"
        )
    return out


def _run_nuitka(project_root: Path, safe_mode: bool) -> None:
    icon_path = project_root / "resources" / "icon.ico"
    main_module = project_root / "src" / "ez_co" / "main.py"
    build_dir = project_root / "build"
    dist_dir = project_root

    print("Checking prerequisites...")
    venv_path = project_root / ".venv"
    if not venv_path.is_dir():
        print(
            f"Error: Virtual environment not found at {venv_path}\n"
            "Please run `poetry run init-env` first to set up the environment",
            file=sys.stderr,
        )
        raise SystemExit(1)
    if not icon_path.is_file():
        print(f"Error: Icon file not found at {icon_path}", file=sys.stderr)
        raise SystemExit(1)
    if not main_module.is_file():
        print(f"Error: Main module not found at {main_module}", file=sys.stderr)
        raise SystemExit(1)

    print("Creating build directories...")
    if build_dir.exists():
        print("Removing existing build directory...")
        shutil.rmtree(build_dir)
    build_dir.mkdir(parents=True)

    env = _prep_env(project_root, dict(os.environ))
    res_root = project_root / "src" / "ez_co" / "resources"
    inc_data = f"{_nix_path(res_root)}=ez_co/resources"
    out_dir = _nix_path(build_dir)
    main_arg = _nix_path(main_module)
    icon_arg = _nix_path(icon_path)

    print("Running Nuitka via current interpreter (Poetry env)...")

    common = [
        sys.executable,
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        f"--windows-icon-from-ico={icon_arg}",
        "--assume-yes-for-downloads",
        "--enable-plugin=pyside6",
        "--include-package=ez_co",
        "--include-package=PIL",
        "--include-package=yaml",
        "--include-package=pypdf",
        "--include-module=PySide6.QtPdf",
        f"--include-data-dir={inc_data}",
        f"--output-dir={out_dir}",
        "--output-filename=EzCo.exe",
    ]

    if safe_mode:
        print("Building in safe mode (no optimization options)...")
        cmd = common + [
            "--windows-console-mode=force",
            main_arg,
        ]
    else:
        print("Building with performance optimizations...")
        cmd = common + [
            "--windows-console-mode=disable",
            "--lto=yes",
            "--prefer-source-code",
            main_arg,
        ]

    info_path = res_root / "about" / "info.json"
    build_id = source_tree_hash(project_root / "src")
    print(f"Build id: {build_id}")
    with stamped_info_json(info_path, build_id):
        subprocess.run(cmd, cwd=str(project_root), env=env, check=True)

        exe = build_dir / "EzCo.exe"
        print("Build completed successfully!")
        print(f"Executable location: {exe}")

        if not exe.is_file():
            raise SystemExit("Nuitka finished but EzCo.exe was not found.")

        if safe_mode:
            dest = dist_dir / "EzCo(Debug).exe"
            print("Copying executable to project root...")
            shutil.copy2(exe, dest)
            print(f"Executable copied to: {dest}")
        else:
            dest = dist_dir / "EzCo.exe"
            print("Copying executable to project root...")
            shutil.copy2(exe, dest)
            print(f"Executable copied to: {dest}")

        shutil.rmtree(build_dir)


def run_build(*, safe_mode: bool = False) -> None:
    """Nuitka ビルドのみ（`collect` などから再利用）。"""
    _run_nuitka(_project_root(), safe_mode)


def main() -> None:
    parser = argparse.ArgumentParser(description="EzCO Nuitka build")
    parser.add_argument(
        "--safe-mode",
        action="store_true",
        help="Safe build (console, no LTO)",
    )
    args = parser.parse_args()

    root = _project_root()
    start = time.time()

    print("=== EzCO Nuitka Build ===")
    print(f"Build started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Project root: {root}")
    print(f"Virtual environment: {root / '.venv'}")

    if args.safe_mode:
        print("=== SAFE MODE: 最適化オプションなしでビルド ===")

    try:
        run_build(safe_mode=args.safe_mode)
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e

    elapsed = int(time.time() - start)
    minutes, seconds = elapsed // 60, elapsed % 60
    print(f"Build ended at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=== Build completed ===")
    print(f"Total build time: {minutes}分 {seconds}秒")


if __name__ == "__main__":
    main()
