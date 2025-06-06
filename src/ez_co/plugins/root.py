"""ZIP 内リソースへアクセスするルート。プラグインはメソッド名だけ使う。"""
from __future__ import annotations

import zipfile
from pathlib import Path


class ZipPluginRoot:
    def __init__(self, zip_path: Path, archive: zipfile.ZipFile, get_text, host):
        self.zip_path = zip_path
        self._archive = archive
        self._lang_cache = {}
        self.get_text = get_text
        self.host = host

    def read_bytes(self, relative_path: str) -> bytes:
        return self._archive.read(self._normalize(relative_path))

    def exists(self, relative_path: str) -> bool:
        name = self._normalize(relative_path)
        try:
            self._archive.getinfo(name)
            return True
        except KeyError:
            return name in self._archive.namelist()

    def _normalize(self, relative_path: str) -> str:
        return str(relative_path or "").replace("\\", "/").lstrip("/")
