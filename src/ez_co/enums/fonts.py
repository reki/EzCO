"""フォント形式とフォントファミリーの情報。"""
from enum import Enum
from typing import Dict, List, Set, Optional, Tuple
from PySide6.QtGui import QFontDatabase
from ez_co.utils.language_manager import get_text

class FontType(Enum):
    """フォントタイプの列挙"""
    # TrueType フォント
    TTF = "ttf"
    # OpenType フォント
    OTF = "otf"


class FontInfo:
    """フォント情報を保持するクラス"""
    # フォントタイプと拡張子のマッピング
    EXTENSIONS: Dict[FontType, List[str]] = {
        FontType.TTF: [".ttf"],
        FontType.OTF: [".otf"]
    }

    # フォントタイプと表示名のマッピング
    DISPLAY_NAMES: Dict[FontType, str] = {
        FontType.TTF: "TrueType Font",
        FontType.OTF: "OpenType Font"
    }

    # フォントタイプとMIMEタイプのマッピング
    MIME_TYPES: Dict[FontType, str] = {
        FontType.TTF: "font/ttf",
        FontType.OTF: "font/otf"
    }

    @classmethod
    def get_all_extensions(cls) -> Set[str]:
        """すべてのフォント拡張子を取得する。

        Returns:
            登録されている拡張子の集合。
        """
        extensions = set()
        for ext_list in cls.EXTENSIONS.values():
            extensions.update(ext_list)
        return extensions

    @classmethod
    def get_font_type_by_extension(cls, extension: str) -> FontType:
        """拡張子からフォントタイプを取得する。

        Args:
            extension: 調べる拡張子。大文字小文字は区別しない。

        Returns:
            一致したフォントタイプ。無ければ None。
        """
        extension = extension.lower()
        for font_type, ext_list in cls.EXTENSIONS.items():
            if extension in ext_list:
                return font_type
        return None

    @classmethod
    def get_display_name(cls, font_type: FontType) -> str:
        """フォントタイプの表示名を取得する。

        Args:
            font_type: 表示名を引くフォントタイプ。

        Returns:
            対応する表示名。無ければ値の文字列。
        """
        return cls.DISPLAY_NAMES.get(font_type, str(font_type.value))

    @classmethod
    def get_mime_type(cls, font_type: FontType) -> str:
        """フォントタイプのMIMEタイプを取得する。

        Args:
            font_type: MIMEタイプを引くフォントタイプ。

        Returns:
            対応するMIMEタイプ。無ければ application/octet-stream。
        """
        return cls.MIME_TYPES.get(font_type, "application/octet-stream")

    @classmethod
    def get_all_font_types(cls) -> List[FontType]:
        """すべてのフォントタイプを取得する。

        Returns:
            定義されているフォントタイプの一覧。
        """
        return list(FontType)

    @classmethod
    def get_file_filter_string(cls) -> str:
        """ファイル選択ダイアログ用のフィルター文字列を取得する。

        Returns:
            全フォント拡張子を並べたフィルター文字列。
        """
        extensions = []
        for font_type in cls.get_all_font_types():
            extensions.extend(cls.EXTENSIONS[font_type])
        # フィルター文字列を作成
        filter_parts = []
        for ext in extensions:
            filter_parts.append(f"*{ext}")
        return f"{get_text('ui.font_files')} ({' '.join(filter_parts)})"

    @classmethod
    def is_font_file(cls, file_path: str) -> bool:
        """ファイルがフォントファイルかどうかを判定する。

        Args:
            file_path: 調べるファイルパス。

        Returns:
            拡張子がフォントなら True。
        """
        from pathlib import Path
        path = Path(file_path)
        return path.suffix.lower() in cls.get_all_extensions()


