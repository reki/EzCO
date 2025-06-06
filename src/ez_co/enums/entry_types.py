from enum import Enum
class EntryType(Enum):
    """履歴エントリのタイプ"""
    FILE = "file"
    FOLDER = "folder"
    @classmethod
    def get_display_name(cls, entry_type) -> str:
        """表示名を取得"""
        if entry_type == cls.FILE:
            return "ファイル"
        elif entry_type == cls.FOLDER:
            return "フォルダ"
        else:
            return "不明"
    @classmethod
    def from_string(cls, value: str):
        """文字列からenum値を取得"""
        try:
            return cls(value)
        except ValueError:
            return cls.FILE  # デフォルトはファイル 