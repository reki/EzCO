"""EzCo 向け PNG 読み込みサンプル。

ホストは Class() のあと load(root, get_text, host) を渡す。

このサンプルは get_text だけ使う。host は load で受け取って保持する。

ホストが呼ぶ必須メソッド:
    get_file_count(path) -> int
    list_entries(path) -> [エントリ名, ...]
    read_entry(path, index) -> オブジェクト(name, data: bytes)

このサンプル固有:
    開いたことが分かるよう、画像に色とラベルを重ねている（本番では不要）。
"""
from mark import mark_image


class FileLoader:
    """単一 PNG を1ページとして読むサンプル。"""

    def __init__(self):
        """root、get_text、host の入れ物を空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None

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
        """ページ数を返す。

        Args:
            file_path: 対象ファイル。件数には使わない。

        Returns:
            常に 1。
        """
        return 1

    def list_entries(self, file_path):
        """ファイル名を1件返す。

        Args:
            file_path: 対象ファイル。

        Returns:
            末尾のファイル名を1件持つリスト。
        """
        return [_basename(file_path)]

    def read_entry(self, file_path, index):
        """色とラベルを重ねた PNG を返す。

        Args:
            file_path: 対象ファイル。
            index: エントリ番号。

        Returns:
            名前と加工後バイト列を持つエントリ。
        """
        name = self.list_entries(file_path)[index]
        label = self.get_text("plugin.watermark")
        with open(file_path, "rb") as handle:
            data = mark_image(handle.read(), label)
        return _Entry(name, data)


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


def _basename(path):
    """パスの末尾の名前を返す。

    Args:
        path: 対象パス。

    Returns:
        区切りを除いた末尾の名前。
    """
    return str(path).replace("\\", "/").rstrip("/").split("/")[-1]