class FontFamilyManager:
    """フォントファミリーの統一管理クラス"""

    # 日本語名と英語名のマッピング
    FONT_NAME_MAPPING = {
        # 日本語名: [英語名, 別名...]
        "メイリオ": ["Meiryo", "Meiryo UI"],
        "游ゴシック": ["Yu Gothic", "Yu Gothic UI", "Yu Gothic Light", "Yu Gothic Medium"],
        "游明朝": ["Yu Mincho", "Yu Mincho Light", "Yu Mincho Medium"],
        "ＭＳ ゴシック": ["MS Gothic", "ＭＳ ゴシック"],
        "ＭＳ Ｐゴシック": ["MS PGothic", "ＭＳ Ｐゴシック"],
        "ＭＳ 明朝": ["MS Mincho", "ＭＳ 明朝"],
        "ＭＳ Ｐ明朝": ["MS PMincho", "ＭＳ Ｐ明朝"],
        "HGゴシック": ["HGGothicE", "HGGothicM", "HGPGothicE", "HGPGothicM", "HGSGothicE", "HGSGothicM"],
        "HG明朝": ["HGMinchoE", "HGMinchoB", "HGPMinchoE", "HGPMinchoB", "HGSMinchoE", "HGSMinchoB"],
        "HG行書体": ["HGGyoshotai", "HGPGyoshotai", "HGSGyoshotai"],
        "HG教科書体": ["HGKyokashotai", "HGPKyokashotai", "HGSKyokashotai"],
        "BIZ UDゴシック": ["BIZ UDGothic", "BIZ UDPGothic"],
        "BIZ UD明朝": ["BIZ UDMincho", "BIZ UDPMincho"],
        "UD デジタル 教科書体": ["UD Digi Kyokasho N", "UD Digi Kyokasho NK", "UD Digi Kyokasho NP"],
    }

    # 言語別のフォント候補（優先順位順）
    FONT_CANDIDATES = {
        "ja": ["メイリオ", "游ゴシック", "HGゴシック", "ＭＳ ゴシック", "BIZ UDゴシック"],
        "en": ["Segoe UI", "Arial", "Calibri", "Tahoma", "Verdana"]
    }

    @classmethod
    def get_available_font_families(cls) -> List[str]:
        """利用可能なフォントファミリーの一覧を取得する。

        Returns:
            重複を除いて整理し、ソートしたフォント名。
        """
        all_fonts = set()

        # QFontDatabaseから取得
        font_db = QFontDatabase()
        qt_families = font_db.families()
        all_fonts.update(qt_families)

        # Windowsレジストリから取得（Windows環境のみ）
        try:
            import winreg
            import platform
            if platform.system() == "Windows":
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                    r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
                    i = 0
                    while True:
                        try:
                            name, _, _ = winreg.EnumValue(key, i)
                            # " (TrueType)" などを除去
                            font_name = name.split('(')[0].strip()
                            # "&" で区切られた複数フォント名を分割
                            if '&' in font_name:
                                for part in font_name.split('&'):
                                    all_fonts.add(part.strip())
                            else:
                                all_fonts.add(font_name)
                            i += 1
                        except OSError:
                            # レジストリの列挙が尽きたらループを抜ける
                            break
        except Exception:
            # レジストリを読めなければ、フォント一覧には足さず続ける
            pass

        # プロジェクトフォントフォルダから取得
        try:
            from ez_co.utils.data_location import get_data_root
            from ez_co.utils.path_utils import get_project_root
            font_dirs = [get_project_root() / "font", get_data_root() / "font"]
            seen = set()
            for font_dir in font_dirs:
                resolved = font_dir.resolve()
                if resolved in seen or not font_dir.exists() or not font_dir.is_dir():
                    continue
                seen.add(resolved)
                for f in font_dir.iterdir():
                    if f.suffix.lower() in FontInfo.get_all_extensions():
                        all_fonts.add(f.stem)
        except Exception:
            # フォントフォルダを読めなければ、その分は足さず続ける
            pass

        # 重複する名前を統合し、優先度の高い名前を選択
        unified_fonts = cls._unify_font_names(all_fonts)

        return sorted(unified_fonts)

    @classmethod
    def _unify_font_names(cls, font_names: Set[str]) -> Set[str]:
        """フォント名を統一し、重複を除去する。

        Args:
            font_names: 統一する前のフォント名。

        Returns:
            代表名にまとめたフォント名。
        """
        unified = set()
        used_variants = set()

        for font_name in font_names:
            # 既に処理済みの場合はスキップ
            if font_name in used_variants:
                continue

            # マッピングに基づいて代表名を見つける
            representative_name = cls._find_representative_name(font_name, font_names)
            if representative_name:
                unified.add(representative_name)
                # このファミリーの全バリアントをマーク
                variants = cls._get_font_variants(representative_name)
                used_variants.update(variants)
                used_variants.add(representative_name)
            else:
                # マッピングにない場合は、そのまま追加（ただし類似名をチェック）
                if not cls._is_similar_font_already_added(font_name, unified):
                    unified.add(font_name)
                    used_variants.add(font_name)

        return unified

    @classmethod
    def _find_representative_name(cls, font_name: str, available_fonts: Set[str]) -> Optional[str]:
        """フォント名の代表名を見つける。

        Args:
            font_name: 調べるフォント名。
            available_fonts: 利用できるフォント名。

        Returns:
            マッピングの日本語名ならその名前。英語名がバリアントなら、日本語名が利用できるとき日本語名、そうでなければその英語名。マッピング外は None。
        """
        # 日本語名がマッピングにある場合
        if font_name in cls.FONT_NAME_MAPPING:
            return font_name

        # 英語名が日本語名のバリアントに含まれる場合
        for jp_name, variants in cls.FONT_NAME_MAPPING.items():
            if font_name in variants:
                # 日本語名が利用可能なら日本語名を優先
                if jp_name in available_fonts:
                    return jp_name
                # 利用可能でなければ英語名を返す
                return font_name

        return None

    @classmethod
    def _get_font_variants(cls, representative_name: str) -> List[str]:
        """代表名に対応するすべてのバリアントを取得する。

        Args:
            representative_name: バリアントを引く代表名。

        Returns:
            マッピングされた別名と代表名自身。
        """
        variants = []
        if representative_name in cls.FONT_NAME_MAPPING:
            variants.extend(cls.FONT_NAME_MAPPING[representative_name])
        variants.append(representative_name)
        return variants

    @classmethod
    def _is_similar_font_already_added(cls, font_name: str, existing_fonts: Set[str]) -> bool:
        """類似のフォントが既に追加されているかチェックする。

        Args:
            font_name: 調べるフォント名。
            existing_fonts: すでに採用したフォント名。

        Returns:
            Bold、Light、Medium、Italic、UI、Regular を除いた基部が一致すれば True。
        """
        # 基本的な類似パターンをチェック
        base_name = font_name.replace(" Bold", "").replace(" Light", "").replace(" Medium", "")
        base_name = base_name.replace(" Italic", "").replace(" UI", "").replace(" Regular", "")

        for existing in existing_fonts:
            existing_base = existing.replace(" Bold", "").replace(" Light", "").replace(" Medium", "")
            existing_base = existing_base.replace(" Italic", "").replace(" UI", "").replace(" Regular", "")
            if base_name == existing_base:
                return True

        return False

    @classmethod
    def get_font_family_variants(cls, family_name: str) -> List[str]:
        """指定されたフォントファミリーの全バリアントを取得する。

        Args:
            family_name: バリアントを探すファミリー名。

        Returns:
            マッピングとスタイルから、利用できるもの。無ければファミリー名だけ。
        """
        available_fonts = set(QFontDatabase().families())
        variants = []

        # マッピングからバリアントを検索
        base_variants = cls._get_font_variants(family_name)

        # 利用可能なバリアントのみを返す
        for variant in base_variants:
            if variant in available_fonts:
                variants.append(variant)

        # QFontDatabaseから直接バリアントを検索
        font_db = QFontDatabase()
        styles = font_db.styles(family_name)
        for style in styles:
            if style and style != "Regular":
                variant_name = f"{family_name} {style}"
                if variant_name in available_fonts and variant_name not in variants:
                    variants.append(variant_name)

        return sorted(variants) if variants else [family_name]

    @classmethod
    def get_default_font_for_language(cls, language_code: str) -> str:
        """指定された言語の推奨フォントを取得する。

        Args:
            language_code: 言語コード。ja で始まるときだけ日本語の候補を使う。

        Returns:
            候補のうち最初に利用できる代表名。候補が無ければ利用可能な先頭。フォントが無ければ Arial。
        """
        # 言語コードの正規化
        lang_key = "ja" if language_code and language_code.startswith("ja") else "en"

        # 利用可能なフォント一覧を取得
        available_fonts = set(cls.get_available_font_families())

        # 候補リストから最初に見つかったものを返す
        candidates = cls.FONT_CANDIDATES.get(lang_key, cls.FONT_CANDIDATES["en"])
        for candidate in candidates:
            if candidate in available_fonts:
                return candidate
            # バリアントもチェック
            variants = cls._get_font_variants(candidate)
            for variant in variants:
                if variant in available_fonts:
                    return candidate  # 代表名を返す

        # フォールバック
        if available_fonts:
            return sorted(available_fonts)[0]

        return "Arial"  # 最終的なフォールバック

    @classmethod
    def normalize_font_name(cls, font_name: str) -> str:
        """設定と表示で揃えるため、フォント名を正規化する。

        Args:
            font_name: 正規化するフォント名。

        Returns:
            マッピングされた英語名は日本語名。日本語名とその他はそのまま。
        """
        # マッピングにある英語名を日本語名に変換
        for jp_name, variants in cls.FONT_NAME_MAPPING.items():
            if font_name in variants:
                return jp_name

        # 日本語名はそのまま返す
        if font_name in cls.FONT_NAME_MAPPING:
            return font_name

        # その他はそのまま返す
        return font_name
