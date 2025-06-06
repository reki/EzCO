from enum import Enum
from typing import Dict, List, Set, Optional
from pathlib import Path
from ez_co.utils.language_manager import get_text
class ArchiveType(Enum):
    """アーカイブタイプの列挙"""
    ZIP = "zip"
    SEVEN_ZIP = "7z"
    RAR = "rar"
    TAR = "tar"
    TAR_GZ = "tar_gz"
    TAR_BZ2 = "tar_bz2"
    TAR_XZ = "tar_xz"
    GZ = "gz"
    BZ2 = "bz2"
    XZ = "xz"
    CBZ = "cbz"
    CBR = "cbr"
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
        """すべてのアーカイブ拡張子を取得"""
        extensions = set()
        for ext_list in cls.EXTENSIONS.values():
            extensions.update(ext_list)
        return extensions
    @classmethod
    def get_archive_type_by_extension(cls, extension: str) -> Optional[ArchiveType]:
        """拡張子からアーカイブタイプを取得"""
        extension = extension.lower()
        for archive_type, ext_list in cls.EXTENSIONS.items():
            if extension in ext_list:
                return archive_type
        return None
    @classmethod
    def _get_compression_archive_type(cls, suffix: str) -> Optional[ArchiveType]:
        """圧縮拡張子からアーカイブタイプを取得"""
        compression_mapping = {
            cls.EXTENSIONS[ArchiveType.GZ][0]: ArchiveType.GZ,
            cls.EXTENSIONS[ArchiveType.BZ2][0]: ArchiveType.BZ2,
            cls.EXTENSIONS[ArchiveType.XZ][0]: ArchiveType.XZ
        }
        return compression_mapping.get(suffix)
    @classmethod
    def _get_tar_compression_archive_type(cls, suffix: str) -> Optional[ArchiveType]:
        """TAR圧縮拡張子からアーカイブタイプを取得"""
        tar_compression_mapping = {
            cls.EXTENSIONS[ArchiveType.GZ][0]: ArchiveType.TAR_GZ,
            cls.EXTENSIONS[ArchiveType.BZ2][0]: ArchiveType.TAR_BZ2,
            cls.EXTENSIONS[ArchiveType.XZ][0]: ArchiveType.TAR_XZ
        }
        return tar_compression_mapping.get(suffix)
    @classmethod
    def get_archive_type_by_path(cls, file_path: str) -> Optional[ArchiveType]:
        """ファイルパスからアーカイブタイプを取得"""
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
        """アーカイブタイプの表示名を取得"""
        return cls.DISPLAY_NAMES.get(archive_type, str(archive_type.value))
    @classmethod
    def get_config_key(cls, archive_type: ArchiveType) -> str:
        """アーカイブタイプの設定キーを取得"""
        return cls.CONFIG_KEYS.get(archive_type, archive_type.value)
    @classmethod
    def get_internal_name(cls, archive_type: ArchiveType) -> str:
        """アーカイブタイプの内部処理名を取得"""
        return cls.INTERNAL_NAMES.get(archive_type, archive_type.value)
    @classmethod
    def get_all_archive_types(cls) -> List[ArchiveType]:
        """すべてのアーカイブタイプを取得"""
        return list(ArchiveType)
    @classmethod
    def get_archive_types_for_settings(cls) -> List[tuple]:
        """設定ダイアログ用のアーカイブタイプリストを取得"""
        return [(cls.get_config_key(archive_type), cls.get_display_name(archive_type)) 
                for archive_type in cls.get_all_archive_types()]
    @classmethod
    def is_archive_file(cls, file_path: str) -> bool:
        """ファイルがアーカイブファイルかどうかを判定"""
        return cls.get_archive_type_by_path(file_path) is not None
    @classmethod
    def get_file_filter_string(cls) -> str:
        """ファイル選択ダイアログ用のフィルター文字列を取得"""
        extensions = []
        for archive_type in cls.get_all_archive_types():
            extensions.extend(cls.EXTENSIONS[archive_type])
        # 拡張子を*.ext形式に変換
        filter_extensions = [f"*{ext}" for ext in extensions]
        return f"{get_text("ui.archive_files")} ({' '.join(filter_extensions)});;All files (*)"
    @classmethod
    def get_comic_filter_string(cls) -> str:
        """コミックファイル選択ダイアログ用のフィルター文字列を取得"""
        comic_types = [ArchiveType.CBZ, ArchiveType.CBR, ArchiveType.ZIP, ArchiveType.RAR, ArchiveType.PDF]
        comic_extensions = []
        for archive_type in comic_types:
            comic_extensions.extend(cls.EXTENSIONS[archive_type])
        filter_extensions = [f"*{ext}" for ext in comic_extensions]
        return f"Comic files ({' '.join(filter_extensions)});;All files (*)" 