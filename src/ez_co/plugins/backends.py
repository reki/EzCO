"""プラグイン読み込みバックエンド。DLL は口だけ残す。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Protocol

from ez_co.plugins.zip_loader import load_zip_plugin
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)


class LoaderBackend(Protocol):
    def can_load(self, path: Path) -> bool: ...
    def load(self, path: Path, host=None) -> Optional[Any]: ...


class ZipPythonBackend:
    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() == ".zip"

    def load(self, path: Path, host=None):
        return load_zip_plugin(path, host=host)


class DllBackend:
    def can_load(self, path: Path) -> bool:
        return path.suffix.lower() == ".dll"

    def load(self, path: Path, host=None):
        logger.warning(get_log_text("plugin_dll_unsupported", path=path))
        return None
