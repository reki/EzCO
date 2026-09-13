import json
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import os
from ez_co.utils.data_location import get_data_root
from ez_co.enums.entry_types import EntryType
from ez_co.enums.archives import ArchiveInfo
from ez_co.utils.language_manager import get_log_text, get_text

CONFIG_DB_NAME = "config.db"
LEGACY_DB_NAME = "bookmarks.db"
APP_STATE_CURRENT_PROFILE = "current_profile"

logger = logging.getLogger(__name__)

def get_default_profile_name() -> str:
    """デフォルトプロファイル名を取得（多言語化対応）"""
    return get_text("ui.default")

def resolve_database_path() -> Path:
    """config.db のパスを返す。旧 bookmarks.db があればリネームする。"""
    root = get_data_root()
    config_db = root / CONFIG_DB_NAME
    legacy_db = root / LEGACY_DB_NAME
    if legacy_db.exists() and not config_db.exists():
        try:
            legacy_db.rename(config_db)
            logger.info(get_log_text("database_renamed_from_bookmarks", src=str(legacy_db), dest=str(config_db)))
        except Exception as e:
            logger.error(get_log_text("database_rename_failed", error=e))
            return legacy_db
    elif legacy_db.exists() and config_db.exists():
        logger.info(get_log_text("database_keep_config_db", config_db=str(config_db), legacy_db=str(legacy_db)))
    return config_db

