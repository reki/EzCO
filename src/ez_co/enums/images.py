"""画像形式と拡張子・表示名の対応。"""
from enum import Enum
from typing import Dict, List, Set
from ez_co.utils.language_manager import get_text

class ImageType(Enum):
    """画像タイプの列挙"""
    # JPEG 形式
    JPEG = "jpeg"
    # PNG 形式
    PNG = "png"
    # GIF 形式
    GIF = "gif"
    # BMP 形式
    BMP = "bmp"
    # WebP 形式
    WEBP = "webp"
    # TIFF 形式
    TIFF = "tiff"


class ImageInfo:
    """画像情報を保持するクラス"""
    # 画像タイプと拡張子のマッピング
    EXTENSIONS: Dict[ImageType, List[str]] = {
        ImageType.JPEG: [".jpg", ".jpeg"],
        ImageType.PNG: [".png"],
        ImageType.GIF: [".gif"],
        ImageType.BMP: [".bmp"],
        ImageType.WEBP: [".webp"],
        ImageType.TIFF: [".tiff", ".tif"]
    }
    # 画像タイプと表示名のマッピング
    DISPLAY_NAMES: Dict[ImageType, str] = {
        ImageType.JPEG: "JPEG",
        ImageType.PNG: "PNG",
        ImageType.GIF: "GIF",
        ImageType.BMP: "BMP",
        ImageType.WEBP: "WebP",
        ImageType.TIFF: "TIFF"
    }
    # 画像タイプとMIMEタイプのマッピング
    MIME_TYPES: Dict[ImageType, str] = {
        ImageType.JPEG: "image/jpeg",
        ImageType.PNG: "image/png",
        ImageType.GIF: "image/gif",
        ImageType.BMP: "image/bmp",
        ImageType.WEBP: "image/webp",
        ImageType.TIFF: "image/tiff"
    }
    @classmethod
    def get_all_extensions(cls) -> Set[str]:
        """すべての画像拡張子を取得する。

        Returns:
            登録されている拡張子の集合。
        """
        extensions = set()
        for ext_list in cls.EXTENSIONS.values():
            extensions.update(ext_list)
        return extensions

    @classmethod
    def get_image_type_by_extension(cls, extension: str) -> ImageType:
        """拡張子から画像タイプを取得する。

        Args:
            extension: 調べる拡張子。大文字小文字は区別しない。

        Returns:
            一致した画像タイプ。無ければ None。
        """
        extension = extension.lower()
        for image_type, ext_list in cls.EXTENSIONS.items():
            if extension in ext_list:
                return image_type
        return None

    @classmethod
    def get_display_name(cls, image_type: ImageType) -> str:
        """画像タイプの表示名を取得する。

        Args:
            image_type: 表示名を引く画像タイプ。

        Returns:
            対応する表示名。無ければ値の文字列。
        """
        return cls.DISPLAY_NAMES.get(image_type, str(image_type.value))

    @classmethod
    def get_mime_type(cls, image_type: ImageType) -> str:
        """画像タイプのMIMEタイプを取得する。

        Args:
            image_type: MIMEタイプを引く画像タイプ。

        Returns:
            対応するMIMEタイプ。無ければ application/octet-stream。
        """
        return cls.MIME_TYPES.get(image_type, "application/octet-stream")

    @classmethod
    def get_all_image_types(cls) -> List[ImageType]:
        """すべての画像タイプを取得する。

        Returns:
            定義されている画像タイプの一覧。
        """
        return list(ImageType)

    @classmethod
    def get_file_filter_string(cls) -> str:
        """ファイル選択ダイアログ用のフィルター文字列を取得する。

        Returns:
            全画像拡張子を並べたフィルター文字列。
        """

        extensions = []
        for image_type in cls.get_all_image_types():
            extensions.extend(cls.EXTENSIONS[image_type])
        # フィルター文字列を作成
        filter_parts = []
        for ext in extensions:
            filter_parts.append(f"*{ext}")

        # 多言語化対応
        image_files_text = get_text("ui.image_files")
        return f"{image_files_text} ({' '.join(filter_parts)})"

    @classmethod
    def is_image_file(cls, file_path: str) -> bool:
        """ファイルが画像ファイルかどうかを判定する。

        Args:
            file_path: 調べるファイルパス。

        Returns:
            拡張子が画像なら True。
        """
        from pathlib import Path
        path = Path(file_path)
        return path.suffix.lower() in cls.get_all_extensions()
