import sys
import os
from pathlib import Path

def is_nuitka() -> bool:
    """
    nuitkaでコンパイルされているかどうかを確認
    """
    is_nuitka_compiled = "__compiled__" in globals()
    is_nuitka_onefile = "NUITKA_ONEFILE_PARENT" in os.environ
    return is_nuitka_compiled or is_nuitka_onefile

def get_project_root() -> Path:
    """exe化/非exe化両対応でプロジェクトルートを返す"""
    # nuitkaでコンパイルされた場合を優先チェック
    if is_nuitka():
        # sys.argv[0]を使用（デバッグ情報で正しいパスが確認済み）
        argv0_path = sys.argv[0]
        if argv0_path and os.path.isfile(argv0_path):
            exe_dir = os.path.dirname(os.path.abspath(argv0_path))
            path = Path(exe_dir).resolve()
            return path
        # フォールバック: sys.executable
        if sys.executable and os.path.isfile(sys.executable):
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            path = Path(exe_dir).resolve()
            return path

    # 他のフリーザー（PyInstallerなど）でコンパイルされた場合
    elif getattr(sys, 'frozen', False):
        path = Path(sys.executable).parent.resolve()
        return path
    # 開発環境
    else:
        # src/ez_co/utils/から見てプロジェクトルート
        path = Path(__file__).parent.parent.parent.parent.resolve()
        return path