class DatabaseManager:
    """ブックマーク・履歴・プロファイル設定を管理するSQLite3データベースクラス"""
    def __init__(self, config=None):
        self.db_path = resolve_database_path()
        self.config = config
        self.current_profile = get_default_profile_name()
        self._init_database()
        persisted = self.get_persisted_current_profile()
        if persisted:
            self.current_profile = persisted

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
    def _init_database(self):
        """データベースとテーブルを初期化"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                
                # プロファイルテーブル（プロファイル名がPK）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS profiles (
                        name TEXT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_default INTEGER DEFAULT 0
                    )
                ''')
                
                # ブックマークテーブル（フォルダ機能付き）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bookmarks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        page_number INTEGER NOT NULL,
                        title TEXT,
                        folder_id INTEGER DEFAULT 0,
                        sort_order INTEGER DEFAULT 0,
                        entry_type TEXT DEFAULT 'file',
                        profile_name TEXT DEFAULT 'デフォルト',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(file_path, page_number, profile_name),
                        FOREIGN KEY (profile_name) REFERENCES profiles (name) ON DELETE CASCADE
                    )
                ''')
                # ブックマークフォルダテーブル
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bookmark_folders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        parent_id INTEGER DEFAULT 0,
                        sort_order INTEGER DEFAULT 0,
                        profile_name TEXT DEFAULT 'デフォルト',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (profile_name) REFERENCES profiles (name) ON DELETE CASCADE
                    )
                ''')
                # 履歴テーブル（entry_typeフィールドを追加）
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        page_number INTEGER NOT NULL,
                        title TEXT,
                        entry_type TEXT DEFAULT 'file',
                        profile_name TEXT DEFAULT 'デフォルト',
                        accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        encrypted_password TEXT,
                        FOREIGN KEY (profile_name) REFERENCES profiles (name) ON DELETE CASCADE
                    )
                ''')
                # 履歴テーブルにインデックスを追加（パフォーマンス向上）
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_history_accessed_at 
                    ON history(accessed_at DESC)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_history_profile 
                    ON history(profile_name)
                ''')
                # ブックマークフォルダにインデックスを追加
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_bookmarks_folder_id 
                    ON bookmarks(folder_id)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_bookmarks_profile 
                    ON bookmarks(profile_name)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_bookmark_folders_profile 
                    ON bookmark_folders(profile_name)
                ''')
                
                # 既存のテーブルにプロファイル外部キーを追加（マイグレーション）
                self._migrate_existing_tables(cursor)
                
                # プロファイルテーブルが空の場合、デフォルトプロファイルを作成
                cursor.execute("SELECT COUNT(*) FROM profiles")
                profile_count = cursor.fetchone()[0]
                if profile_count == 0:
                    default_name = get_default_profile_name()
                    cursor.execute('''
                        INSERT INTO profiles (name, created_at, is_default)
                        VALUES (?, CURRENT_TIMESTAMP, 1)
                    ''', (default_name,))
                    logger.info(get_log_text("default_profile_created"))
                
                self._ensure_default_profile_flag(cursor)
                self._ensure_app_state_current_profile(cursor)
                conn.commit()
            self._seed_missing_profile_settings()
        except Exception as e:
            logger.error(get_log_text("database_init_failed", error=e))
            raise
    def _migrate_existing_tables(self, cursor):
        """既存のテーブルにプロファイル外部キーを追加するマイグレーション"""
        try:
            # 履歴テーブルの更新
            cursor.execute("PRAGMA table_info(history)")
            history_columns = [column[1] for column in cursor.fetchall()]
            
            # 既存のentry_typeフィールドが存在しない場合は追加
            if 'entry_type' not in history_columns:
                cursor.execute('''
                    ALTER TABLE history ADD COLUMN entry_type TEXT DEFAULT 'file'
                ''')
                logger.info(get_log_text("database_entry_type_column_added"))
            
            # 既存のaccessed_atフィールドが存在しない場合は追加
            if 'accessed_at' not in history_columns:
                cursor.execute('''
                    ALTER TABLE history ADD COLUMN accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ''')
                logger.info(get_log_text("database_accessed_at_column_added"))
            
            # 既存のprofile_nameフィールドが存在しない場合は追加
            if 'profile_name' not in history_columns:
                default_name = get_default_profile_name()
                cursor.execute(f'''
                    ALTER TABLE history ADD COLUMN profile_name TEXT DEFAULT '{default_name}'
                ''')
                logger.info(get_log_text("database_profile_column_added"))

            if 'encrypted_password' not in history_columns:
                cursor.execute('''
                    ALTER TABLE history ADD COLUMN encrypted_password TEXT
                ''')
                logger.info(get_log_text("database_encrypted_password_column_added"))
            
            # ブックマークテーブルの更新
            cursor.execute("PRAGMA table_info(bookmarks)")
            bookmark_columns = [column[1] for column in cursor.fetchall()]
            
            if 'entry_type' not in bookmark_columns:
                cursor.execute('''
                    ALTER TABLE bookmarks ADD COLUMN entry_type TEXT DEFAULT 'file'
                ''')
                logger.info(get_log_text("database_bookmark_entry_type_column_added"))
            
            if 'profile_name' not in bookmark_columns:
                default_name = get_default_profile_name()
                cursor.execute(f'''
                    ALTER TABLE bookmarks ADD COLUMN profile_name TEXT DEFAULT '{default_name}'
                ''')
                logger.info(get_log_text("database_profile_column_added"))
            
            # ブックマークフォルダテーブルの更新
            cursor.execute("PRAGMA table_info(bookmark_folders)")
            folder_columns = [column[1] for column in cursor.fetchall()]
            
            if 'profile_name' not in folder_columns:
                default_name = get_default_profile_name()
                cursor.execute(f'''
                    ALTER TABLE bookmark_folders ADD COLUMN profile_name TEXT DEFAULT '{default_name}'
                ''')
                logger.info(get_log_text("database_profile_column_added"))

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS app_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS profile_settings (
                    profile_name TEXT NOT NULL,
                    section TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (profile_name, section, key),
                    FOREIGN KEY (profile_name) REFERENCES profiles (name) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_profile_settings_profile
                ON profile_settings(profile_name)
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS plugin_settings (
                    profile_name TEXT NOT NULL,
                    plugin_key TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (profile_name, plugin_key, key),
                    FOREIGN KEY (profile_name) REFERENCES profiles (name) ON DELETE CASCADE
                )
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_plugin_settings_plugin
                ON plugin_settings(profile_name, plugin_key)
            ''')

            cursor.execute("PRAGMA table_info(profiles)")
            profile_columns = [column[1] for column in cursor.fetchall()]
            if 'is_default' not in profile_columns:
                cursor.execute('ALTER TABLE profiles ADD COLUMN is_default INTEGER DEFAULT 0')
                logger.info(get_log_text("database_is_default_column_added"))
                
        except Exception as e:
            logger.error(get_log_text("database_migration_failed", error=e))
    
    def set_current_profile(self, profile_name: str):
        """現在のプロファイルをメモリ上に設定"""
        self.current_profile = profile_name

    def set_current_profile_persistent(self, profile_name: str):
        """現在のプロファイルをDBに保存する"""
        self.current_profile = profile_name
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)
                ''', (APP_STATE_CURRENT_PROFILE, profile_name))
                conn.commit()
        except Exception as e:
            logger.error(get_log_text("profile_persist_failed", profile_name=profile_name, error=e))

    def get_persisted_current_profile(self) -> Optional[str]:
        """保存されている現在のプロファイル名を取得"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT value FROM app_state WHERE key = ?', (APP_STATE_CURRENT_PROFILE,))
                row = cursor.fetchone()
                if row and row[0] and self._profile_exists_conn(cursor, row[0]):
                    return row[0]
                return self.get_default_protected_profile()
        except Exception as e:
            logger.error(get_log_text("profile_get_failed", error=e))
            return get_default_profile_name()

    def get_default_protected_profile(self) -> str:
        """削除できない既定プロファイル名を取得"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT name FROM profiles WHERE is_default = 1 LIMIT 1')
                row = cursor.fetchone()
                if row:
                    return row[0]
        except Exception:
            pass
        return get_default_profile_name()

    def is_protected_profile(self, profile_name: str) -> bool:
        return profile_name == self.get_default_protected_profile()

    def _profile_exists_conn(self, cursor, profile_name: str) -> bool:
        cursor.execute('SELECT COUNT(*) FROM profiles WHERE name = ?', (profile_name,))
        return cursor.fetchone()[0] > 0

    def _ensure_default_profile_flag(self, cursor):
        cursor.execute("SELECT COUNT(*) FROM profiles WHERE is_default = 1")
        if cursor.fetchone()[0] > 0:
            return
        default_name = get_default_profile_name()
        cursor.execute("SELECT name FROM profiles WHERE name = ?", (default_name,))
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE profiles SET is_default = 1 WHERE name = ?", (default_name,))
            return
        cursor.execute("SELECT name FROM profiles ORDER BY created_at ASC LIMIT 1")
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE profiles SET is_default = 1 WHERE name = ?", (row[0],))

    def _ensure_app_state_current_profile(self, cursor):
        cursor.execute('SELECT value FROM app_state WHERE key = ?', (APP_STATE_CURRENT_PROFILE,))
        row = cursor.fetchone()
        if row and row[0] and self._profile_exists_conn(cursor, row[0]):
            return
        default_name = get_default_profile_name()
        cursor.execute("SELECT name FROM profiles WHERE is_default = 1 LIMIT 1")
        flagged = cursor.fetchone()
        current = flagged[0] if flagged else default_name
        cursor.execute('''
            INSERT OR REPLACE INTO app_state (key, value) VALUES (?, ?)
        ''', (APP_STATE_CURRENT_PROFILE, current))

    def _seed_missing_profile_settings(self):
        """設定行が無いプロファイルへデフォルト設定を入れる（既存データは上書きしない）"""
        try:
            from ez_co.config import Config
            default_dict = Config().to_dict()
            for profile_name in self.get_profiles():
                if not self.has_profile_settings(profile_name):
                    self.save_profile_config(profile_name, default_dict)
        except Exception as e:
            logger.error(get_log_text("database_profile_settings_seed_failed", error=e))

    def has_profile_settings(self, profile_name: str) -> bool:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(*) FROM profile_settings WHERE profile_name = ?',
                    (profile_name,)
                )
                return cursor.fetchone()[0] > 0
        except Exception as e:
            logger.error(get_log_text("database_profile_settings_check_failed", error=e))
            return False

    def save_profile_config(self, profile_name: str, config_dict: Dict[str, Any]) -> bool:
        """プロファイル単位の設定を保存する"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM profile_settings WHERE profile_name = ?', (profile_name,))
                for section, values in (config_dict or {}).items():
                    if section == "profile" or not isinstance(values, dict):
                        continue
                    if not values:
                        cursor.execute(
                            '''
                            INSERT INTO profile_settings (profile_name, section, key, value)
                            VALUES (?, ?, ?, ?)
                            ''',
                            (profile_name, section, "", json.dumps({}, ensure_ascii=False))
                        )
                        continue
                    for key, value in values.items():
                        cursor.execute(
                            '''
                            INSERT INTO profile_settings (profile_name, section, key, value)
                            VALUES (?, ?, ?, ?)
                            ''',
                            (profile_name, section, key, json.dumps(value, ensure_ascii=False))
                        )
                conn.commit()
            return True
        except Exception as e:
            logger.error(get_log_text("database_profile_settings_save_failed", profile_name=profile_name, error=e))
            return False

    def _plugin_key(self, plugin_id: str) -> str:
        from ez_co.plugins.settings_key import hash_plugin_id
        return hash_plugin_id(plugin_id)

    def get_plugin_setting(self, plugin_id: str, key: str, default: Any = None) -> Any:
        profile_name = self.current_profile
        plugin_key = self._plugin_key(plugin_id)
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT value FROM plugin_settings
                    WHERE profile_name = ? AND plugin_key = ? AND key = ?
                    ''',
                    (profile_name, plugin_key, str(key or "")),
                )
                row = cursor.fetchone()
            if row is None:
                return default
            try:
                return json.loads(row[0]) if row[0] is not None else default
            except (TypeError, json.JSONDecodeError):
                return row[0]
        except Exception as e:
            logger.error(get_log_text("database_plugin_setting_get_failed", error=e))
            return default

    def set_plugin_setting(self, plugin_id: str, key: str, value: Any) -> bool:
        profile_name = self.current_profile
        plugin_key = self._plugin_key(plugin_id)
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    INSERT INTO plugin_settings (profile_name, plugin_key, key, value)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(profile_name, plugin_key, key) DO UPDATE SET value = excluded.value
                    ''',
                    (profile_name, plugin_key, str(key or ""), json.dumps(value, ensure_ascii=False)),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(get_log_text("database_plugin_setting_save_failed", error=e))
            return False

    def delete_plugin_setting(self, plugin_id: str, key: str) -> bool:
        profile_name = self.current_profile
        plugin_key = self._plugin_key(plugin_id)
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    DELETE FROM plugin_settings
                    WHERE profile_name = ? AND plugin_key = ? AND key = ?
                    ''',
                    (profile_name, plugin_key, str(key or "")),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(get_log_text("database_plugin_setting_delete_failed", error=e))
            return False

    def copy_plugin_settings(self, source_profile: str, dest_profile: str) -> bool:
        if not source_profile or not dest_profile or source_profile == dest_profile:
            return False
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM plugin_settings WHERE profile_name = ?', (dest_profile,))
                cursor.execute(
                    '''
                    INSERT INTO plugin_settings (profile_name, plugin_key, key, value)
                    SELECT ?, plugin_key, key, value FROM plugin_settings WHERE profile_name = ?
                    ''',
                    (dest_profile, source_profile),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error(get_log_text("database_plugin_settings_copy_failed", error=e))
            return False

    def load_profile_config(self, profile_name: str) -> Dict[str, Any]:
        """プロファイル単位の設定を読み込む"""
        result: Dict[str, Any] = {}
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT section, key, value FROM profile_settings WHERE profile_name = ?',
                    (profile_name,)
                )
                for section, key, value in cursor.fetchall():
                    try:
                        parsed = json.loads(value) if value is not None else None
                    except json.JSONDecodeError:
                        parsed = value
                    section_data = result.setdefault(section, {})
                    if key == "":
                        continue
                    section_data[key] = parsed
        except Exception as e:
            logger.error(get_log_text("database_profile_settings_load_failed", profile_name=profile_name, error=e))
        return result

    def create_profile(self, profile_name: str, settings: Optional[Dict[str, Any]] = None) -> bool:
        """新しいプロファイルを作成"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO profiles (name, created_at, is_default)
                    VALUES (?, CURRENT_TIMESTAMP, 0)
                ''', (profile_name,))
                conn.commit()
            from ez_co.config import Config
            config_dict = settings if settings is not None else Config().to_dict()
            self.save_profile_config(profile_name, config_dict)
            source = self.current_profile
            if source and source != profile_name:
                self.copy_plugin_settings(source, profile_name)
            logger.info(get_log_text("profile_created", profile_name=profile_name))
            return True
        except sqlite3.IntegrityError:
            logger.warning(get_log_text("profile_already_exists", profile_name=profile_name))
            return False
        except Exception as e:
            logger.error(get_log_text("profile_create_failed", profile_name=profile_name, error=e))
            return False
    def get_profiles(self) -> List[str]:
        """すべてのプロファイル名を取得"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT name FROM profiles
                    ORDER BY created_at ASC
                ''')
                rows = cursor.fetchall()
                return [row[0] for row in rows]
        except Exception as e:
            logger.error(get_log_text("profile_get_failed", error=e))
            return [get_default_profile_name()]  # エラー時は多言語化されたデフォルトのみ返す
    def delete_profile(self, profile_name: str) -> bool:
        """プロファイルを削除（既定プロファイルは削除不可）"""
        if self.is_protected_profile(profile_name):
            logger.warning(get_log_text("default_profile_cannot_delete"))
            return False
        
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM profile_settings WHERE profile_name = ?', (profile_name,))
                cursor.execute('DELETE FROM plugin_settings WHERE profile_name = ?', (profile_name,))
                cursor.execute('DELETE FROM bookmarks WHERE profile_name = ?', (profile_name,))
                cursor.execute('DELETE FROM bookmark_folders WHERE profile_name = ?', (profile_name,))
                cursor.execute('DELETE FROM history WHERE profile_name = ?', (profile_name,))
                cursor.execute('DELETE FROM profiles WHERE name = ?', (profile_name,))
                conn.commit()
                logger.info(get_log_text("profile_deleted", profile_name=profile_name))
                return True
        except Exception as e:
            logger.error(get_log_text("profile_delete_failed", profile_name=profile_name, error=e))
            return False

    def rename_profile(self, old_name: str, new_name: str) -> bool:
        """プロファイル名を変更する"""
        new_name = (new_name or "").strip()
        if not old_name or not new_name or old_name == new_name:
            return False
        if self.profile_exists(new_name):
            return False
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE profiles SET name = ? WHERE name = ?', (new_name, old_name))
                if cursor.rowcount == 0:
                    return False
                for table in ("profile_settings", "plugin_settings", "bookmarks", "bookmark_folders", "history"):
                    cursor.execute(
                        f'UPDATE {table} SET profile_name = ? WHERE profile_name = ?',
                        (new_name, old_name)
                    )
                cursor.execute(
                    'UPDATE app_state SET value = ? WHERE key = ? AND value = ?',
                    (new_name, APP_STATE_CURRENT_PROFILE, old_name)
                )
                conn.commit()
            if self.current_profile == old_name:
                self.current_profile = new_name
            logger.info(get_log_text("profile_renamed", old_name=old_name, new_name=new_name))
            return True
        except Exception as e:
            logger.error(get_log_text("profile_rename_failed", old_name=old_name, new_name=new_name, error=e))
            return False
    def profile_exists(self, profile_name: str) -> bool:
        """プロファイルが存在するかチェック"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT COUNT(*) FROM profiles WHERE name = ?', (profile_name,))
                count = cursor.fetchone()[0]
                return count > 0
        except Exception as e:
            logger.error(get_log_text("profile_check_failed", profile_name=profile_name, error=e))
            return False
    def add_bookmark(self, file_path: str, page_number: int, title: str = None, folder_id: int = 0, entry_type: str = EntryType.FILE.value) -> bool:
        """ブックマークを追加"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                # 最大のsort_orderを取得（現在のプロファイル内で）
                cursor.execute('''
                    SELECT MAX(sort_order) FROM bookmarks WHERE folder_id = ? AND profile_name = ?
                ''', (folder_id, self.current_profile))
                max_order = cursor.fetchone()[0] or 0
                new_order = max_order + 1
                cursor.execute('''
                    INSERT OR REPLACE INTO bookmarks (file_path, page_number, title, folder_id, sort_order, entry_type, profile_name, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (file_path, page_number, title, folder_id, new_order, entry_type, self.current_profile))
                conn.commit()
                # logger.info(get_log_text("database_bookmark_added", file_path=file_path, page_number=page_number, folder_id=folder_id))
                return True
        except Exception as e:
            logger.error(get_log_text("database_bookmark_add_failed", error=e))
            return False
    def remove_bookmark(self, file_path: str, page_number: int) -> bool:
        """ブックマークを削除"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM bookmarks 
                    WHERE file_path = ? AND page_number = ? AND profile_name = ?
                ''', (file_path, page_number, self.current_profile))
                conn.commit()
                # logger.info(get_log_text("database_bookmark_removed", file_path=file_path, page_number=page_number))
                return True
        except Exception as e:
            logger.error(get_log_text("database_bookmark_remove_failed", error=e))
            return False
    def get_bookmarks(self, folder_id: int = 0) -> List[Dict[str, Any]]:
        """指定されたフォルダのブックマークを取得"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_path, page_number, title, folder_id, sort_order, entry_type, created_at
                    FROM bookmarks
                    WHERE folder_id = ? AND profile_name = ?
                    ORDER BY sort_order ASC
                ''', (folder_id, self.current_profile))
                rows = cursor.fetchall()
                bookmark_list = [
                    {
                        'file_path': row[0],
                        'page_number': row[1],
                        'title': row[2],
                        'folder_id': row[3],
                        'sort_order': row[4],
                        'entry_type': row[5] if len(row) > 5 else EntryType.FILE.value,
                        'created_at': row[6] if len(row) > 6 else row[5]
                    }
                    for row in rows
                ]
                # アーカイブ設定に基づいてフィルタリング
                return self._filter_entries_by_archive_settings(bookmark_list)
        except Exception as e:
            logger.error(get_log_text("database_get_bookmarks_failed", error=e))
            return []
    def get_all_bookmarks(self) -> List[Dict[str, Any]]:
        """すべてのブックマークを取得（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_path, page_number, title, folder_id, sort_order, entry_type, created_at
                    FROM bookmarks
                    WHERE profile_name = ?
                    ORDER BY folder_id ASC, sort_order ASC
                ''', (self.current_profile,))
                rows = cursor.fetchall()
                bookmark_list = [
                    {
                        'file_path': row[0],
                        'page_number': row[1],
                        'title': row[2],
                        'folder_id': row[3],
                        'sort_order': row[4],
                        'entry_type': row[5] if len(row) > 5 else EntryType.FILE.value,
                        'created_at': row[6] if len(row) > 6 else row[5]
                    }
                    for row in rows
                ]
                # アーカイブ設定に基づいてフィルタリング
                return self._filter_entries_by_archive_settings(bookmark_list)
        except Exception as e:
            logger.error(get_log_text("database_get_all_bookmarks_failed", error=e))
            return []
    def update_bookmark_order(self, bookmark_id: int, new_order: int) -> bool:
        """ブックマークの順序を更新"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE bookmarks SET sort_order = ? WHERE id = ?
                ''', (new_order, bookmark_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(get_log_text("database_bookmark_order_update_failed", error=e))
            return False
    def move_bookmark_to_folder(self, file_path: str, page_number: int, folder_id: int) -> bool:
        """ブックマークを別のフォルダに移動"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE bookmarks SET folder_id = ? WHERE file_path = ? AND page_number = ? AND profile_name = ?
                ''', (folder_id, file_path, page_number, self.current_profile))
                conn.commit()
                return True
        except Exception as e:
            logger.error(get_log_text("database_bookmark_move_failed", error=e))
            return False
    def add_history(self, file_path: str, page_number: int, title: str = None, entry_type: str = EntryType.FILE.value, encrypted_password: str = None) -> bool:
        """履歴を追加（同じファイル・ページ・タイプ・プロファイルの組み合わせが既に存在する場合は日付だけ更新）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                # 同じファイル、ページ、タイプ、プロファイルの組み合わせが既に存在するかチェック
                cursor.execute('''
                    SELECT id FROM history 
                    WHERE file_path = ? AND page_number = ? AND entry_type = ? AND profile_name = ?
                ''', (file_path, page_number, entry_type, self.current_profile))
                existing_record = cursor.fetchone()
                if existing_record:
                    if encrypted_password is not None:
                        cursor.execute('''
                            UPDATE history 
                            SET accessed_at = CURRENT_TIMESTAMP, title = ?, encrypted_password = ?
                            WHERE file_path = ? AND page_number = ? AND entry_type = ? AND profile_name = ?
                        ''', (title, encrypted_password, file_path, page_number, entry_type, self.current_profile))
                    else:
                        cursor.execute('''
                            UPDATE history 
                            SET accessed_at = CURRENT_TIMESTAMP, title = ?
                            WHERE file_path = ? AND page_number = ? AND entry_type = ? AND profile_name = ?
                        ''', (title, file_path, page_number, entry_type, self.current_profile))
                    # logger.info(get_log_text("database_history_updated", file_path=file_path, page_number=page_number, entry_type=entry_type))
                else:
                    cursor.execute('''
                        INSERT INTO history (file_path, page_number, title, entry_type, profile_name, accessed_at, encrypted_password)
                        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                    ''', (file_path, page_number, title, entry_type, self.current_profile, encrypted_password))
                    # logger.info(get_log_text("database_history_added", file_path=file_path, page_number=page_number, entry_type=entry_type))
                conn.commit()
                return True
        except Exception as e:
            logger.error(get_log_text("database_history_add_failed", error=e))
            return False

    def get_stored_archive_password(self, file_path: str) -> Optional[str]:
        """履歴に保存したファイルパスワードを復号して返す。"""
        try:
            from ez_co.utils.password_protect import decrypt_secret
            from ez_co.handlers.archive_password import normalize_archive_path
            from ez_co.handlers.virtual_path_handler import VirtualPathHandler

            candidates = {file_path}
            try:
                candidates.add(normalize_archive_path(file_path))
            except Exception:
                pass
            if VirtualPathHandler.is_virtual_path(file_path):
                parsed = VirtualPathHandler.parse_virtual_path(file_path)
                if parsed:
                    candidates.add(str(parsed[0]))
                    try:
                        candidates.add(normalize_archive_path(str(parsed[0])))
                    except Exception:
                        pass

            with self._connect() as conn:
                cursor = conn.cursor()
                placeholders = ",".join("?" * len(candidates))
                cursor.execute(f'''
                    SELECT encrypted_password FROM history
                    WHERE profile_name = ?
                      AND encrypted_password IS NOT NULL
                      AND encrypted_password != ''
                      AND file_path IN ({placeholders})
                    ORDER BY accessed_at DESC
                    LIMIT 1
                ''', (self.current_profile, *candidates))
                row = cursor.fetchone()
                if not row:
                    return None
                return decrypt_secret(row[0])
        except Exception as e:
            logger.error(get_log_text("database_get_stored_archive_password_failed", error=e))
            return None

    def get_stored_pdf_password(self, file_path: str) -> Optional[str]:
        return self.get_stored_archive_password(file_path)
    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """履歴を取得（最新のものから、現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_path, page_number, title, entry_type, accessed_at
                    FROM history
                    WHERE profile_name = ?
                    ORDER BY accessed_at DESC
                    LIMIT ?
                ''', (self.current_profile, limit))
                rows = cursor.fetchall()
                history_list = [
                    {
                        'file_path': row[0],
                        'page_number': row[1],
                        'title': row[2],
                        'entry_type': row[3],
                        'accessed_at': row[4]
                    }
                    for row in rows
                ]
                # アーカイブ設定に基づいてフィルタリング
                return self._filter_entries_by_archive_settings(history_list)
        except Exception as e:
            logger.error(get_log_text("database_get_history_failed", error=e))
            return []
    def get_latest_history(self) -> Optional[Dict[str, Any]]:
        """最新の履歴を取得（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_path, page_number, title, entry_type, accessed_at
                    FROM history
                    WHERE profile_name = ?
                    ORDER BY accessed_at DESC
                    LIMIT 1
                ''', (self.current_profile,))
                row = cursor.fetchone()
                if row:
                    return {
                        'file_path': row[0],
                        'page_number': row[1],
                        'title': row[2],
                        'entry_type': row[3],
                        'accessed_at': row[4]
                    }
                return None
        except Exception as e:
            logger.error(get_log_text("database_get_latest_history_failed", error=e))
            return None
    def clear_history(self) -> bool:
        """履歴をすべて削除（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM history WHERE profile_name = ?', (self.current_profile,))
                conn.commit()
                logger.info(get_log_text("database_history_cleared"))
                return True
        except Exception as e:
            logger.error(get_log_text("database_history_clear_failed", error=e))
            return False
    def cleanup_old_history(self, max_count: int) -> bool:
        """古い履歴を削除して最大数を制限（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM history 
                    WHERE profile_name = ? AND id NOT IN (
                        SELECT id FROM history 
                        WHERE profile_name = ?
                        ORDER BY accessed_at DESC 
                        LIMIT ?
                    )
                ''', (self.current_profile, self.current_profile, max_count))
                conn.commit()
                logger.info(get_log_text("database_history_cleaned", max_count=max_count))
                return True
        except Exception as e:
            logger.error(get_log_text("database_history_cleanup_failed", error=e))
            return False
    def add_bookmark_folder(self, name: str, parent_id: int = 0) -> int:
        """ブックマークフォルダを追加"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                # 最大のsort_orderを取得（現在のプロファイル内で）
                cursor.execute('''
                    SELECT MAX(sort_order) FROM bookmark_folders WHERE parent_id = ? AND profile_name = ?
                ''', (parent_id, self.current_profile))
                max_order = cursor.fetchone()[0] or 0
                new_order = max_order + 1
                cursor.execute('''
                    INSERT INTO bookmark_folders (name, parent_id, sort_order, profile_name, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ''', (name, parent_id, new_order, self.current_profile))
                conn.commit()
                folder_id = cursor.lastrowid
                # logger.info(get_log_text("database_bookmark_folder_added", folder_name=name, folder_id=folder_id))
                return folder_id
        except Exception as e:
            logger.error(get_log_text("database_bookmark_folder_add_failed", error=e))
            return 0
    def get_bookmark_folders(self, parent_id: int = 0) -> List[Dict[str, Any]]:
        """ブックマークフォルダを取得（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT id, name, parent_id, sort_order, created_at
                    FROM bookmark_folders
                    WHERE parent_id = ? AND profile_name = ?
                    ORDER BY sort_order ASC
                ''', (parent_id, self.current_profile))
                rows = cursor.fetchall()
                return [
                    {
                        'id': row[0],
                        'name': row[1],
                        'parent_id': row[2],
                        'sort_order': row[3],
                        'created_at': row[4]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(get_log_text("database_get_bookmark_folders_failed", error=e))
            return []
    def get_last_used_folder(self) -> int:
        """最後に使用されたフォルダIDを取得（設定から）"""
        # ここでは簡単に0（ルート）を返す。実際の実装では設定ファイルから取得
        return 0 
    def delete_bookmark_folder(self, folder_id: int) -> bool:
        """ブックマークフォルダを削除"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                # フォルダ内にブックマークやサブフォルダがないことを確認（プロファイル内で）
                cursor.execute("SELECT COUNT(*) FROM bookmarks WHERE folder_id = ? AND profile_name = ?", (folder_id, self.current_profile))
                bookmark_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM bookmark_folders WHERE parent_id = ? AND profile_name = ?", (folder_id, self.current_profile))
                subfolder_count = cursor.fetchone()[0]
                if bookmark_count > 0 or subfolder_count > 0:
                    # logger.warning(get_log_text("database_folder_delete_warning", folder_id=folder_id, bookmark_count=bookmark_count, subfolder_count=subfolder_count))
                    return False
                cursor.execute("DELETE FROM bookmark_folders WHERE id = ? AND profile_name = ?", (folder_id, self.current_profile))
                conn.commit()
                logger.info(get_log_text("database_bookmark_folder_deleted", folder_id=folder_id))
                return True
        except Exception as e:
            logger.error(get_log_text("database_bookmark_folder_delete_failed", error=e))
            return False
    def rename_bookmark_folder(self, folder_id: int, new_name: str) -> bool:
        """ブックマークフォルダの名前を変更"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("UPDATE bookmark_folders SET name = ? WHERE id = ? AND profile_name = ?", (new_name, folder_id, self.current_profile))
                conn.commit()
                # logger.info(get_log_text("database_bookmark_folder_renamed", folder_id=folder_id, new_name=new_name))
                return True
        except Exception as e:
            logger.error(get_log_text("database_bookmark_folder_rename_failed", error=e))
            return False
    def get_bookmark(self, file_path: str, page_number: int) -> Optional[Dict[str, Any]]:
        """特定のファイルとページのブックマークを取得（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, file_path, page_number, title, folder_id, entry_type, created_at FROM bookmarks WHERE file_path = ? AND page_number = ? AND profile_name = ?",
                    (file_path, page_number, self.current_profile)
                )
                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'file_path': row[1],
                        'page_number': row[2],
                        'title': row[3],
                        'folder_id': row[4],
                        'entry_type': row[5] if len(row) > 5 else EntryType.FILE.value,
                        'created_at': row[6] if len(row) > 6 else row[5]
                    }
                return None
        except Exception as e:
            logger.error(get_log_text("database_get_bookmark_failed", error=e))
            return None
    def delete_history_item(self, file_path: str, page_number: int, entry_type: str = EntryType.FILE.value) -> bool:
        """履歴アイテムを削除（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM history 
                    WHERE file_path = ? AND page_number = ? AND entry_type = ? AND profile_name = ?
                ''', (file_path, page_number, entry_type, self.current_profile))
                conn.commit()
                # logger.info(get_log_text("database_history_item_deleted", file_path=file_path, page_number=page_number, entry_type=entry_type))
                return True
        except Exception as e:
            logger.error(get_log_text("database_history_item_delete_failed", error=e))
            return False
    def delete_history_by_file_path(self, file_path: str, entry_type: str = EntryType.FILE.value) -> bool:
        """同じファイル/フォルダの既存の履歴を削除（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM history 
                    WHERE file_path = ? AND entry_type = ? AND profile_name = ?
                ''', (file_path, entry_type, self.current_profile))
                conn.commit()
                # logger.info(get_log_text("database_history_file_deleted", file_path=file_path, entry_type=entry_type))
                return True
        except Exception as e:
            logger.error(get_log_text("database_history_file_delete_failed", error=e))
            return False
    def get_history_by_file_path(self, file_path: str, entry_type: str = EntryType.FILE.value) -> Optional[Dict[str, Any]]:
        """特定のファイルパスの履歴を取得（現在のプロファイル）"""
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT file_path, page_number, title, entry_type, accessed_at
                    FROM history
                    WHERE file_path = ? AND entry_type = ? AND profile_name = ?
                    ORDER BY accessed_at DESC
                    LIMIT 1
                ''', (file_path, entry_type, self.current_profile))
                row = cursor.fetchone()
                if row:
                    return {
                        'file_path': row[0],
                        'page_number': row[1],
                        'title': row[2],
                        'entry_type': row[3],
                        'accessed_at': row[4]
                    }
                return None
        except Exception as e:
            logger.error(get_log_text("database_get_history_by_file_path_failed", error=e))
            return None
    
    def _should_filter_archive_entry(self, file_path: str) -> bool:
        """アーカイブ設定に基づいてエントリをフィルタリングするかどうかを判定"""
        if not self.config:
            # logger.info(get_log_text("debug_filter_entry_no_config", file_path=file_path))
            return False
        
        # virtual pathの場合はアーカイブファイル部分を抽出
        actual_archive_path = file_path
        is_virtual_path = file_path.startswith("archive:")
        if is_virtual_path:
            try:
                from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                archive_path, internal_path = VirtualPathHandler.parse_virtual_path(file_path)
                actual_archive_path = str(archive_path)
                # logger.info(get_log_text("debug_filter_virtual_path", file_path=file_path, archive_path=actual_archive_path))
            except Exception as e:
                logger.error(get_log_text("debug_filter_virtual_path_error", file_path=file_path, error=e))
                return False

        from ez_co.plugins.manager import get_plugin_manager
        decision = get_plugin_manager().resolve(actual_archive_path, self.config)
        if decision.is_skipped:
            return True
        
        # アーカイブファイルかどうかを確認
        is_archive = ArchiveInfo.is_archive_file(actual_archive_path) or is_virtual_path
        # logger.info(get_log_text("debug_filter_entry_check", file_path=file_path, is_archive=is_archive))
        
        # アーカイブサポートが無効な場合、すべてのアーカイブファイルをフィルタリング
        archive_enabled = self.config.archive.get("enabled", True)
        if not archive_enabled:
            if is_archive:
                # logger.info(get_log_text("debug_filter_entry_archive_disabled", file_path=file_path))
                return True
        
        # 特定のアーカイブタイプが無効な場合、そのタイプのファイルをフィルタリング
        archive_type = ArchiveInfo.get_archive_type_by_path(actual_archive_path)
        if archive_type is not None:
            config_key = ArchiveInfo.get_config_key(archive_type)
            type_enabled = self.config.archive.get(config_key, True)
            # logger.info(get_log_text("debug_filter_entry_type_check", file_path=file_path, archive_type=ArchiveInfo.get_display_name(archive_type), config_key=config_key, type_enabled=type_enabled))
            if not type_enabled:
                # logger.info(get_log_text("debug_filter_entry_type_disabled", file_path=file_path, archive_type=ArchiveInfo.get_display_name(archive_type)))
                return True
        
        # logger.info(get_log_text("debug_filter_entry_not_filtered", file_path=file_path))
        return False
    
    def _filter_entries_by_archive_settings(self, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """アーカイブ設定に基づいてエントリリストをフィルタリング"""
        if not self.config:
            logger.info(get_log_text("debug_filter_no_config"))
            return entries
        
        filtered_entries = []
        filtered_count = 0
        for entry in entries:
            file_path = entry['file_path']
            should_filter = self._should_filter_archive_entry(file_path)
            if should_filter:
                filtered_count += 1
                # logger.info(get_log_text("debug_filter_entry_filtered", file_path=file_path))
            else:
                filtered_entries.append(entry)
        
        # logger.info(get_log_text("debug_filter_summary", total=len(entries), filtered=filtered_count, remaining=len(filtered_entries)))
        return filtered_entries 