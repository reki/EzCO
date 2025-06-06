from enum import Enum
from typing import Dict, List, Set
from ez_co.utils.language_manager import get_text

class ImageType(Enum):
    """画像タイプの列挙"""
    JPEG = "jpeg"
    PNG = "png"
    GIF = "gif"
    BMP = "bmp"
    WEBP = "webp"
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
        """すべての画像拡張子を取得"""
        extensions = set()
        for ext_list in cls.EXTENSIONS.values():
            extensions.update(ext_list)
        return extensions
    @classmethod
    def get_image_type_by_extension(cls, extension: str) -> ImageType:
        """拡張子から画像タイプを取得"""
        extension = extension.lower()
        for image_type, ext_list in cls.EXTENSIONS.items():
            if extension in ext_list:
                return image_type
        return None
    @classmethod
    def get_display_name(cls, image_type: ImageType) -> str:
        """画像タイプの表示名を取得"""
        return cls.DISPLAY_NAMES.get(image_type, str(image_type.value))
    @classmethod
    def get_mime_type(cls, image_type: ImageType) -> str:
        """画像タイプのMIMEタイプを取得"""
        return cls.MIME_TYPES.get(image_type, "application/octet-stream")
    @classmethod
    def get_all_image_types(cls) -> List[ImageType]:
        """すべての画像タイプを取得"""
        return list(ImageType)
    @classmethod
    def get_file_filter_string(cls) -> str:
        """ファイル選択ダイアログ用のフィルター文字列を取得"""
        
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
        """ファイルが画像ファイルかどうかを判定"""
        from pathlib import Path
        path = Path(file_path)
        return path.suffix.lower() in cls.get_all_extensions() 