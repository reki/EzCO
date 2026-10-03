"""プラグイン読み込みバックエンド。DLL は口だけ残す。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Protocol

from ez_co.plugins.zip_loader import load_plugin, peek_manifest
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)


class LoaderBackend(Protocol):
    """プラグインを読めるかの判定と読み込みを行うバックエンド。"""

    def can_load(self, path: Path) -> bool:
        """このバックエンドが path を読めるか返す。

        Args:
            path: 判定するパス。

        Returns:
            読めるなら True。
        """
        ...

    def load(self, path: Path, host=None) -> Optional[Any]:
        """path のプラグインを読み込む。

        Args:
            path: 読み込むパス。
            host: 渡すホスト。

        Returns:
            読み込み結果。読めなければ None。
        """
        ...


class ZipPythonBackend:
    """ディレクトリまたは ZIP の Python プラグインを読む。"""

    def can_load(self, path: Path) -> bool:
        """ZIP ファイル、または manifest.json があるディレクトリなら True。

        Args:
            path: 判定するパス。

        Returns:
            読めるなら True。
        """
        if path.is_file():
            return path.suffix.lower() == ".zip"
        return path.is_dir() and (path / "manifest.json").is_file()

    def peek(self, path: Path) -> dict:
        """実体化せず manifest の概要を読む。

        Args:
            path: 対象の ZIP またはディレクトリ。

        Returns:
            id、name、version、formats、sidebar を持つ dict。
        """
        return peek_manifest(path)

    def load(self, path: Path, host=None):
        """ZIP またはディレクトリのプラグインを読み込む。

        Args:
            path: 読み込むパス。
            host: 渡すホスト。

        Returns:
            manifest、インスタンス、root、アーカイブの組。
        """
        return load_plugin(path, host=host)


class DllBackend:
    """DLL プラグイン用の口。読み込みは未対応。"""

    def can_load(self, path: Path) -> bool:
        """拡張子が .dll なら True。

        Args:
            path: 判定するパス。

        Returns:
            .dll なら True。
        """
        return path.suffix.lower() == ".dll"

    def load(self, path: Path, host=None):
        """DLL は未対応なので警告して何も返さない。

        Args:
            path: 対象パス。
            host: 渡すホスト。使わない。
        """
        logger.warning(get_log_text("plugin_dll_unsupported", path=path))
        return None
