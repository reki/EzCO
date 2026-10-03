"""履歴エントリの種別。"""
from enum import Enum
class EntryType(Enum):
    """履歴エントリのタイプ"""
    # ファイルの履歴種別
    FILE = "file"
    # フォルダの履歴種別
    FOLDER = "folder"
    @classmethod
    def get_display_name(cls, entry_type) -> str:
        """表示名を取得する。

        Args:
            entry_type: 表示名を引く種別。

        Returns:
            ファイルなら「ファイル」、フォルダなら「フォルダ」、それ以外は「不明」。
        """
        if entry_type == cls.FILE:
            return "ファイル"
        elif entry_type == cls.FOLDER:
            return "フォルダ"
        else:
            return "不明"

    @classmethod
    def from_string(cls, value: str):
        """文字列からenum値を取得する。

        Args:
            value: 変換する文字列。

        Returns:
            一致したメンバー。値が無ければファイル。
        """
        try:
            return cls(value)
        except ValueError:
            # 不明な文字列はファイルに戻す
            return cls.FILE  # デフォルトはファイル
