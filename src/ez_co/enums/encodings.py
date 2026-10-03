"""文字エンコーディングの種別とアーカイブ向けの組み合わせ。"""
from enum import Enum
from typing import Dict, List, Tuple
class EncodingType(Enum):
    """エンコーディングタイプの列挙"""
    # UTF-8
    UTF8 = "utf-8"
    # CP437
    CP437 = "cp437"
    # Shift_JIS
    SHIFT_JIS = "shift_jis"
    # EUC-JP
    EUC_JP = "euc-jp"
    # ISO-2022-JP
    ISO_2022_JP = "iso-2022-jp"


class EncodingInfo:
    """エンコーディング情報を保持するクラス"""
    # エンコーディングタイプと表示名のマッピング
    DISPLAY_NAMES: Dict[EncodingType, str] = {
        EncodingType.UTF8: "UTF-8",
        EncodingType.CP437: "CP437 (DOS)",
        EncodingType.SHIFT_JIS: "Shift_JIS",
        EncodingType.EUC_JP: "EUC-JP",
        EncodingType.ISO_2022_JP: "ISO-2022-JP"
    }
    # エンコーディングタイプと説明のマッピング
    DESCRIPTIONS: Dict[EncodingType, str] = {
        EncodingType.UTF8: "Unicode UTF-8 エンコーディング",
        EncodingType.CP437: "DOS/Windows のコードページ 437",
        EncodingType.SHIFT_JIS: "日本語 Shift_JIS エンコーディング",
        EncodingType.EUC_JP: "日本語 EUC-JP エンコーディング",
        EncodingType.ISO_2022_JP: "日本語 ISO-2022-JP エンコーディング"
    }
    @classmethod
    def get_display_name(cls, encoding_type: EncodingType) -> str:
        """エンコーディングタイプの表示名を取得する。

        Args:
            encoding_type: 表示名を引くエンコーディングタイプ。

        Returns:
            対応する表示名。無ければ値の文字列。
        """
        return cls.DISPLAY_NAMES.get(encoding_type, str(encoding_type.value))

    @classmethod
    def get_description(cls, encoding_type: EncodingType) -> str:
        """エンコーディングタイプの説明を取得する。

        Args:
            encoding_type: 説明を引くエンコーディングタイプ。

        Returns:
            対応する説明。無ければ空文字。
        """
        return cls.DESCRIPTIONS.get(encoding_type, "")

    @classmethod
    def get_all_encoding_types(cls) -> List[EncodingType]:
        """すべてのエンコーディングタイプを取得する。

        Returns:
            定義されているエンコーディングタイプの一覧。
        """
        return list(EncodingType)

    @classmethod
    def get_encoding_combinations_for_archive(cls, archive_type: str) -> List[Tuple[str, str]]:
        """アーカイブタイプに応じたエンコーディング組み合わせを取得する。

        Args:
            archive_type: 組み合わせを選ぶアーカイブタイプ。

        Returns:
            エンコーディング名の組。zip、7z、rar、tar 系、それ以外で候補が変わる。
        """
        if archive_type == "zip":
            # ZIPファイルはCP437で保存されることが多い
            return [
                ('cp437', 'utf-8'),
                ('cp437', 'shift_jis'),
                ('cp437', 'euc-jp'),
                ('cp437', 'iso-2022-jp'),
                ('utf-8', 'utf-8'),
                ('shift_jis', 'utf-8'),
                ('euc-jp', 'utf-8'),
                ('iso-2022-jp', 'utf-8'),
            ]
        elif archive_type in ["7z", "rar"]:
            # 7zとRARは通常UTF-8で保存されるが、古いバージョンでは問題が発生する可能性
            return [
                ('utf-8', 'utf-8'),
                ('cp437', 'utf-8'),
                ('cp437', 'shift_jis'),
                ('shift_jis', 'utf-8'),
                ('euc-jp', 'utf-8'),
                ('iso-2022-jp', 'utf-8'),
            ]
        elif archive_type in ["tar", "tar.gz", "tar.bz2", "tar.xz"]:
            # TARはシステム依存だが、通常UTF-8
            return [
                ('utf-8', 'utf-8'),
                ('cp437', 'utf-8'),
                ('shift_jis', 'utf-8'),
                ('euc-jp', 'utf-8'),
                ('iso-2022-jp', 'utf-8'),
            ]
        else:
            # その他の形式はUTF-8を試行
            return [
                ('utf-8', 'utf-8'),
                ('cp437', 'utf-8'),
            ]

    @classmethod
    def get_default_encoding_combinations(cls) -> List[Tuple[str, str]]:
        """デフォルトのエンコーディング組み合わせを取得する。

        Returns:
            utf-8 と utf-8、cp437 と utf-8 の組。
        """
        return [
            ('utf-8', 'utf-8'),
            ('cp437', 'utf-8'),
        ]
