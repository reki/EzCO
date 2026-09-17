"""プラグイン内リソースへアクセスするルート。プラグインはメソッド名だけ使う。"""
from __future__ import annotations

import zipfile
from pathlib import Path


def _normalize(relative_path: str) -> str:
    return str(relative_path or "").replace("\\", "/").lstrip("/")


def resource_relative(kind: str, relative_path: str) -> str:
    """resources/{kind}/ からの相対パス。register_config_json もこれを使う（read_config は呼ばない）。"""
    name = _normalize(relative_path)
    if not name:
        raise KeyError(relative_path)
    relative = Path(name)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise KeyError(relative_path)
    return f"resources/{_normalize(kind)}/{name}"


class ZipPluginSource:
    def __init__(self, archive: zipfile.ZipFile):
        self.archive = archive

    def read_bytes(self, name: str) -> bytes:
        return self.archive.read(name)

    def exists(self, name: str) -> bool:
        try:
            self.archive.getinfo(name)
            return True
        except KeyError:
            return name in self.archive.namelist()

    def namelist(self) -> list[str]:
        return [item.replace("\\", "/") for item in self.archive.namelist()]

    def close(self) -> None:
        self.archive.close()


class DirPluginSource:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.archive = None

    def _resolve(self, name: str) -> Path:
        relative = Path(_normalize(name))
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise KeyError(name)
        return self.root.joinpath(*relative.parts)

    def read_bytes(self, name: str) -> bytes:
        path = self._resolve(name)
        if not path.is_file():
            raise KeyError(name)
        return path.read_bytes()

    def exists(self, name: str) -> bool:
        try:
            return self._resolve(name).is_file()
        except KeyError:
            return False

    def namelist(self) -> list[str]:
        names = []
        for path in self.root.rglob("*"):
            if path.is_file():
                names.append(path.relative_to(self.root).as_posix())
        return names

    def close(self) -> None:
        return None


def open_plugin_source(path: Path):
    path = Path(path)
    if path.is_dir():
        return DirPluginSource(path)
    return ZipPluginSource(zipfile.ZipFile(path, "r"))


class PluginRoot:
    def __init__(self, root_path: Path, source, get_text, host):
        self.zip_path = Path(root_path)
        self._source = source
        self._lang_cache = {}
        self.get_text = get_text
        self.host = host

    def read_bytes(self, relative_path: str) -> bytes:
        return self._source.read_bytes(_normalize(relative_path))

    def exists(self, relative_path: str) -> bool:
        return self._source.exists(_normalize(relative_path))

    def read_ui(self, relative_path: str) -> bytes:
        return self.read_bytes(resource_relative("ui", relative_path))

    def read_asset(self, relative_path: str) -> bytes:
        return self.read_bytes(resource_relative("assets", relative_path))

    def read_config(self, relative_path: str) -> bytes:
        return self.read_bytes(resource_relative("config", relative_path))


ZipPluginRoot = PluginRoot
