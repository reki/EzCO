"""
プロジェクト初期化（旧 init.sh 相当）。`poetry run init-env`。
"""
from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


MINGW_URL = (
    "https://github.com/niXman/mingw-builds-binaries/releases/download/"
    "13.2.0-rt_v11-rev1/x86_64-13.2.0-release-posix-seh-ucrt-rt_v11-rev1.7z"
)


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _compiler_found(bin_dir: Path) -> bool:
    if (bin_dir / "mingw64" / "bin" / "gcc.exe").is_file():
        print("MinGW-w64がbinディレクトリに見つかりました")
        return True
    if shutil.which("cl.exe"):
        print("Microsoft Visual Studio C++コンパイラがシステムに見つかりました")
        return True
    if shutil.which("gcc.exe") or shutil.which("gcc"):
        print("GCCコンパイラがシステムに見つかりました")
        return True
    return False


def _maybe_download_mingw(bin_dir: Path) -> bool:
    print("")
    print("推奨オプション:")
    print("1. Microsoft Visual Studio Build Tools (推奨)")
    print("   - WindowsでのPython開発標準")
    print("   - 公式Pythonとの互換性が最高")
    print("   - ダウンロード: https://aka.ms/buildtools")
    print("")
    print("2. MinGW-w64 (軽量オプション)")
    print("   - 軽量で無料")
    print("   - 自動ダウンロード可能")
    print("")
    try:
        ans = input("MinGW-w64を自動ダウンロードしますか？ (y/N): ").strip().lower()
    except EOFError:
        ans = ""
    if ans not in ("y", "yes"):
        print(
            "Microsoft Visual Studio Build Toolsの手動インストールを推奨します\n"
            "インストール後、再度 `poetry run init-env` を実行してください"
        )
        return False

    print("MinGW-w64をダウンロード中...")
    bin_dir.mkdir(parents=True, exist_ok=True)
    archive = bin_dir / "mingw64.7z"
    try:
        print("ダウンロード中...")
        urllib.request.urlretrieve(MINGW_URL, archive)
    except OSError as e:
        print(f"ダウンロードに失敗しました: {e}", file=sys.stderr)
        return False

    print("展開中...")
    seven = shutil.which("7z")
    if seven:
        r = subprocess.run([seven, "x", str(archive)], cwd=str(bin_dir))
        if r.returncode != 0:
            print("7z による展開に失敗しました。", file=sys.stderr)
            return False
    else:
        print(
            "エラー: 7-Zip (7z) が PATH にありません。\n"
            f"手動で {archive} を {bin_dir} に展開し、"
            "mingw64/bin/gcc.exe があることを確認してください。"
        )
        return False

    try:
        archive.unlink(missing_ok=True)
    except OSError:
        pass

    if (bin_dir / "mingw64" / "bin" / "gcc.exe").is_file():
        print("MinGW-w64のインストールが完了しました")
        return True

    print("警告: MinGW-w64の自動インストールが失敗しました")
    return False


def main() -> None:
    root = _project_root()
    bin_dir = root / "bin"

    print("=== EzCO プロジェクト初期化スクリプト ===")
    print(f"初期化開始時刻: {datetime.datetime.now()}")
    print(f"プロジェクトルート: {root}")

    print("=== 依存関係のインストール ===")
    if shutil.which("poetry") is None:
        print(
            "エラー: Poetryがインストールされていません\n"
            "Poetryをインストールしてから再度実行してください\n"
            "インストール方法: https://python-poetry.org/docs/#installation",
            file=sys.stderr,
        )
        raise SystemExit(1)

    subprocess.run(["poetry", "--version"], cwd=str(root), check=True)
    print("Python依存関係をインストール中...")
    subprocess.run(["poetry", "install"], cwd=str(root), check=True)

    print("=== C++コンパイラのチェック ===")
    bin_dir.mkdir(parents=True, exist_ok=True)

    found = _compiler_found(bin_dir)
    if not found:
        print("C++コンパイラが見つかりません。")
        found = _maybe_download_mingw(bin_dir)

    print("=== セットアップ確認 ===")
    print("Python環境を確認中...")
    subprocess.run(["poetry", "run", "python", "--version"], cwd=str(root), check=True)
    print("Nuitkaを確認中...")
    subprocess.run(
        ["poetry", "run", "python", "-m", "nuitka", "--version"],
        cwd=str(root),
        check=True,
    )

    if found:
        print("✓ C++コンパイラが利用可能です")
    else:
        print("⚠ C++コンパイラが見つかりません")
        print(
            "  手動でMicrosoft Visual Studio Build ToolsまたはMinGW-w64をインストールしてください"
        )

    print("=== 初期化完了 ===")
    print(f"初期化終了時刻: {datetime.datetime.now()}")
    print("")
    print("次のステップ:")
    print("1. ビルドを実行: poetry run build")
    print("2. セーフモードでビルド: poetry run build -- --safe-mode")
    print("")
    print("注意: 初回ビルド時にNuitkaが追加のコンポーネントをダウンロードする場合があります")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        raise SystemExit(e.returncode) from e
