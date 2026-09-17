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
    def __init__(self):
        self.root = None
        self.get_text = None
        self.host = None

    def load(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host

    def get_file_count(self, file_path):
        return 1

    def list_entries(self, file_path):
        return [_basename(file_path)]

    def read_entry(self, file_path, index):
        name = self.list_entries(file_path)[index]
        label = self.get_text("plugin.watermark")
        with open(file_path, "rb") as handle:
            data = mark_image(handle.read(), label)
        return _Entry(name, data)


class _Entry:
    def __init__(self, name, data):
        self.name = name
        self.data = data


def _basename(path):
    return str(path).replace("\\", "/").rstrip("/").split("/")[-1]
