import json
import os
import locale
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from importlib import resources
logger = logging.getLogger(__name__)
class LanguageManager:
    """言語管理クラス"""
    def __init__(self):
        self.current_language = "system"
        self.language_data = {}
        self.available_languages = {}
        self._load_available_languages()
        self._load_language()
    def _load_available_languages(self):
        """利用可能な言語を読み込み"""
        self.available_languages = {}
        # システムのデフォルト言語を追加
        try:
            system_lang = locale.getdefaultlocale()[0]
            if system_lang:
                lang_code = system_lang.split('_')[0]
                self.available_languages["system"] = {
                    "name": "システムのデフォルト言語",
                    "code": lang_code,
                    "file": None
                }
        except Exception as e:
            logger.warning(f"システム言語の取得に失敗: {e}")
            self.available_languages["system"] = {
                "name": "システムのデフォルト言語",
                "code": "ja",
                "file": None
            }
        # resources/langsフォルダから言語ファイルを読み込み
        try:
            with resources.path("ez_co.resources.langs", "") as langs_path:
                for file_path in Path(langs_path).glob("*.json"):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lang_data = json.load(f)
                                lang_code = lang_data.get("language_code", file_path.stem)
                                lang_name = lang_data.get("language", file_path.stem)
                                self.available_languages[lang_code] = {
                                    "name": lang_name,
                                    "code": lang_code,
                                    "file": file_path
                                }
                        except Exception as e:
                            logger.warning(f"言語ファイルの読み込みに失敗 {file_path}: {e}")
        except Exception as e:
            logger.warning(f"resources/langsフォルダの読み込みに失敗: {e}")
        # 起動ディレクトリのlangsフォルダから言語ファイルを読み込み（優先）
        try:
            startup_dir = Path.cwd()
            langs_dir = startup_dir / "langs"
            if langs_dir.exists() and langs_dir.is_dir():
                for file_path in langs_dir.glob("*.json"):
                    if file_path.is_file():
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                lang_data = json.load(f)
                                lang_code = lang_data.get("language_code", file_path.stem)
                                lang_name = lang_data.get("language", file_path.stem)
                                # 起動ディレクトリのファイルを優先
                                self.available_languages[lang_code] = {
                                    "name": lang_name,
                                    "code": lang_code,
                                    "file": file_path
                                }
                        except Exception as e:
                            logger.warning(f"起動ディレクトリの言語ファイルの読み込みに失敗 {file_path}: {e}")
        except Exception as e:
            logger.warning(f"起動ディレクトリのlangsフォルダの読み込みに失敗: {e}")
    def _load_language(self, language_code: Optional[str] = None):
        """言語データを読み込み"""
        if language_code is None:
            language_code = self.current_language
        if language_code == "system":
            # システムのデフォルト言語を使用
            try:
                system_lang = locale.getdefaultlocale()[0]
                if system_lang:
                    lang_code = system_lang.split('_')[0]
                else:
                    lang_code = "ja"  # デフォルトは日本語
            except Exception:
                lang_code = "ja"
        else:
            lang_code = language_code
        # 指定された言語が利用可能かチェック
        if lang_code not in self.available_languages:
            # 利用できない場合は日本語をフォールバック
            if "ja" in self.available_languages:
                lang_code = "ja"
            else:
                # 日本語もない場合は最初に見つかった言語を使用
                available_codes = [k for k in self.available_languages.keys() if k != "system"]
                if available_codes:
                    lang_code = available_codes[0]
                else:
                    # 何もない場合は空のデータを使用
                    self.language_data = {}
                    return
        lang_info = self.available_languages[lang_code]
        file_path = lang_info["file"]
        if file_path and file_path.exists():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.language_data = json.load(f)
                logger.info(f"言語ファイルを読み込みました: {lang_code}")
            except Exception as e:
                logger.error(f"言語ファイルの読み込みに失敗: {e}")
                self.language_data = {}
        else:
            # ファイルが存在しない場合は空のデータを使用
            self.language_data = {}
    def get_text(self, key: str, **kwargs) -> str:
        """テキストを取得"""
        if not self.language_data:
            # 言語データがない場合はキー名を返す
            return key
        
        # ドット区切りのキーを処理（例: "ui.file"）
        keys = key.split('.')
        value = self.language_data
        
        try:
            for k in keys:
                value = value[k]
        except (KeyError, TypeError):
            # キーが存在しない場合はキー名を返す
            return key
        
        # 文字列でない場合はキー名を返す
        if not isinstance(value, str):
            return key
        
        # エスケープされた改行コードを実際の改行文字に変換
        value = value.replace('\\n', '\n')
        
        # フォーマット文字列の処理
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        
        return value
    def get_available_languages(self) -> Dict[str, Dict[str, Any]]:
        """利用可能な言語の一覧を取得"""
        return self.available_languages.copy()
    def set_language(self, language_code: str) -> bool:
        """言語を設定"""
        if language_code not in self.available_languages:
            return False
        self.current_language = language_code
        self._load_language(language_code)
        logger.info(f"言語を変更しました: {language_code}")
        return True
    def get_current_language(self) -> str:
        """現在の言語コードを取得"""
        return self.current_language
    def get_current_language_name(self) -> str:
        """現在の言語名を取得"""
        if self.current_language in self.available_languages:
            return self.available_languages[self.current_language]["name"]
        return "Unknown"
# グローバルインスタンス
language_manager = LanguageManager()
def get_text(key: str, **kwargs) -> str:
    """テキストを取得する便利関数"""
    return language_manager.get_text(key, **kwargs)
def set_language(language_code: str) -> bool:
    """言語を設定する便利関数"""
    return language_manager.set_language(language_code)
def get_available_languages() -> Dict[str, Dict[str, Any]]:
    """利用可能な言語の一覧を取得する便利関数"""
    return language_manager.get_available_languages()
def get_log_text(key: str, **kwargs) -> str:
    """ログメッセージ用のテキストを取得する関数"""
    return language_manager.get_text(f"logging.{key}", **kwargs)
def get_message_text(key: str, **kwargs) -> str:
    """メッセージ用のテキストを取得する関数"""
    return language_manager.get_text(f"messages.{key}", **kwargs) 