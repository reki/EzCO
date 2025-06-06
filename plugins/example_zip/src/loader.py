"""EzCo 向け ZIP 読み込みサンプル。

ホストは必ず次で生成する。
    FileLoader(root, get_text, host)

    root
        プラグイン ZIP 内のリソース。read_bytes / exists。
    get_text(key, **kwargs)
        プラグイン langs/{言語}.json を優先し、なければ本体の文言。
    host
        ask_password / show_dialog / run_action。

ホストが呼ぶ必須メソッド:
    supported_formats() -> [(".zip", "archive"), ...]
    get_file_count(path) -> int
    list_entries(path) -> [エントリ名, ...]
    read_entry(path, index) -> オブジェクト(name, data: bytes)

このサンプル固有:
    暗号化 ZIP（ZipCrypto / AES）なら host.ask_password でパスワードを取る。
    開いたことが分かるよう、画像に色とラベルを重ねている（本番では不要）。
"""
import pyzipper

from mark import mark_image

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


class FileLoader:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self._passwords = {}

    def supported_formats(self):
        return [(".zip", "archive")]

    def get_file_count(self, file_path):
        return len(self.list_entries(file_path))

    def list_entries(self, file_path):
        password = self._unlock(file_path)
        names = []
        with pyzipper.AESZipFile(file_path, "r") as archive:
            if password:
                archive.setpassword(password.encode("utf-8"))
            for name in archive.namelist():
                if name.endswith("/"):
                    continue
                if _suffix(name) in IMAGE_SUFFIXES:
                    names.append(name)
        return names

    def read_entry(self, file_path, index):
        name = self.list_entries(file_path)[index]
        password = self._unlock(file_path)
        label = self.get_text("plugin.watermark")
        with pyzipper.AESZipFile(file_path, "r") as archive:
            data = mark_image(archive.read(name, pwd=_pwd_bytes(password)), label)
        return _Entry(name, data)

    def _unlock(self, file_path):
        cached = self._passwords.get(file_path)
        if cached is not None:
            return cached
        if not _is_encrypted(file_path):
            self._passwords[file_path] = ""
            return ""
        password = self.host.ask_password(file_path, verify=lambda pwd: _verify_zip(file_path, pwd))
        if password is None:
            raise RuntimeError("password cancelled")
        self._passwords[file_path] = password
        return password


class _Entry:
    def __init__(self, name, data):
        self.name = name
        self.data = data


def _is_encrypted(file_path):
    with pyzipper.AESZipFile(file_path, "r") as archive:
        return any(info.flag_bits & 0x1 for info in archive.infolist() if not info.is_dir())


def _verify_zip(file_path, password):
    pwd = _pwd_bytes(password)
    try:
        with pyzipper.AESZipFile(file_path, "r") as archive:
            encrypted = [info for info in archive.infolist() if (info.flag_bits & 0x1) and not info.is_dir()]
            if not encrypted:
                return True
            first = encrypted[0]
            archive.read(first, pwd=pwd)
            return True
    except RuntimeError:
        return False


def _pwd_bytes(password):
    if not password:
        return None
    return password.encode("utf-8")


def _basename(path):
    return str(path).replace("\\", "/").rstrip("/").split("/")[-1]


def _suffix(name):
    base = _basename(name)
    dot = base.rfind(".")
    if dot < 0:
        return ""
    return base[dot:].lower()
