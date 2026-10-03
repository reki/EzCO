"""EzCo 向け ZIP 読み込みサンプル。

ホストは Class() のあと load(root, get_text, host) を渡す。

    root
        プラグイン ZIP 内のリソース。read_bytes / exists。
    get_text(key, **kwargs)
        プラグイン resources/langs/{言語}.json を優先し、なければ本体の文言。
    host
        ask_password / show_dialog / run_action。

ホストが呼ぶ必須メソッド:
    get_file_count(path) -> int
    list_entries(path) -> [エントリ名, ...]
    read_entry(path, index) -> オブジェクト(name, data: bytes)

このサンプル固有:
    暗号化 ZIP（ZipCrypto / AES）なら host.ask_password でパスワードを取る。
    開いたことが分かるよう、画像に色とラベルを重ねている（本番では不要）。
"""
import pyzipper

from mark import mark_image

# ZIP 内で画像として開く拡張子。
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tif", ".tiff"}


class FileLoader:
    """画像入り ZIP をページとして読むサンプル。暗号化ならパスワードを尋ねる。"""

    def __init__(self):
        """root、get_text、host と、ファイルごとのパスワードを空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None
        self._passwords = {}

    def load(self, root, get_text, host):
        """root、get_text、host を保持する。

        Args:
            root: プラグインルート。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
        self.root = root
        self.get_text = get_text
        self.host = host

    def get_file_count(self, file_path):
        """画像エントリの件数を返す。

        Args:
            file_path: 対象 ZIP。

        Returns:
            画像エントリの件数。
        """
        return len(self.list_entries(file_path))

    def list_entries(self, file_path):
        """画像拡張子のエントリ名を返す。

        Args:
            file_path: 対象 ZIP。

        Returns:
            ディレクトリを除いた画像名。
        """
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
        """指定エントリを読み、色とラベルを重ねて返す。

        Args:
            file_path: 対象 ZIP。
            index: エントリ番号。

        Returns:
            名前と加工後バイト列を持つエントリ。
        """
        name = self.list_entries(file_path)[index]
        password = self._unlock(file_path)
        label = self.get_text("plugin.watermark")
        with pyzipper.AESZipFile(file_path, "r") as archive:
            data = mark_image(archive.read(name, pwd=_pwd_bytes(password)), label)
        return _Entry(name, data)

    def _unlock(self, file_path):
        """暗号化 ZIP ならパスワードを取り、結果を覚える。

        Args:
            file_path: 対象 ZIP。

        Returns:
            パスワード。暗号化でなければ空文字。

        Raises:
            RuntimeError: パスワード入力が取り消されたとき。
        """
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
    """エントリ名とバイト列。"""

    def __init__(self, name, data):
        """名前とバイト列を保持する。

        Args:
            name: エントリ名。
            data: バイト列。
        """
        self.name = name
        self.data = data


def _is_encrypted(file_path):
    """ZIP に暗号化エントリがあるか返す。

    Args:
        file_path: 対象 ZIP。

    Returns:
        暗号化フラグのあるファイルがあれば True。
    """
    with pyzipper.AESZipFile(file_path, "r") as archive:
        return any(info.flag_bits & 0x1 for info in archive.infolist() if not info.is_dir())


def _verify_zip(file_path, password):
    """パスワードで暗号化エントリを読めるか返す。

    Args:
        file_path: 対象 ZIP。
        password: 試すパスワード。

    Returns:
        読めれば True。失敗なら False。
    """
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
        # パスワードで開けなければ False を返す。
        return False


def _pwd_bytes(password):
    """パスワードを ZIP に渡すバイト列にする。

    Args:
        password: パスワード。空なら無し。

    Returns:
        UTF-8 のバイト列。空なら None。
    """
    if not password:
        return None
    return password.encode("utf-8")


def _basename(path):
    """パスの末尾の名前を返す。

    Args:
        path: 対象パス。

    Returns:
        区切りを除いた末尾の名前。
    """
    return str(path).replace("\\", "/").rstrip("/").split("/")[-1]


def _suffix(name):
    """名前の拡張子を小文字で返す。

    Args:
        name: ファイル名。

    Returns:
        ドット付きの小文字。ドットが無ければ空文字。
    """
    base = _basename(name)
    dot = base.rfind(".")
    if dot < 0:
        return ""
    return base[dot:].lower()
