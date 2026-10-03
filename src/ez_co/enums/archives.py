"""アーカイブ形式と拡張子・表示名の対応。"""
from enum import Enum
from typing import Dict, List, Set, Optional
from pathlib import Path
from ez_co.utils.language_manager import get_text
class ArchiveType(Enum):
    """アーカイブタイプの列挙"""
    # ZIP 形式
    ZIP = "zip"
    # 7z 形式
    SEVEN_ZIP = "7z"
    # RAR 形式
    RAR = "rar"
    # tar 形式
    TAR = "tar"
    # gzip 付き tar 形式
    TAR_GZ = "tar_gz"
    # bzip2 付き tar 形式
    TAR_BZ2 = "tar_bz2"
    # xz 付き tar 形式
    TAR_XZ = "tar_xz"
    # gzip 形式
    GZ = "gz"
    # bzip2 形式
    BZ2 = "bz2"
    # xz 形式
    XZ = "xz"
    # CBZ 形式
    CBZ = "cbz"
    # CBR 形式
    CBR = "cbr"
    # PDF 形式
    PDF = "pdf"


class ArchiveInfo:
    """アーカイブ情報を保持するクラス"""
    # アーカイブタイプと拡張子のマッピング
    EXTENSIONS: Dict[ArchiveType, List[str]] = {
        ArchiveType.ZIP: [".zip"],
        ArchiveType.SEVEN_ZIP: [".7z"],
        ArchiveType.RAR: [".rar"],
        ArchiveType.TAR: [".tar"],
        ArchiveType.TAR_GZ: [".tar.gz", ".tgz"],
        ArchiveType.TAR_BZ2: [".tar.bz2", ".tbz2"],
        ArchiveType.TAR_XZ: [".tar.xz", ".txz"],
        ArchiveType.GZ: [".gz"],
        ArchiveType.BZ2: [".bz2"],
        ArchiveType.XZ: [".xz"],
        ArchiveType.CBZ: [".cbz"],
        ArchiveType.CBR: [".cbr"],
        ArchiveType.PDF: [".pdf"]
    }
    # アーカイブタイプと表示名のマッピング
    DISPLAY_NAMES: Dict[ArchiveType, str] = {
        ArchiveType.ZIP: "ZIP",
        ArchiveType.SEVEN_ZIP: "7-Zip",
        ArchiveType.RAR: "RAR",
        ArchiveType.TAR: "TAR",
        ArchiveType.TAR_GZ: "TAR.GZ",
        ArchiveType.TAR_BZ2: "TAR.BZ2",
        ArchiveType.TAR_XZ: "TAR.XZ",
        ArchiveType.GZ: "GZ",
        ArchiveType.BZ2: "BZ2",
        ArchiveType.XZ: "XZ",
        ArchiveType.CBZ: "CBZ",
        ArchiveType.CBR: "CBR",
        ArchiveType.PDF: "PDF"
    }
    # アーカイブタイプと設定キーのマッピング
    CONFIG_KEYS: Dict[ArchiveType, str] = {
        ArchiveType.ZIP: "zip",
        ArchiveType.SEVEN_ZIP: "7z",
        ArchiveType.RAR: "rar",
        ArchiveType.TAR: "tar",
        ArchiveType.TAR_GZ: "tar_gz",
        ArchiveType.TAR_BZ2: "tar_bz2",
        ArchiveType.TAR_XZ: "tar_xz",
        ArchiveType.GZ: "gz",
        ArchiveType.BZ2: "bz2",
        ArchiveType.XZ: "xz",
        ArchiveType.CBZ: "cbz",
        ArchiveType.CBR: "cbr",
        ArchiveType.PDF: "pdf"
    }
    # アーカイブタイプと内部処理名のマッピング
    INTERNAL_NAMES: Dict[ArchiveType, str] = {
        ArchiveType.ZIP: "zip",
        ArchiveType.SEVEN_ZIP: "7z",
        ArchiveType.RAR: "rar",
        ArchiveType.TAR: "tar",
        ArchiveType.TAR_GZ: "tar.gz",
        ArchiveType.TAR_BZ2: "tar.bz2",
        ArchiveType.TAR_XZ: "tar.xz",
        ArchiveType.GZ: "gz",
        ArchiveType.BZ2: "bz2",
        ArchiveType.XZ: "xz",
        ArchiveType.CBZ: "cbz",
        ArchiveType.CBR: "cbr",
        ArchiveType.PDF: "pdf"
    }
    @classmethod
    def get_all_extensions(cls) -> Set[str]:
        """すべてのアーカイブ拡張子を取得する。

        Returns:
            登録されている拡張子の集合。
        """
        extensions = set()
        for ext_list in cls.EXTENSIONS.values():
            extensions.update(ext_list)
        return extensions

    @classmethod
    def get_archive_type_by_extension(cls, extension: str) -> Optional[ArchiveType]:
        """拡張子からアーカイブタイプを取得する。

        Args:
            extension: 調べる拡張子。大文字小文字は区別しない。

        Returns:
            一致したアーカイブタイプ。無ければ None。
        """
        extension = extension.lower()
        for archive_type, ext_list in cls.EXTENSIONS.items():
            if extension in ext_list:
                return archive_type
        return None

    @classmethod
    def _get_compression_archive_type(cls, suffix: str) -> Optional[ArchiveType]:
        """圧縮拡張子からアーカイブタイプを取得する。

        Args:
            suffix: 圧縮の拡張子。

        Returns:
            gz、bz2、xz に対応するタイプ。無ければ None。
        """
        compression_mapping = {
            cls.EXTENSIONS[ArchiveType.GZ][0]: ArchiveType.GZ,
            cls.EXTENSIONS[ArchiveType.BZ2][0]: ArchiveType.BZ2,
            cls.EXTENSIONS[ArchiveType.XZ][0]: ArchiveType.XZ
        }
        return compression_mapping.get(suffix)

    @classmethod
    def _get_tar_compression_archive_type(cls, suffix: str) -> Optional[ArchiveType]:
        """TAR圧縮拡張子からアーカイブタイプを取得する。

        Args:
            suffix: 圧縮の拡張子。

        Returns:
            tar.gz、tar.bz2、tar.xz に対応するタイプ。無ければ None。
        """
        tar_compression_mapping = {
            cls.EXTENSIONS[ArchiveType.GZ][0]: ArchiveType.TAR_GZ,
            cls.EXTENSIONS[ArchiveType.BZ2][0]: ArchiveType.TAR_BZ2,
            cls.EXTENSIONS[ArchiveType.XZ][0]: ArchiveType.TAR_XZ
        }
        return tar_compression_mapping.get(suffix)

    @classmethod
    def get_archive_type_by_path(cls, file_path: str) -> Optional[ArchiveType]:
        """ファイルパスからアーカイブタイプを取得する。

        Args:
            file_path: 調べるファイルパス。

        Returns:
            圧縮拡張子かつ tar なら TAR 圧縮、そうでなければ単体の圧縮。それ以外は拡張子から引いたタイプ。無ければ None。
        """
        path = Path(file_path)
        suffix = path.suffix.lower()
        # 複合拡張子の処理
        compression_types = [ArchiveType.GZ, ArchiveType.BZ2, ArchiveType.XZ]
        compression_extensions = []
        for archive_type in compression_types:
            compression_extensions.extend(cls.EXTENSIONS[archive_type])
        if suffix in compression_extensions:
            # TARファイルの拡張子を取得
            tar_extensions = cls.EXTENSIONS[ArchiveType.TAR]
            is_tar_file = any(path.stem.endswith(tar_ext) for tar_ext in tar_extensions)
            if is_tar_file:
                return cls._get_tar_compression_archive_type(suffix)
            else:
                return cls._get_compression_archive_type(suffix)
        # 通常の拡張子の処理
        return cls.get_archive_type_by_extension(suffix)

    @classmethod
    def get_display_name(cls, archive_type: ArchiveType) -> str:
        """アーカイブタイプの表示名を取得する。

        Args:
            archive_type: 表示名を引くアーカイブタイプ。

        Returns:
            対応する表示名。無ければ値の文字列。
        """
        return cls.DISPLAY_NAMES.get(archive_type, str(archive_type.value))

    @classmethod
    def get_config_key(cls, archive_type: ArchiveType) -> str:
        """アーカイブタイプの設定キーを取得する。

        Args:
            archive_type: 設定キーを引くアーカイブタイプ。

        Returns:
            対応する設定キー。無ければ値。
        """
        return cls.CONFIG_KEYS.get(archive_type, archive_type.value)

    @classmethod
    def get_internal_name(cls, archive_type: ArchiveType) -> str:
        """アーカイブタイプの内部処理名を取得する。

        Args:
            archive_type: 内部処理名を引くアーカイブタイプ。

        Returns:
            対応する内部処理名。無ければ値。
        """
        return cls.INTERNAL_NAMES.get(archive_type, archive_type.value)

    @classmethod
    def get_all_archive_types(cls) -> List[ArchiveType]:
        """すべてのアーカイブタイプを取得する。

        Returns:
            定義されているアーカイブタイプの一覧。
        """
        return list(ArchiveType)

    @classmethod
    def get_archive_types_for_settings(cls) -> List[tuple]:
        """設定ダイアログ用のアーカイブタイプリストを取得する。

        Returns:
            設定キーと表示名の組の一覧。
        """
        return [(cls.get_config_key(archive_type), cls.get_display_name(archive_type))
                for archive_type in cls.get_all_archive_types()]

    @classmethod
    def is_archive_file(cls, file_path: str) -> bool:
        """ファイルがアーカイブファイルかどうかを判定する。

        Args:
            file_path: 調べるファイルパス。

        Returns:
            パスからアーカイブタイプが取れれば True。
        """
        return cls.get_archive_type_by_path(file_path) is not None

    @classmethod
    def get_file_filter_string(cls) -> str:
        """ファイル選択ダイアログ用のフィルター文字列を取得する。

        Returns:
            全アーカイブ拡張子と全ファイルを含むフィルター文字列。
        """
        extensions = []
        for archive_type in cls.get_all_archive_types():
            extensions.extend(cls.EXTENSIONS[archive_type])
        # 拡張子を*.ext形式に変換
        filter_extensions = [f"*{ext}" for ext in extensions]
        return f"{get_text("ui.archive_files")} ({' '.join(filter_extensions)});;All files (*)"

    @classmethod
    def get_comic_filter_string(cls) -> str:
        """コミックファイル選択ダイアログ用のフィルター文字列を取得する。

        Returns:
            CBZ、CBR、ZIP、RAR、PDF の拡張子を並べたフィルター文字列。
        """
        comic_types = [ArchiveType.CBZ, ArchiveType.CBR, ArchiveType.ZIP, ArchiveType.RAR, ArchiveType.PDF]
        comic_extensions = []
        for archive_type in comic_types:
            comic_extensions.extend(cls.EXTENSIONS[archive_type])
        filter_extensions = [f"*{ext}" for ext in comic_extensions]
        return f"Comic files ({' '.join(filter_extensions)});;All files (*)"
