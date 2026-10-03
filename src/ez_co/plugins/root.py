"""プラグイン内リソースへアクセスするルート。プラグインはメソッド名だけ使う。"""
from __future__ import annotations

import zipfile
from pathlib import Path


def _normalize(relative_path: str) -> str:
    """相対パスの区切りをスラッシュにし、先頭のスラッシュを除く。

    Args:
        relative_path: 対象パス。

    Returns:
        正規化した文字列。
    """
    return str(relative_path or "").replace("\\", "/").lstrip("/")


def resource_relative(kind: str, relative_path: str) -> str:
    """resources/{kind}/ からの相対パスを返し、register_config_json もこれを使い read_config は呼ばない。

    Args:
        kind: ui、assets、config などの種別。
        relative_path: 種別ディレクトリ内の相対パス。

    Returns:
        resources/{kind}/ から始まるパス。

    Raises:
        KeyError: 空、絶対パス、ドライブ、または .. を含むとき。
    """
    name = _normalize(relative_path)
    if not name:
        raise KeyError(relative_path)
    relative = Path(name)
    if relative.is_absolute() or relative.drive or ".." in relative.parts:
        raise KeyError(relative_path)
    return f"resources/{_normalize(kind)}/{name}"


class ZipPluginSource:
    """ZIP 内のファイルを名前で読むソース。"""

    def __init__(self, archive: zipfile.ZipFile):
        """開いている ZipFile を保持する。

        Args:
            archive: 開いた ZipFile。
        """
        self.archive = archive

    def read_bytes(self, name: str) -> bytes:
        """ZIP 内の名前に対応するバイト列を読む。

        Args:
            name: ZIP 内の名前。

        Returns:
            ファイルのバイト列。
        """
        return self.archive.read(name)

    def exists(self, name: str) -> bool:
        """ZIP 内にその名前があるか返す。

        Args:
            name: ZIP 内の名前。

        Returns:
            あれば True。
        """
        try:
            self.archive.getinfo(name)
            return True
        except KeyError:
            # getinfo に無い名前は一覧で探し直す。
            return name in self.archive.namelist()

    def namelist(self) -> list[str]:
        """ZIP 内の名前をスラッシュ区切りで返す。

        Returns:
            名前のリスト。
        """
        return [item.replace("\\", "/") for item in self.archive.namelist()]

    def close(self) -> None:
        """ZIP を閉じる。"""
        self.archive.close()


class DirPluginSource:
    """ディレクトリをプラグインソースとして読む。"""

    def __init__(self, root: Path):
        """ルートディレクトリを保持する。

        Args:
            root: プラグインのルート。
        """
        self.root = Path(root)
        self.archive = None

    def _resolve(self, name: str) -> Path:
        """相対名をルート内のパスにする。

        Args:
            name: ルートからの相対名。

        Returns:
            ルート内のパス。

        Raises:
            KeyError: 絶対パス、ドライブ、または .. を含むとき。
        """
        relative = Path(_normalize(name))
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise KeyError(name)
        return self.root.joinpath(*relative.parts)

    def read_bytes(self, name: str) -> bytes:
        """ルート内のファイルを読む。

        Args:
            name: ルートからの相対名。

        Returns:
            ファイルのバイト列。

        Raises:
            KeyError: ファイルが無い、または名前がルート外のとき。
        """
        path = self._resolve(name)
        if not path.is_file():
            raise KeyError(name)
        return path.read_bytes()

    def exists(self, name: str) -> bool:
        """ルート内にそのファイルがあるか返す。

        Args:
            name: ルートからの相対名。

        Returns:
            ファイルなら True。名前が不正なら False。
        """
        try:
            return self._resolve(name).is_file()
        except KeyError:
            # ルート外の名前は無いものとして False を返す。
            return False

    def namelist(self) -> list[str]:
        """ルート以下のファイルをスラッシュ区切りの相対名で返す。

        Returns:
            相対名のリスト。
        """
        names = []
        for path in self.root.rglob("*"):
            if path.is_file():
                names.append(path.relative_to(self.root).as_posix())
        return names

    def close(self) -> None:
        """ディレクトリソースは閉じる対象が無い。"""
        return None


def open_plugin_source(path: Path):
    """ディレクトリならディレクトリソース、それ以外は ZIP ソースを開く。

    Args:
        path: プラグインのパス。

    Returns:
        DirPluginSource または ZipPluginSource。
    """
    path = Path(path)
    if path.is_dir():
        return DirPluginSource(path)
    return ZipPluginSource(zipfile.ZipFile(path, "r"))


class PluginRoot:
    """プラグインから resources と任意パスを読む入口。"""

    def __init__(self, root_path: Path, source, get_text, host):
        """ソース、文言関数、ホストを保持する。

        Args:
            root_path: プラグインのパス。
            source: バイト列を読むソース。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
        self.zip_path = Path(root_path)
        self._source = source
        self._lang_cache = {}
        self.get_text = get_text
        self.host = host

    def read_bytes(self, relative_path: str) -> bytes:
        """プラグイン内の相対パスをバイト列で読む。

        Args:
            relative_path: プラグインルートからの相対パス。

        Returns:
            バイト列。
        """
        return self._source.read_bytes(_normalize(relative_path))

    def exists(self, relative_path: str) -> bool:
        """プラグイン内にその相対パスがあるか返す。

        Args:
            relative_path: プラグインルートからの相対パス。

        Returns:
            あれば True。
        """
        return self._source.exists(_normalize(relative_path))

    def read_ui(self, relative_path: str) -> bytes:
        """resources/ui のファイルを読む。

        Args:
            relative_path: ui ディレクトリ内の相対パス。

        Returns:
            バイト列。
        """
        return self.read_bytes(resource_relative("ui", relative_path))

    def read_asset(self, relative_path: str) -> bytes:
        """resources/assets のファイルを読む。

        Args:
            relative_path: assets ディレクトリ内の相対パス。

        Returns:
            バイト列。
        """
        return self.read_bytes(resource_relative("assets", relative_path))

    def read_config(self, relative_path: str) -> bytes:
        """resources/config のファイルを読む。

        Args:
            relative_path: config ディレクトリ内の相対パス。

        Returns:
            バイト列。
        """
        return self.read_bytes(resource_relative("config", relative_path))


ZipPluginRoot = PluginRoot
