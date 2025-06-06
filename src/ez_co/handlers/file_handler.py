import os
import py7zr
import rarfile
import tarfile
import gzip
import bz2
import lzma
from pathlib import Path
from typing import List, Optional, Generator, Union, Tuple
from PIL import Image
import io
import logging
import shutil
from collections import OrderedDict
import time
import threading
from queue import Queue, PriorityQueue
from concurrent.futures import ThreadPoolExecutor
import queue
import traceback
import tempfile
import concurrent.futures
import re
from ez_co.enums.archives import ArchiveInfo, ArchiveType
from ez_co.enums.images import ImageInfo
from ez_co.enums.encodings import EncodingInfo
from ez_co.handlers.virtual_path_handler import VirtualPathHandler
from ez_co.handlers.archive_password import (
    PASSWORD_ARCHIVE_TYPES,
    apply_rar_password,
    apply_zip_password,
    get_session_password,
    open_zip,
    seven_zip_password_arg,
)
from ez_co.handlers.pdf_handler import list_pdf_entries, load_pdf_image
from ez_co.utils.language_manager import get_text, get_log_text
import humanfriendly
logger = logging.getLogger(__name__)
def natural_sort_key(path):
    """自然順序ソート用のキー生成関数（数字を考慮）"""
    # ファイル名を取得（仮想パスの場合は|以降の部分を取得）
    path_str = str(path)
    if '|' in path_str:
        # 仮想パスの場合（archive://path|filename形式）
        filename = path_str.split('|')[-1]
    else:
        # 通常のパスの場合
        filename = str(path.name)
    
    # ファイル名から数字と文字を分離してソート
    parts = []
    for part in re.split(r'(\d+)', filename.lower()):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
    return parts
class FileHandler:
    # 画像拡張子をenumから取得
    SUPPORTED_IMAGE_EXTENSIONS = ImageInfo.get_all_extensions()
    SUPPORTED_ARCHIVE_EXTENSIONS = ArchiveInfo.get_all_extensions()
    def __init__(self, config=None, plugin_manager=None):
        self.config = config
        self.plugin_manager = plugin_manager
        self.current_files = []
        self.current_index = 0
        self.current_archive = None
        self.current_archive_path = None
        # 新しいファイルハンドル管理設定用
        self.archive_metadata_cache = {}  # 将来のキャッシュ機能用
        self.image_cache = {}
        self.cache_size = 0
        # 設定からキャッシュサイズを読み込み、humanfriendlyでパース
        self.cache_limit = self._parse_cache_size()
        self._on_image_loaded = None
        self._on_error_occurred = None  # エラー発生時のコールバック
        self._archive_password_provider = None
        self._current_loading = None
        self._loading_lock = threading.Lock()
        self._prefetch_lock = threading.Lock()
        self._prefetch_in_progress = set()
        self._prefetch_pending = set()
        # プリフェッチスレッド関連
        self._prefetch_thread = None
        self._prefetch_running = False
        # ワーカースレッド用のキュー
        self._image_queue = queue.Queue()
        self._prefetch_queue = queue.PriorityQueue()
        # スレッドプール
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=3)
        # 処理停止フラグ
        self._stop_all_loading = threading.Event()
        self._current_session_id = 0
        self._session_lock = threading.Lock()
        # ワーカースレッドを開始
        self._start_workers()
        # 一時ディレクトリの作成
        self.temp_dir = None
        self._create_temp_dir()
    def _start_workers(self):
        def prefetch_worker():
            logger.info(get_log_text("debug_prefetch_worker_started"))
            while True:
                try:
                    # タイムアウト付きでキューから取得
                    priority, index = self._prefetch_queue.get(timeout=1.0)
                    if index is None:
                        logger.info(get_log_text("debug_prefetch_worker_stopping"))
                        break
                    
                    # セッションが無効になっていないかチェック
                    current_session = self._get_current_session_id()
                    if self._stop_all_loading.is_set():
                        logger.info(get_log_text("debug_prefetch_worker_session_cancelled", session_id=current_session, index=index))
                        self._prefetch_queue.task_done()
                        continue
                    
                    logger.info(get_log_text("debug_prefetch_worker_processing", priority=priority, index=index, session_id=current_session))
                    self._prefetch_around(index, current_session)
                    self._prefetch_queue.task_done()
                except queue.Empty:
                    # タイムアウトは正常な動作なのでログを出力しない
                    continue
                except Exception as e:
                    logger.error(get_log_text("file_handler_worker_error", error=e))
        def image_loader_worker():
            logger.info(get_log_text("debug_image_loader_worker_started"))
            while True:
                try:
                    # タイムアウト付きでキューから取得
                    task = self._image_queue.get(timeout=1.0)
                    if task is None:
                        logger.info(get_log_text("debug_image_loader_worker_stopping"))
                        break
                    
                    file, cache_key, is_current, session_id = task
                    
                    # セッションが無効になっていないかチェック
                    if not self._is_session_active(session_id):
                        logger.info(get_log_text("debug_image_loader_worker_session_cancelled", session_id=session_id, file=file))
                        if not is_current:
                            with self._prefetch_lock:
                                self._prefetch_pending.discard(cache_key)
                        self._image_queue.task_done()
                        continue
                    
                    logger.info(get_log_text("debug_image_loader_worker_processing", file=file, cache_key=cache_key, is_current=is_current, session_id=session_id))
                    self._load_image(file, cache_key, is_current, session_id)
                    self._image_queue.task_done()
                except queue.Empty:
                    # タイムアウトは正常な動作なのでログを出力しない
                    continue
                except Exception as e:
                    logger.error(get_log_text("file_handler_worker_error", error=e))
        logger.info(get_log_text("debug_starting_worker_threads"))
        threading.Thread(target=prefetch_worker, daemon=True).start()
        threading.Thread(target=image_loader_worker, daemon=True).start()
        logger.info(get_log_text("debug_worker_threads_started"))

    def stop_all_loading(self):
        """現在進行中のすべての読み込み処理を停止"""
        logger.info(get_log_text("file_handler_stopping_all_loading"))
        
        # 停止フラグを設定
        self._stop_all_loading.set()
        
        # 新しいセッションIDを生成
        with self._session_lock:
            self._current_session_id += 1
            current_session = self._current_session_id
            logger.info(get_log_text("file_handler_new_session_started", session_id=current_session))
        
        # キューをクリア
        try:
            while not self._image_queue.empty():
                try:
                    self._image_queue.get_nowait()
                    self._image_queue.task_done()
                except queue.Empty:
                    break
        except Exception as e:
            logger.debug(get_log_text("file_handler_queue_clear_error", queue_name="image_queue", error=e))
        
        try:
            while not self._prefetch_queue.empty():
                try:
                    self._prefetch_queue.get_nowait()
                    self._prefetch_queue.task_done()
                except queue.Empty:
                    break
        except Exception as e:
            logger.debug(get_log_text("file_handler_queue_clear_error", queue_name="prefetch_queue", error=e))
        
        with self._prefetch_lock:
            self._prefetch_pending.clear()
            self._prefetch_in_progress.clear()
        
        # キャッシュをクリア（大きなアーカイブファイルのメモリを解放）
        self._clear_image_cache()
        
        # 停止フラグをリセット
        self._stop_all_loading.clear()
        
        logger.info(get_log_text("file_handler_all_loading_stopped", session_id=current_session))
        
        return current_session

    def _clear_image_cache(self):
        """画像キャッシュを完全にクリア"""
        logger.info(get_log_text("file_handler_clearing_image_cache", cache_size=len(self.image_cache), memory_size=self.cache_size))
        self.image_cache.clear()
        self.cache_size = 0
        logger.info(get_log_text("file_handler_image_cache_cleared"))

    def _get_current_session_id(self) -> int:
        """現在のセッションIDを取得"""
        with self._session_lock:
            return self._current_session_id

    def _is_session_active(self, session_id: int) -> bool:
        """指定されたセッションがアクティブかチェック"""
        return session_id == self._get_current_session_id() and not self._stop_all_loading.is_set()
    def open_file(self, file_path: Union[str, Path]) -> bool:
        """単一ファイルを開く"""
        logger.info(get_log_text("file_handler_opening_single_file", file_path=file_path))
        return self.open_files([file_path])
    def is_archive_supported(self, file_path: Union[str, Path]) -> bool:
        """アーカイブファイルがサポートされているかチェック"""
        if not self.config:
            logger.warning(get_log_text("debug_no_config_available_archive_check", file_path=file_path))
            return False
        decision = self._resolve_handler(file_path)
        if decision.is_skipped:
            logger.info(get_log_text("debug_archive_support_disabled_globally", file_path=file_path))
            return False
        if not self.config.archive.get("enabled", True):
            logger.info(get_log_text("debug_archive_support_disabled_globally", file_path=file_path))
            return False
        if decision.is_plugin and decision.is_archive:
            logger.info(get_log_text("debug_plugin_archive_support", file_path=file_path, plugin_id=decision.provider_id))
            return True
        if not decision.is_archive:
            logger.info(get_log_text("debug_archive_type_not_supported", file_path=file_path))
            return False
        # enumからアーカイブタイプを取得
        archive_type = ArchiveInfo.get_archive_type_by_path(str(file_path))
        if archive_type is None:
            logger.info(get_log_text("debug_archive_type_not_supported", file_path=file_path))
            return False
        # 設定キーを取得してサポート状況をチェック
        config_key = ArchiveInfo.get_config_key(archive_type)
        supported = self.config.archive.get(config_key, True)
        logger.info(get_log_text("debug_archive_support", archive_type=ArchiveInfo.get_display_name(archive_type), supported=supported, file_path=file_path))
        return supported

    def _get_plugin_manager(self):
        if self.plugin_manager is None:
            from ez_co.plugins.manager import get_plugin_manager
            self.plugin_manager = get_plugin_manager()
        return self.plugin_manager

    def _resolve_handler(self, file_path: Union[str, Path]):
        return self._get_plugin_manager().resolve(str(file_path), self.config)

    def _is_handled_archive(self, file_path: Union[str, Path]) -> bool:
        return self._resolve_handler(file_path).is_archive

    def _is_plugin_image(self, file_path: Union[str, Path]) -> bool:
        decision = self._resolve_handler(file_path)
        return decision.is_plugin and decision.is_image

    def _is_supported_by_plugins(self, file_path: Union[str, Path]) -> bool:
        decision = self._resolve_handler(file_path)
        return decision.kind is not None

    def _image_from_bytes(self, data: bytes) -> Optional[Image.Image]:
        image = Image.open(io.BytesIO(data))
        image.load()
        return image

    def _load_plugin_image(self, file_path: Union[str, Path]) -> Optional[Image.Image]:
        try:
            decision = self._resolve_handler(file_path)
            if not (decision.plugin and decision.is_image):
                return None
            entry = decision.plugin.read_entry(str(file_path), 0)
            data = entry.data if hasattr(entry, "data") else entry[1]
            return self._image_from_bytes(data)
        except Exception as exc:
            logger.error(get_log_text("debug_plugin_read_failed", file_path=file_path, error=exc))
            return None

    def _expand_plugin_archive(self, archive_path: Path, plugin) -> List[Path]:
        files = []
        try:
            names = plugin.list_entries(str(archive_path))
        except Exception as exc:
            logger.error(get_log_text("debug_plugin_read_failed", file_path=archive_path, error=exc))
            return files
        for name in names:
            virtual_path = Path(f"archive://{archive_path}|{name}")
            files.append(virtual_path)
            logger.debug(get_log_text("file_handler_found_image_in_archive", decoded_name=name))
        return files

    def _read_plugin_archive_entry(self, archive_path_str: str, filename: str, plugin) -> Optional[Image.Image]:
        try:
            names = plugin.list_entries(archive_path_str)
            target_index = None
            normalized = filename.replace("\\", "/")
            for index, name in enumerate(names):
                if name.replace("\\", "/") == normalized:
                    target_index = index
                    break
            if target_index is None:
                base = Path(normalized).name
                for index, name in enumerate(names):
                    if Path(str(name).replace("\\", "/")).name == base:
                        target_index = index
                        break
            if target_index is None:
                error_msg = get_log_text("debug_file_not_found_in_archive", filename=filename)
                logger.error(error_msg)
                self._notify_error("file_not_in_archive", error_msg, archive_path_str)
                return None
            entry = plugin.read_entry(archive_path_str, target_index)
            data = entry.data if hasattr(entry, "data") else entry[1]
            return self._image_from_bytes(data)
        except Exception as exc:
            logger.error(get_log_text("debug_plugin_read_failed", file_path=archive_path_str, error=exc))
            return None
    def open_files(self, files: List[Union[str, Path]]) -> bool:
        """複数のファイルを開く"""
        try:
            logger.info(get_log_text("file_handler_opening_files", files=files))
            
            # 既存の読み込み処理をすべて停止
            session_id = self.stop_all_loading()
            
            # アーカイブ設定の状況をログに出力
            if self.config:
                logger.info(get_log_text("debug_archive_settings", enabled=self.config.archive.get('enabled', True)))
                logger.info(get_log_text("debug_archive_types", archive_types=self.config.archive))
            else:
                logger.warning(get_log_text("debug_no_config_available"))
            # ファイルリストをクリア
            self.current_files = []
            skipped_archives = []
            for file in files:
                logger.info(get_log_text("debug_processing_file", file=file, is_dir=Path(file).is_dir() if hasattr(Path(file), 'is_dir') else 'N/A', exists=Path(file).exists() if hasattr(Path(file), 'exists') else 'N/A'))
                # archive:\... 形式の仮想パスの処理
                if isinstance(file, str) and VirtualPathHandler.is_virtual_path(file):
                    logger.info(get_log_text("debug_processing_virtual_path", file=file))
                    result = VirtualPathHandler.parse_virtual_path(file)
                    if result:
                        archive_path, inner_file = result
                        # アーカイブファイルが存在するかチェック
                        if archive_path.exists():
                            # アーカイブ設定をチェック
                            if not self.is_archive_supported(archive_path):
                                logger.warning(get_log_text("debug_archive_not_supported_by_settings", archive_path=archive_path))
                                skipped_archives.append(str(archive_path))
                                continue
                            # アーカイブ全体を展開してcurrent_filesに追加
                            archive_files = self._expand_archive(archive_path)
                            if archive_files:
                                # 指定された画像のインデックスを探す
                                target_index = 0
                                for i, archive_file in enumerate(archive_files):
                                    if str(archive_file).endswith(f"|{inner_file}"):
                                        target_index = i
                                        break
                                # アーカイブ全体を追加
                                self.current_files.extend(archive_files)
                                # 指定された画像のインデックスを設定
                                self.current_index = len(self.current_files) - len(archive_files) + target_index
                                logger.info(get_log_text("debug_added_archive_files", file_count=len(archive_files), current_index=self.current_index))
                            else:
                                logger.warning(get_log_text("debug_no_images_found_in_archive", archive_path=archive_path))
                        else:
                            logger.warning(get_log_text("debug_archive_file_not_found", archive_path=archive_path))
                    else:
                        logger.warning(get_log_text("debug_failed_to_parse_virtual_path", file=file))
                    continue
                # 通常のファイル・ディレクトリの処理
                file_path = Path(file) if isinstance(file, str) else file
                if file_path.is_dir():
                    logger.info(get_log_text("debug_scanning_directory", file_path=file_path))
                    directory_files = self._scan_directory(file_path)
                    self.current_files.extend(directory_files)
                elif file_path.is_file():
                    logger.info(get_log_text("debug_adding_single_file", file_path=file_path))
                    self.current_files.append(file_path)
                else:
                    logger.warning(get_log_text("file_handler_file_not_found", file=file))
            logger.info(get_log_text("debug_total_files_found", file_count=len(self.current_files)))
            logger.info(get_log_text("debug_files_list", files_list=self.current_files))
            # スキップされたアーカイブファイルがある場合はログに記録
            if skipped_archives:
                logger.info(get_log_text("debug_skipped_archives_due_to_settings", skipped_archives=skipped_archives))
            if not self.current_files:
                logger.error(get_log_text("file_handler_no_valid_files"))
                return False
            # 新しいファイルを開く時は常に1ページ目から開始
            self.current_index = 0
            logger.info(get_log_text("debug_initial_file_index_set", current_index=self.current_index, current_file=self.current_files[self.current_index]))
            logger.info(get_log_text("debug_about_to_call_open_current_file"))
            success = self._open_current_file()
            if success:
                # 先読みを開始
                self._prefetch_around(self.current_index)
                logger.info(get_log_text("debug_file_opened_successfully", file_count=len(self.current_files), current_index=self.current_index))
            else:
                logger.error(get_log_text("debug_failed_to_open_current_file"))
            return success
        except Exception as e:
            logger.error(get_log_text("file_handler_failed_to_open_files", error=e))
            return False
    def _scan_directory(self, directory: Path) -> List[Path]:
        """ディレクトリ内の画像ファイルとアーカイブファイルを再帰的に検索"""
        logger.info(get_log_text("debug_scanning_directory", file_path=directory))
        files = []
        skipped_archives = []
        
        # ディレクトリが存在するかチェック
        if not directory.exists():
            error_msg = get_log_text("file_handler_folder_access_failed", directory=directory, error="Directory does not exist")
            logger.error(error_msg)
            self._notify_error("folder_access_failed", error_msg, str(directory))
            return files
        
        if not directory.is_dir():
            error_msg = get_log_text("file_handler_folder_access_failed", directory=directory, error="Path is not a directory")
            logger.error(error_msg)
            self._notify_error("folder_access_failed", error_msg, str(directory))
            return files
        
        # 設定に応じてスキャン方式を決定
        should_keep_handles = self._should_keep_archive_handles()
        logger.info(get_log_text("debug_directory_scan_handle_management", 
                                directory=directory, keep_handles=should_keep_handles))
        
        try:
            if should_keep_handles:
                # 従来方式：Path.rglob()を使用（ディレクトリハンドル保持）
                logger.info(get_log_text("debug_using_rglob_scan", directory=directory))
                for path in directory.rglob('*'):
                    logger.debug(get_log_text("file_handler_checking_path", path=path))
                    if path.is_file():
                        self._process_file_in_scan(path, files, skipped_archives)
            else:
                # 新方式：os.walk()を使用（ディレクトリハンドル即座解放）
                logger.info(get_log_text("debug_using_os_walk_scan", directory=directory))
                import os
                for root, dirs, file_names in os.walk(str(directory)):
                    root_path = Path(root)
                    for file_name in file_names:
                        file_path = root_path / file_name
                        # 拡張子ベースの軽量チェック（is_file()を最小限に）
                        if self._is_supported_file_extension(file_path):
                            self._process_file_in_scan(file_path, files, skipped_archives)
        except PermissionError as e:
            error_msg = get_log_text("file_handler_folder_access_failed", directory=directory, error=f"Permission denied: {e}")
            logger.error(error_msg)
            self._notify_error("folder_access_failed", error_msg, str(directory))
        except FileNotFoundError as e:
            error_msg = get_log_text("file_handler_folder_access_failed", directory=directory, error=f"Folder not found: {e}")
            logger.error(error_msg)
            self._notify_error("folder_access_failed", error_msg, str(directory))
        except OSError as e:
            error_msg = get_log_text("file_handler_folder_access_failed", directory=directory, error=f"OS error: {e}")
            logger.error(error_msg)
            self._notify_error("folder_access_failed", error_msg, str(directory))
        except Exception as e:
            logger.error(get_log_text("file_handler_error_during_directory_scan", error=e))
        
        # スキップされたアーカイブファイルがある場合はログに記録
        if skipped_archives:
            logger.info(get_log_text("debug_skipped_archives_during_directory_scan", skipped_archives=skipped_archives))
        # 自然順序でソート
        files.sort(key=natural_sort_key)
        logger.info(get_log_text("debug_directory_scan_completed", file_count=len(files)))
        logger.info(get_log_text("debug_found_files", files_list=files))
        return files
    
    def _is_supported_file_extension(self, file_path: Path) -> bool:
        """拡張子ベースでサポートファイルかチェック（軽量版）"""
        try:
            if self._resolve_handler(file_path).is_skipped:
                return False
            suffix = file_path.suffix.lower()
            return (suffix in self.SUPPORTED_IMAGE_EXTENSIONS or
                    ArchiveInfo.is_archive_file(str(file_path)) or
                    self._is_supported_by_plugins(file_path))
        except Exception:
            return False
    
    def _process_file_in_scan(self, path: Path, files: List[Path], skipped_archives: List[str]):
        """スキャン中のファイル処理"""
        # ファイルハンドル管理設定に応じてファイル存在チェック
        should_keep_handles = self._should_keep_archive_handles()
        
        try:
            # ハンドル非保持モードでは軽量チェック
            if not should_keep_handles:
                # 拡張子のみでチェック（is_file()回避）
                if not self._is_supported_file_extension(path):
                    return
            else:
                # 従来通りの完全チェック
                if self._resolve_handler(path).is_skipped or not (
                    path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS or
                    ArchiveInfo.is_archive_file(str(path)) or
                    self._is_supported_by_plugins(path)
                ):
                    logger.debug(get_log_text("file_handler_skipping_unsupported_file", path=path, suffix=path.suffix.lower()))
                    return
            
            logger.debug(get_log_text("file_handler_found_supported_file", path=path, suffix=path.suffix.lower()))
            
            # アーカイブファイルの場合は中身を展開
            if self._is_handled_archive(path):
                # アーカイブ設定をチェック
                if not self.is_archive_supported(path):
                    logger.warning(get_log_text("debug_archive_not_supported_by_settings", archive_path=path))
                    skipped_archives.append(str(path))
                    return
                logger.info(get_log_text("debug_expanding_archive", archive_path=path))
                archive_files = self._expand_archive(path)
                logger.info(get_log_text("debug_archive_contains_images", archive_path=path, image_count=len(archive_files)))
                files.extend(archive_files)
            else:
                files.append(path)
        except Exception as e:
            logger.debug(get_log_text("debug_file_processing_error", path=path, error=e))
    def _decode_archive_filename(self, name: str, archive_type: str) -> str:
        """アーカイブファイル内のファイル名を適切なエンコーディングでデコード"""
        # 文字列のアーカイブタイプをenumに変換
        archive_type_enum = None
        for at in ArchiveType:
            if ArchiveInfo.get_internal_name(at) == archive_type:
                archive_type_enum = at
                break
        if archive_type_enum is None:
            # 未知のアーカイブタイプの場合はデフォルトエンコーディングを使用
            encodings_to_try = EncodingInfo.get_default_encoding_combinations()
        else:
            # アーカイブタイプに応じたエンコーディング組み合わせを取得
            encodings_to_try = EncodingInfo.get_encoding_combinations_for_archive(archive_type)
        for source_encoding, target_encoding in encodings_to_try:
            try:
                if source_encoding == target_encoding:
                    decoded_name = name
                else:
                    decoded_name = name.encode(source_encoding).decode(target_encoding)
                # デコードされた名前が有効な文字列かチェック
                if decoded_name and not decoded_name.startswith('\x00'):
                    logger.debug(get_log_text("file_handler_successfully_decoded", name=name, source_encoding=source_encoding, target_encoding=target_encoding, decoded_name=decoded_name))
                    return decoded_name
            except (UnicodeEncodeError, UnicodeDecodeError, LookupError):
                continue
        # すべてのエンコーディングが失敗した場合は元の名前を使用
        logger.warning(get_log_text("debug_failed_to_decode_filename", name=name, archive_type=archive_type))
        return name
    def _decode_zip_filename(self, name: str) -> str:
        """ZIPファイル内のファイル名を適切なエンコーディングでデコード（後方互換性のため）"""
        return self._decode_archive_filename(name, ArchiveInfo.get_internal_name(ArchiveType.ZIP))
    def _expand_archive(self, archive_path: Path) -> List[Path]:
        """アーカイブファイル内の画像ファイルを展開"""
        logger.info(get_log_text("debug_expanding_archive", archive_path=archive_path))
        files = []
        try:
            decision = self._resolve_handler(archive_path)
            if decision.plugin and decision.is_archive:
                files = self._expand_plugin_archive(archive_path, decision.plugin)
                files.sort(key=natural_sort_key)
                logger.info(get_log_text("debug_expanded_images_from_archive", archive_path=archive_path, image_count=len(files)))
                return files
            archive_type = ArchiveInfo.get_archive_type_by_path(str(archive_path))
            if archive_type is None:
                logger.error(get_log_text("debug_unknown_archive_type", archive_path=archive_path))
                return files
            internal_name = ArchiveInfo.get_internal_name(archive_type)
            if archive_type in PASSWORD_ARCHIVE_TYPES:
                if not self._ensure_archive_unlocked(str(archive_path)):
                    logger.warning(get_log_text("debug_archive_password_cancelled", file_path=archive_path))
                    return files
            if archive_type in (ArchiveType.ZIP, ArchiveType.CBZ):
                with open_zip(archive_path) as archive:
                    apply_zip_password(archive, str(archive_path))
                    for name in archive.namelist():
                        # 文字エンコーディングの修正
                        decoded_name = self._decode_zip_filename(name)
                        logger.debug(get_log_text("file_handler_original_name_decoded", name=name, decoded_name=decoded_name))
                        if Path(decoded_name).suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                            # アーカイブ内の画像ファイルを仮想的なPathとして作成
                            virtual_path = Path(f"archive://{archive_path}|{decoded_name}")
                            files.append(virtual_path)
                            logger.debug(get_log_text("file_handler_found_image_in_archive", decoded_name=decoded_name))
            elif archive_type == ArchiveType.SEVEN_ZIP:
                with py7zr.SevenZipFile(archive_path, 'r', password=seven_zip_password_arg(str(archive_path))) as archive:
                    for name in archive.getnames():
                        # 文字エンコーディングの修正
                        decoded_name = self._decode_archive_filename(name, internal_name)
                        logger.debug(get_log_text("file_handler_original_name_decoded", name=name, decoded_name=decoded_name))
                        if Path(decoded_name).suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                            virtual_path = Path(f"archive://{archive_path}|{decoded_name}")
                            files.append(virtual_path)
                            logger.debug(get_log_text("file_handler_found_image_in_archive", decoded_name=decoded_name))
            elif archive_type in (ArchiveType.RAR, ArchiveType.CBR):
                with rarfile.RarFile(archive_path, 'r') as archive:
                    apply_rar_password(archive, str(archive_path))
                    for name in archive.namelist():
                        # 文字エンコーディングの修正
                        decoded_name = self._decode_archive_filename(name, internal_name)
                        # パス区切り文字を正規化（バックスラッシュをスラッシュに変換）
                        normalized_name = decoded_name.replace('\\', '/')
                        logger.debug(get_log_text("file_handler_original_name_decoded_normalized", name=name, decoded_name=decoded_name, normalized_name=normalized_name))
                        if Path(normalized_name).suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                            virtual_path = Path(f"archive://{archive_path}|{normalized_name}")
                            files.append(virtual_path)
                            logger.debug(get_log_text("file_handler_found_image_in_rar", normalized_name=normalized_name))
            elif archive_type in [ArchiveType.TAR, ArchiveType.TAR_GZ, ArchiveType.TAR_BZ2, ArchiveType.TAR_XZ]:
                with tarfile.open(archive_path) as archive:
                    for name in archive.getnames():
                        # 文字エンコーディングの修正
                        decoded_name = self._decode_archive_filename(name, internal_name)
                        logger.debug(get_log_text("file_handler_original_name_decoded", name=name, decoded_name=decoded_name))
                        if Path(decoded_name).suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                            virtual_path = Path(f"archive://{archive_path}|{decoded_name}")
                            files.append(virtual_path)
                            logger.debug(get_log_text("file_handler_found_image_in_tar", decoded_name=decoded_name))
            elif archive_type in [ArchiveType.GZ, ArchiveType.BZ2, ArchiveType.XZ]:
                # 単一ファイル圧縮形式の場合
                if archive_path.stem.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                    virtual_path = Path(f"archive://{archive_path}|{archive_path.stem}")
                    files.append(virtual_path)
                    logger.debug(get_log_text("file_handler_found_compressed_image", archive_type=ArchiveInfo.get_display_name(archive_type), filename=archive_path.stem))
            elif archive_type == ArchiveType.PDF:
                for name in list_pdf_entries(str(archive_path)):
                    virtual_path = Path(f"archive://{archive_path}|{name}")
                    files.append(virtual_path)
                    logger.debug(get_log_text("file_handler_found_page_in_pdf", name=name))
        except Exception as e:
            logger.error(get_log_text("debug_error_expanding_archive", archive_path=archive_path, error=e))
        # 自然順序でソート
        files.sort(key=natural_sort_key)
        logger.info(get_log_text("debug_expanded_images_from_archive", archive_path=archive_path, image_count=len(files)))
        return files
    def _open_current_file(self) -> bool:
        """現在のファイルを開く（画像の読み込みはget_current_image()で行う）"""
        logger.info(get_log_text("debug_open_current_file_called", current_index=self.current_index, total_files=len(self.current_files)))
        if not self.current_files:
            logger.warning(get_log_text("debug_no_files_to_open"))
            return False
        file = self.current_files[self.current_index]
        logger.info(get_log_text("file_handler_opening_file", file=file))
        logger.info(get_log_text("debug_open_current_file_target", file=file, index=self.current_index))
        logger.info(get_log_text("file_handler_current_archive_info", current_archive=self.current_archive))
        
        # 仮想パスの処理（画像読み込みはget_current_image()で行う）
        file_str = str(file)
        if VirtualPathHandler.is_virtual_path(file_str) or file_str.startswith("archive://") or file_str.startswith("archive:\\"):
            logger.info(get_log_text("debug_processing_virtual_archive_path", file=file))
            # 仮想パスの場合はTrueを返す（画像読み込みはget_current_image()で行う）
            return True
        
        # str型ならPathに変換
        file_path = Path(file) if isinstance(file, str) else file
        logger.info(get_log_text("file_handler_file_path_info", file_path=file_path, suffix=file_path.suffix))
        
        if self._resolve_handler(file_path).is_skipped:
            logger.warning(get_log_text("file_handler_unsupported_file_type", suffix=file_path.suffix))
            return False

        # 圧縮ファイルの処理
        if self._is_handled_archive(file_path):
            # アーカイブ設定をチェック
            if not self.is_archive_supported(file_path):
                logger.warning(get_log_text("debug_archive_not_supported_by_settings_in_open_current_file", file_path=file_path))
                return False
            logger.info(get_log_text("file_handler_opening_as_archive", file_path=file_path))
            return self._open_archive(file_path)
        
        # 画像ファイルの処理（仮想的なPathは除外）
        elif ((file_path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS or self._is_plugin_image(file_path)) and
              not str(file_path).startswith("archive://") and
              not str(file_path).startswith("archive:\\")):
            logger.info(get_log_text("file_handler_opening_as_image", file_path=file_path))
            # 画像ファイルの場合はTrueを返す（画像読み込みはget_current_image()で行う）
            # プリフェッチを開始（非同期）
            self._prefetch_around(self.current_index)
            logger.info(get_log_text("debug_image_file_prefetch_started", file_path=file_path))
            return True
        
        logger.warning(get_log_text("file_handler_unsupported_file_type", suffix=file_path.suffix))
        return False
    def _open_archive(self, file: Path) -> bool:
        """アーカイブファイルを開く"""
        try:
            decision = self._resolve_handler(file)
            if decision.plugin and decision.is_archive:
                archive_files = self._expand_archive(file)
                self.current_archive_path = file
                self.current_files = archive_files
                self.current_index = 0
                return True

            archive_type = ArchiveInfo.get_archive_type_by_path(str(file))
            if archive_type is None:
                logger.error(get_log_text("debug_unknown_archive_type", archive_path=file))
                return False

            internal_name = ArchiveInfo.get_internal_name(archive_type)
            archive_files = []
            
            # 設定に応じてファイルハンドルの管理方法を決定
            should_keep_handles = self._should_keep_archive_handles()
            logger.info(get_log_text("debug_archive_handle_management", 
                                   archive_path=file, keep_handles=should_keep_handles))

            if archive_type in PASSWORD_ARCHIVE_TYPES:
                if not self._ensure_archive_unlocked(str(file)):
                    return False

            if should_keep_handles:
                # 従来通りファイルハンドルを保持
                if archive_type in (ArchiveType.ZIP, ArchiveType.CBZ):
                    self.current_archive = open_zip(file)
                    apply_zip_password(self.current_archive, str(file))
                    for name in self.current_archive.namelist():
                        decoded_name = self._decode_zip_filename(name)
                        if Path(decoded_name).suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                            virtual_path = f"archive://{file}|{decoded_name}"
                            archive_files.append(virtual_path)
                    logger.info(get_log_text("file_handler_opened_zip_archive", file=file, count=len(archive_files)))
                elif archive_type in [ArchiveType.TAR, ArchiveType.TAR_GZ, ArchiveType.TAR_BZ2, ArchiveType.TAR_XZ]:
                    self.current_archive = tarfile.open(file)
                    for name in self.current_archive.getnames():
                        decoded_name = self._decode_archive_filename(name, internal_name)
                        if Path(decoded_name).suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                            virtual_path = f"archive://{file}|{decoded_name}"
                            archive_files.append(virtual_path)
                    logger.info(get_log_text("file_handler_opened_tar_archive", file=file, count=len(archive_files)))
                elif archive_type == ArchiveType.GZ:
                    self.current_archive = gzip.open(file)
                    if file.stem.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                        virtual_path = f"archive://{file}|{file.stem}"
                        archive_files = [virtual_path]
                        logger.info(get_log_text("file_handler_opened_gzip_archive", file=file))
                    else:
                        archive_files = []
                elif archive_type == ArchiveType.BZ2:
                    self.current_archive = bz2.open(file)
                    if file.stem.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                        virtual_path = f"archive://{file}|{file.stem}"
                        archive_files = [virtual_path]
                        logger.info(get_log_text("file_handler_opened_bzip2_archive", file=file))
                    else:
                        archive_files = []
                elif archive_type == ArchiveType.XZ:
                    self.current_archive = lzma.open(file)
                    if file.stem.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS:
                        virtual_path = f"archive://{file}|{file.stem}"
                        archive_files = [virtual_path]
                        logger.info(get_log_text("file_handler_opened_xz_archive", file=file))
                    else:
                        archive_files = []
                elif archive_type == ArchiveType.PDF:
                    archive_files = self._expand_archive(file)
                    logger.info(get_log_text("file_handler_opened_pdf_archive", file=file, count=len(archive_files)))
                else:
                    # 7zやRARは都度開閉のため、ここでは処理しない
                    archive_files = self._expand_archive(file)
            else:
                # 新しい方式：ファイルハンドルを保持せず、必要時に開く
                logger.info(get_log_text("debug_archive_no_handle_mode", archive_path=file))
                # current_archiveは使用せず、expand_archiveでリストのみ取得
                archive_files = self._expand_archive(file)

            self.current_archive_path = file
            self.current_files = archive_files
            self.current_index = 0
            return True
        except Exception as e:
            logger.error(get_log_text("file_handler_failed_to_open_archive", error=e))
            return False
    def get_current_image(self) -> Optional[Image.Image]:
        """現在の画像を取得（同期的に読み込む）"""
        return self.get_image_at(self.current_index)

    def get_image_at(self, index: int) -> Optional[Image.Image]:
        """指定インデックスの画像を取得（同期的に読み込む）"""
        import time
        start_time = time.time()
        logger.debug(get_log_text("debug_get_current_image_called", current_index=index, total_files=len(self.current_files)))
        
        if not self.current_files:
            logger.warning(get_log_text("debug_no_files_loaded"))
            return None
        if index < 0 or index >= len(self.current_files):
            logger.warning(get_log_text("debug_no_files_loaded"))
            return None
        
        file = self.current_files[index]
        file_str = str(file)
        logger.debug(get_log_text("debug_get_current_image_target", file=file, index=index))
        
        # キャッシュキーを生成
        cache_key = None
        is_virtual_path = False
        
        # 仮想パスの処理
        if VirtualPathHandler.is_virtual_path(file_str) or file_str.startswith("archive://") or file_str.startswith("archive:\\"):
            is_virtual_path = True
            logger.info(get_log_text("debug_processing_virtual_archive_path_in_get_current_image", file=file))
            result = VirtualPathHandler.parse_virtual_path(file_str)
            if result:
                archive_path, filename = result
                logger.info(get_log_text("file_handler_archive_path_filename", archive_path=archive_path, filename=filename))
                normalized_archive_path = str(Path(archive_path).resolve())
                cache_key = f"{normalized_archive_path}|{filename}"
            else:
                logger.error(get_log_text("debug_invalid_virtual_archive_path_format", file=file))
                return None
        else:
            # 通常のファイルパスの処理
            cache_key = str(Path(file).resolve())
        
        if not cache_key:
            logger.error(get_log_text("debug_failed_to_generate_cache_key", file=file))
            return None
        
        logger.info(get_log_text("file_handler_current_image_info", file=file, cache_key=cache_key))
        logger.debug(get_log_text("debug_get_current_image_checking_cache", cache_key=cache_key, cache_size=len(self.image_cache)))
        
        # キャッシュをチェック
        if cache_key in self.image_cache:
            logger.debug(get_log_text("debug_image_found_in_cache", cache_key=cache_key))
            logger.debug(get_log_text("debug_get_current_image_cache_hit", cache_key=cache_key))
            elapsed = time.time() - start_time
            logger.debug(get_log_text("debug_get_current_image_completed", cache_key=cache_key, elapsed_ms=elapsed * 1000))
            return self.image_cache[cache_key]
        
        # キャッシュにない場合は同期的に読み込む
        logger.info(get_log_text("file_handler_getting_image_directly", file=file))
        logger.debug(get_log_text("debug_get_current_image_cache_miss_loading_sync", cache_key=cache_key))
        
        try:
            if is_virtual_path:
                # 仮想パスから画像を読み込む（セッションチェックをスキップ）
                image = self._get_image_from_archive_sync(file_str)
            elif self._is_plugin_image(file):
                image = self._load_plugin_image(file)
            else:
                # 通常のファイルから画像を読み込む
                image = Image.open(Path(file))
                image.load()  # ファイルハンドルを閉じるために画像データをメモリに読み込む
            
            if not image:
                logger.error(get_log_text("debug_failed_to_load_image", file=file))
                return None
            
            # 画像の最適化（大きな画像の場合）
            image = self._optimize_image(image)
            
            # キャッシュに保存
            estimated_size = self._estimate_image_size(image)
            if estimated_size <= self.cache_limit:
                self.image_cache[cache_key] = image
                self.cache_size += estimated_size
                self._evict_cache()
                logger.info(get_log_text("debug_image_loaded_and_cached", cache_key=cache_key))
            else:
                logger.warning(get_log_text("file_handler_cache_too_large", size=estimated_size))
                # キャッシュに保存できない場合でも画像は返す
            
            elapsed = time.time() - start_time
            logger.debug(get_log_text("debug_get_current_image_completed", cache_key=cache_key, elapsed_ms=elapsed * 1000))
            return image
            
        except Exception as e:
            logger.error(get_log_text("debug_failed_to_load_image", file=file, error=str(e)))
            return None
    def _load_image(self, file: str, cache_key: str, is_current: bool = False, session_id: int = None):
        """画像を非同期で読み込み、キャッシュに保存"""
        claimed_prefetch = False
        try:
            # セッションIDが指定されていない場合は現在のセッションIDを取得
            if session_id is None:
                session_id = self._get_current_session_id()
            
            # セッションが無効になっていないかチェック
            if not self._is_session_active(session_id):
                logger.info(get_log_text("debug_load_image_session_cancelled", file=file, session_id=session_id))
                return
            
            logger.info(get_log_text("debug_load_image_started", file=file, cache_key=cache_key, is_current=is_current, session_id=session_id))
            if is_current:
                with self._loading_lock:
                    logger.info(get_log_text("file_handler_setting_current_loading", cache_key=cache_key))
                    self._current_loading = cache_key
            else:
                # pending → in_progress へ遷移。キャッシュ済み・処理中なら読み込みしない
                skip_reason = None
                with self._prefetch_lock:
                    self._prefetch_pending.discard(cache_key)
                    if cache_key in self.image_cache:
                        skip_reason = "cached"
                    elif cache_key in self._prefetch_in_progress:
                        skip_reason = "prefetching"
                    else:
                        self._prefetch_in_progress.add(cache_key)
                        claimed_prefetch = True
                if skip_reason == "cached":
                    logger.info(get_log_text("file_handler_skipping_cached", file=file, session_id=session_id))
                    return
                if skip_reason == "prefetching":
                    logger.info(get_log_text("file_handler_already_prefetching", cache_key=cache_key))
                    return
            
            # 画像読み込み前にもう一度セッションチェック
            if not self._is_session_active(session_id):
                logger.info(get_log_text("debug_load_image_session_cancelled_before_load", file=file, session_id=session_id))
                return
            
            # キュー投入後に別経路でキャッシュされた場合はZIP読み込み・デコードをスキップ
            if cache_key in self.image_cache:
                logger.info(get_log_text("file_handler_skipping_cached", file=file, session_id=session_id))
                return
            
            # 仮想的なパスの処理
            if VirtualPathHandler.is_virtual_path(file):
                logger.info(get_log_text("file_handler_loading_from_archive", file=file))
                image = self._get_image_from_archive(file, session_id)
            elif self._is_plugin_image(file):
                logger.info(get_log_text("file_handler_loading_from_plugin", file=file))
                image = self._load_plugin_image(file)
            else:
                logger.info(get_log_text("file_handler_loading_from_local", file=file))
                image = Image.open(Path(file))
                # ファイルハンドルを閉じるために画像データをメモリに読み込む
                image.load()
            
            # 画像読み込み後にセッションチェック
            if not self._is_session_active(session_id):
                logger.info(get_log_text("debug_load_image_session_cancelled_after_load", file=file, session_id=session_id))
                if image:
                    image.close()
                return
            
            if image:
                # 画像の最適化（大きな画像の場合）
                image = self._optimize_image(image)
                
                # 画像のメモリ使用量を推定
                estimated_size = self._estimate_image_size(image)
                # キャッシュサイズをチェック
                if estimated_size > self.cache_limit:
                    logger.warning(get_log_text("file_handler_cache_too_large", size=estimated_size))
                    image.close()
                    return
                # キャッシュに追加
                self.image_cache[cache_key] = image
                self.cache_size += estimated_size
                # キャッシュサイズが上限を超えたら削除
                self._evict_cache()
                logger.info(get_log_text("debug_image_loaded_and_cached", cache_key=cache_key, estimated_size=estimated_size, session_id=session_id))
                # コールバックを呼び出し（メインスレッドで実行）
                if self._on_image_loaded and self._is_session_active(session_id):
                    try:
                        # QTimer.singleShotを使用してメインスレッドで実行
                        from PySide6.QtCore import QTimer
                        QTimer.singleShot(0, lambda: self._on_image_loaded(file, image))
                    except Exception as e:
                        logger.error(get_log_text("debug_failed_to_call_image_loaded_callback", error=e))
            else:
                logger.error(get_log_text("debug_failed_to_load_image", file=file))
        except Exception as e:
            logger.error(get_log_text("debug_failed_to_load_image_with_error", file=file, error=e))
        finally:
            with self._loading_lock:
                if is_current:
                    logger.info(get_log_text("file_handler_clearing_current_loading", cache_key=cache_key))
                    self._current_loading = None
            if not is_current:
                with self._prefetch_lock:
                    self._prefetch_pending.discard(cache_key)
                    if claimed_prefetch:
                        self._prefetch_in_progress.discard(cache_key)
    def _prefetch_around(self, index, session_id=None):
        # セッションIDが指定されていない場合は現在のセッションIDを取得
        if session_id is None:
            session_id = self._get_current_session_id()
        
        # セッションが無効になっていないかチェック
        if not self._is_session_active(session_id):
            logger.info(get_log_text("debug_prefetch_around_session_cancelled", index=index, session_id=session_id))
            return
        
        # プリフェッチは常に動作させる（ファイルハンドル非保持モードでも都度開閉で対応）
        should_keep_handles = self._should_keep_archive_handles()
        logger.info(get_log_text("debug_prefetch_around_started_handle_mode", 
                                index=index, keep_handles=should_keep_handles, session_id=session_id))
            
        logger.info(get_log_text("debug_prefetch_around_started", index=index, session_id=session_id))
        n = 3
        if self.config and hasattr(self.config, 'cache') and isinstance(self.config.cache, dict):
            n = int(self.config.cache.get("prefetch_pages", 3))
        # 先読みするページのインデックスを優先順位付きで収集
        # 次のページを最優先（優先度1）、その次を優先度2、前のページは優先度3以降
        prefetch_indices = []
        # 次のページを最優先
        if 0 <= index + 1 < len(self.current_files):
            prefetch_indices.append((index + 1, 1))  # 次のページを最優先
        # その他の次のページ
        for i in range(2, n+1):
            if 0 <= index + i < len(self.current_files):
                prefetch_indices.append((index + i, i))  # 優先度を2から開始
        # 前のページ（優先度を下げる）
        for i in range(1, n+1):
            if 0 <= index - i < len(self.current_files):
                prefetch_indices.append((index - i, n + i))  # 前のページは優先度を下げる
        # 優先順位でソート（現在のページに近い順、次のページを優先）
        prefetch_indices.sort(key=lambda x: x[1])
        logger.info(get_log_text("file_handler_prefetch_indices", prefetch_indices=prefetch_indices, session_id=session_id))
        # 各ページを非同期で先読み
        for idx, priority in prefetch_indices:
            # セッションチェック（処理中にキャンセルされた場合）
            if not self._is_session_active(session_id):
                logger.info(get_log_text("debug_prefetch_around_cancelled_during_processing", index=index, session_id=session_id))
                return
                
            file = self.current_files[idx]
            # 仮想的なパスの処理
            if VirtualPathHandler.is_virtual_path(file):
                result = VirtualPathHandler.parse_virtual_path(file)
                if result:
                    archive_path, filename = result
                    # パスを正規化してキャッシュキーとして使用
                    normalized_archive_path = str(Path(archive_path).resolve())
                    cache_key = f"{normalized_archive_path}|{filename}"
                else:
                    logger.error(get_log_text("debug_invalid_virtual_archive_path_format", file=file))
                    continue
            else:
                # 通常ファイルも正規化
                cache_key = str(Path(file).resolve())
            should_enqueue = False
            skip_reason = None
            with self._prefetch_lock:
                if cache_key in self.image_cache:
                    skip_reason = "cached"
                elif cache_key in self._prefetch_pending or cache_key in self._prefetch_in_progress:
                    skip_reason = "prefetching"
                else:
                    self._prefetch_pending.add(cache_key)
                    should_enqueue = True
            if skip_reason == "cached":
                logger.info(get_log_text("file_handler_skipping_cached", file=file, session_id=session_id))
            elif skip_reason == "prefetching":
                logger.info(get_log_text("file_handler_already_prefetching", cache_key=cache_key))
            elif should_enqueue:
                logger.info(get_log_text("file_handler_adding_prefetch_queue", file=file, priority=priority, session_id=session_id))
                self._image_queue.put((str(file), cache_key, False, session_id))
    def _estimate_image_size(self, image: Image.Image) -> int:
        # PIL.Imageのメモリ使用量を推定
        if hasattr(image, 'nbytes'):
            return image.nbytes
        mode_to_bpp = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32, "CMYK": 32}
        bpp = mode_to_bpp.get(image.mode, 24)
        return image.width * image.height * bpp // 8
    
    def _optimize_image(self, image: Image.Image) -> Image.Image:
        """大きな画像を最適化（リサイズ）してメモリ使用量を削減"""
        if not self.config:
            return image
        
        # 最適化が無効な場合はそのまま返す
        if not self.config.cache.get("optimize_large_images", True):
            return image
        
        # 閾値を取得
        optimize_threshold_str = self.config.cache.get("optimize_threshold", "50MB")
        try:
            optimize_threshold = humanfriendly.parse_size(optimize_threshold_str)
        except Exception:
            # パースに失敗した場合はデフォルト値（50MB）
            optimize_threshold = 50 * 1024 * 1024
        
        # 現在の画像サイズを推定
        current_size = self._estimate_image_size(image)
        
        # 閾値を超えていない場合はそのまま返す
        if current_size <= optimize_threshold:
            return image
        
        # 最大解像度を取得
        max_resolution = self.config.cache.get("optimize_max_resolution", 4000)
        
        # 現在の解像度を取得
        width, height = image.size
        
        # 最大解像度を超えている場合のみリサイズ
        if width <= max_resolution and height <= max_resolution:
            return image
        
        # 閾値の2倍以下の場合は最適化をスキップ（表示速度を優先）
        # 大きな画像のみ最適化することで、通常の画像の読み込み速度を向上
        if current_size <= optimize_threshold * 2:
            logger.info(get_log_text("debug_optimization_skipped_for_speed", 
                                    current_size=current_size, threshold=optimize_threshold))
            return image
        
        # アスペクト比を保持してリサイズ
        if width > height:
            new_width = max_resolution
            new_height = int(height * (max_resolution / width))
        else:
            new_height = max_resolution
            new_width = int(width * (max_resolution / height))
        
        logger.info(get_log_text("debug_optimizing_image", 
                                original_size=f"{width}x{height}", 
                                new_size=f"{new_width}x{new_height}",
                                original_memory=current_size,
                                threshold=optimize_threshold))
        
        # リサイズ実行（BICUBICを使用：LANCZOSより高速で品質も良好）
        optimized_image = image.resize((new_width, new_height), Image.Resampling.BICUBIC)
        
        # 元の画像を閉じる
        image.close()
        
        # 最適化後のサイズをログ出力
        optimized_size = self._estimate_image_size(optimized_image)
        logger.info(get_log_text("debug_image_optimized", 
                                original_memory=current_size,
                                optimized_memory=optimized_size,
                                reduction_percent=((current_size - optimized_size) / current_size * 100) if current_size > 0 else 0))
        
        return optimized_image
    def _evict_cache(self):
        # キャッシュサイズが上限を超えたら現在ページからの距離を考慮して削除
        initial_cache_size = self.cache_size
        evicted_count = 0
        
        while self.cache_size > self.cache_limit and self.image_cache:
            # 現在ページからの距離を考慮して最も遠いエントリを見つける
            farthest_key = self._find_farthest_cache_key()
            if farthest_key is None:
                # フォールバック：LRU（最初のエントリ）を削除
                farthest_key = next(iter(self.image_cache))
                logger.warning(get_log_text("debug_cache_eviction_fallback_lru", cache_key=farthest_key))
            
            farthest_image = self.image_cache.pop(farthest_key)
            # 画像のメモリ使用量を推定して減算
            estimated_size = self._estimate_image_size(farthest_image)
            self.cache_size -= estimated_size
            evicted_count += 1
            logger.info(get_log_text("debug_cache_evicted_by_distance", 
                                   cache_key=farthest_key, 
                                   estimated_size=estimated_size,
                                   remaining_cache_size=self.cache_size))
        
        if evicted_count > 0:
            logger.warning(get_log_text("debug_cache_eviction_summary", 
                                      evicted_count=evicted_count,
                                      initial_size=initial_cache_size,
                                      final_size=self.cache_size,
                                      cache_limit=self.cache_limit))
    
    def _find_farthest_cache_key(self) -> Optional[str]:
        """現在ページから最も遠いキャッシュキーを見つける"""
        if not self.current_files or self.current_index < 0:
            return None
        
        max_distance = -1
        farthest_key = None
        
        for cache_key in self.image_cache.keys():
            distance = self._calculate_page_distance(cache_key)
            if distance > max_distance:
                max_distance = distance
                farthest_key = cache_key
                logger.debug(get_log_text("debug_cache_distance_calculation", 
                                        cache_key=cache_key, 
                                        distance=distance,
                                        current_index=self.current_index))
        
        if farthest_key:
            logger.info(get_log_text("debug_cache_farthest_found", 
                                   cache_key=farthest_key, 
                                   distance=max_distance,
                                   current_index=self.current_index))
        
        return farthest_key
    
    def _calculate_page_distance(self, cache_key: str) -> int:
        """キャッシュキーから現在ページまでの距離を計算"""
        try:
            # キャッシュキーに対応するファイルのインデックスを検索
            target_index = self._find_file_index_by_cache_key(cache_key)
            if target_index is None:
                return 999999  # 見つからない場合は非常に大きな距離
            
            # 現在ページからの距離を計算
            distance = abs(target_index - self.current_index)
            return distance
            
        except Exception as e:
            logger.debug(get_log_text("debug_cache_distance_calculation_error", 
                                    cache_key=cache_key, error=e))
            return 999999  # エラーの場合は非常に大きな距離
    
    def _find_file_index_by_cache_key(self, cache_key: str) -> Optional[int]:
        """キャッシュキーに対応するファイルのインデックスを検索"""
        try:
            # アーカイブファイルの場合（cache_key形式: "path|filename"）
            if '|' in cache_key:
                archive_path, filename = cache_key.split('|', 1)
                archive_path = archive_path.replace('\\', '/')
                
                # current_filesから対応する仮想パスを探す
                for i, file_path in enumerate(self.current_files):
                    if VirtualPathHandler.is_virtual_path(str(file_path)):
                        result = VirtualPathHandler.parse_virtual_path(str(file_path))
                        if result:
                            file_archive_path, file_filename = result
                            file_archive_path = str(file_archive_path).replace('\\', '/')
                            # パスを正規化して比較
                            normalized_file_archive = str(Path(file_archive_path).resolve()).replace('\\', '/')
                            normalized_cache_archive = str(Path(archive_path).resolve()).replace('\\', '/')
                            
                            if (normalized_file_archive == normalized_cache_archive and 
                                file_filename == filename):
                                return i
            else:
                # 通常ファイルの場合
                normalized_cache_path = str(Path(cache_key).resolve())
                
                for i, file_path in enumerate(self.current_files):
                    if not VirtualPathHandler.is_virtual_path(str(file_path)):
                        normalized_file_path = str(Path(file_path).resolve())
                        if normalized_file_path == normalized_cache_path:
                            return i
            
            return None
            
        except Exception as e:
            logger.debug(get_log_text("debug_find_file_index_error", 
                                    cache_key=cache_key, error=e))
            return None
    def _get_image_from_archive_sync(self, file: str) -> Optional[Image.Image]:
        """アーカイブから画像を同期的に取得（セッションチェックなし）"""
        try:
            # 仮想的なパスの処理
            if not VirtualPathHandler.is_virtual_path(file):
                logger.error(get_log_text("debug_invalid_virtual_archive_path_format", file=file))
                return None
            
            result = VirtualPathHandler.parse_virtual_path(file)
            if not result:
                logger.error(get_log_text("debug_invalid_virtual_archive_path_format", file=file))
                return None
            
            archive_path, filename = result
            # Pathオブジェクトを文字列に変換し、スラッシュに統一
            archive_path_str = str(archive_path).replace('\\', '/')
            logger.info(get_log_text("file_handler_archive_path_filename", archive_path=archive_path, filename=filename))
            logger.debug(get_log_text("file_handler_get_image_debug", file=file, archive_path=archive_path, archive_path_str=archive_path_str))
            
            # アーカイブファイルの存在チェック
            if not Path(archive_path_str).exists():
                error_msg = get_log_text("debug_archive_file_not_found", archive_path=archive_path_str)
                logger.error(error_msg)
                self._notify_error("file_not_found", error_msg, archive_path_str)
                return None
            
            # アーカイブの種類に応じて処理
            decision = self._resolve_handler(archive_path_str)
            if decision.plugin and decision.is_archive:
                return self._read_plugin_archive_entry(archive_path_str, filename, decision.plugin)

            archive_type = ArchiveInfo.get_archive_type_by_path(archive_path_str)
            if archive_type is None:
                error_msg = get_log_text("debug_unknown_archive_type", archive_path=archive_path_str)
                logger.error(error_msg)
                self._notify_error("unknown_format", error_msg, archive_path_str)
                return None
            
            internal_name = ArchiveInfo.get_internal_name(archive_type)
            
            # 各アーカイブタイプの処理（セッションチェックをスキップ）
            try:
                if archive_type in (ArchiveType.ZIP, ArchiveType.CBZ):
                    return self._process_zip_archive_sync(archive_path_str, filename)
                elif archive_type == ArchiveType.SEVEN_ZIP:
                    return self._process_7z_archive_sync(archive_path_str, filename, internal_name)
                elif archive_type in (ArchiveType.RAR, ArchiveType.CBR):
                    return self._process_rar_archive_sync(archive_path_str, filename, internal_name)
                elif archive_type in [ArchiveType.TAR, ArchiveType.TAR_GZ, ArchiveType.TAR_BZ2, ArchiveType.TAR_XZ]:
                    return self._process_tar_archive_sync(archive_path_str, filename, internal_name)
                elif archive_type == ArchiveType.PDF:
                    return load_pdf_image(archive_path_str, filename)
                else:
                    error_msg = get_log_text("file_handler_unsupported_archive_format", archive_type=archive_type)
                    logger.error(error_msg)
                    self._notify_error("unsupported_format", error_msg, archive_path_str)
                    return None
            except FileNotFoundError:
                error_msg = get_log_text("debug_archive_file_moved_or_deleted", archive_path=archive_path_str)
                logger.error(error_msg)
                self._notify_error("file_moved", error_msg, archive_path_str)
                return None
            except PermissionError:
                error_msg = get_log_text("debug_archive_permission_denied", archive_path=archive_path_str)
                logger.error(error_msg)
                self._notify_error("permission_denied", error_msg, archive_path_str)
                return None
            except Exception as archive_error:
                error_msg = get_log_text("debug_archive_processing_failed", error=archive_error, archive_path=archive_path_str)
                logger.error(error_msg)
                self._notify_error("processing_failed", error_msg, archive_path_str)
                return None
        except Exception as e:
            error_msg = get_log_text("debug_failed_to_get_image_from_archive", error=e)
            logger.error(error_msg)
            self._notify_error("unknown_error", error_msg, "")
            return None
    
    def _get_image_from_archive(self, file: str, session_id: int = None) -> Optional[Image.Image]:
        """アーカイブから画像を取得（非同期用、セッションチェックあり）"""
        try:
            # セッションIDが指定されていない場合は現在のセッションIDを取得
            if session_id is None:
                session_id = self._get_current_session_id()
            
            # セッションが無効になっていないかチェック
            if not self._is_session_active(session_id):
                logger.info(get_log_text("debug_get_image_from_archive_session_cancelled", file=file, session_id=session_id))
                return None
            
            # 仮想的なパスの処理
            if VirtualPathHandler.is_virtual_path(file):
                result = VirtualPathHandler.parse_virtual_path(file)
                if result:
                    archive_path, filename = result
                    # Pathオブジェクトを文字列に変換し、スラッシュに統一
                    archive_path_str = str(archive_path).replace('\\', '/')
                    logger.info(get_log_text("file_handler_archive_path_filename", archive_path=archive_path, filename=filename))
                    logger.debug(get_log_text("file_handler_get_image_debug", file=file, archive_path=archive_path, archive_path_str=archive_path_str))
                    
                    # セッションチェック
                    if not self._is_session_active(session_id):
                        logger.info(get_log_text("debug_get_image_from_archive_session_cancelled_before_check", file=file, session_id=session_id))
                        return None
                    
                    # アーカイブファイルの存在チェック
                    if not Path(archive_path_str).exists():
                        error_msg = get_log_text("debug_archive_file_not_found", archive_path=archive_path_str)
                        logger.error(error_msg)
                        self._notify_error("file_not_found", error_msg, archive_path_str)
                        return None
                    
                    # アーカイブの種類に応じて処理
                    decision = self._resolve_handler(archive_path_str)
                    if decision.plugin and decision.is_archive:
                        return self._read_plugin_archive_entry(archive_path_str, filename, decision.plugin)

                    archive_type = ArchiveInfo.get_archive_type_by_path(archive_path_str)
                    if archive_type is None:
                        error_msg = get_log_text("debug_unknown_archive_type", archive_path=archive_path_str)
                        logger.error(error_msg)
                        self._notify_error("unknown_format", error_msg, archive_path_str)
                        return None
                    
                    internal_name = ArchiveInfo.get_internal_name(archive_type)
                    
                    # 各アーカイブタイプの処理（セッションIDを渡す）
                    try:
                        if archive_type in (ArchiveType.ZIP, ArchiveType.CBZ):
                            return self._process_zip_archive(archive_path_str, filename, session_id)
                        elif archive_type == ArchiveType.SEVEN_ZIP:
                            return self._process_7z_archive(archive_path_str, filename, internal_name, session_id)
                        elif archive_type in (ArchiveType.RAR, ArchiveType.CBR):
                            return self._process_rar_archive(archive_path_str, filename, internal_name, session_id)
                        elif archive_type in [ArchiveType.TAR, ArchiveType.TAR_GZ, ArchiveType.TAR_BZ2, ArchiveType.TAR_XZ]:
                            return self._process_tar_archive(archive_path_str, filename, internal_name, session_id)
                        elif archive_type == ArchiveType.PDF:
                            return load_pdf_image(archive_path_str, filename)
                        else:
                            error_msg = get_log_text("file_handler_unsupported_archive_format", archive_type=archive_type)
                            logger.error(error_msg)
                            self._notify_error("unsupported_format", error_msg, archive_path_str)
                            return None
                    except FileNotFoundError:
                        error_msg = get_log_text("debug_archive_file_moved_or_deleted", archive_path=archive_path_str)
                        logger.error(error_msg)
                        self._notify_error("file_moved", error_msg, archive_path_str)
                        return None
                    except PermissionError:
                        error_msg = get_log_text("debug_archive_permission_denied", archive_path=archive_path_str)
                        logger.error(error_msg)
                        self._notify_error("permission_denied", error_msg, archive_path_str)
                        return None
                    except Exception as archive_error:
                        error_msg = get_log_text("debug_archive_processing_failed", error=archive_error, archive_path=archive_path_str)
                        logger.error(error_msg)
                        self._notify_error("processing_failed", error_msg, archive_path_str)
                        return None
                else:
                    error_msg = get_log_text("debug_invalid_virtual_archive_path_format", file=file)
                    logger.error(error_msg)
                    self._notify_error("invalid_path", error_msg, "")
                    return None
            else:
                # 従来のアーカイブ処理（ファイルハンドル保持時のみ）
                if not self._should_keep_archive_handles():
                    logger.warning(get_log_text("debug_legacy_archive_mode_disabled"))
                    return None
                    
                if not self.current_archive:
                    logger.error(get_log_text("file_handler_no_archive_currently_open"))
                    return None
                with self.current_archive.open(file) as image_file:
                    image = Image.open(image_file)
                    image.load()
                    return image
        except Exception as e:
            error_msg = get_log_text("debug_failed_to_get_image_from_archive", error=e)
            logger.error(error_msg)
            self._notify_error("unknown_error", error_msg, "")
            return None
    
    def next_file(self, step: int = 1) -> bool:
        """次のファイルに移動"""
        logger.info(get_log_text("debug_next_file_called", current_index=self.current_index, total_files=len(self.current_files)))
        target_index = self.current_index + step
        if target_index < len(self.current_files):
            logger.info(get_log_text("debug_next_file_target_index", target_index=target_index, target_file=self.current_files[target_index] if target_index < len(self.current_files) else "N/A"))
            # ファイルアクセス可能性をチェック
            accessible = self._check_file_accessibility(target_index)
            logger.info(get_log_text("debug_next_file_accessibility_check", target_index=target_index, accessible=accessible))
            if not accessible:
                logger.warning(get_log_text("debug_next_file_not_accessible", target_index=target_index))
                return False
            logger.info(get_log_text("debug_next_file_updating_index", old_index=self.current_index, new_index=target_index))
            self.current_index = target_index
            logger.info(get_log_text("debug_next_file_calling_open_current_file", target_index=target_index))
            result = self._open_current_file()
            logger.info(get_log_text("debug_next_file_open_result", result=result, target_index=target_index))
            return result
        logger.info(get_log_text("debug_next_file_at_end", current_index=self.current_index, total_files=len(self.current_files)))
        return False
    def prev_file(self, step: int = 1) -> bool:
        """前のファイルに移動"""
        if self.current_index > 0:
            target_index = max(0, self.current_index - step)
            # ファイルアクセス可能性をチェック
            accessible = self._check_file_accessibility(target_index)
            logger.info(get_log_text("debug_prev_file_accessibility_check", target_index=target_index, accessible=accessible))
            if not accessible:
                return False
            self.current_index = target_index
            return self._open_current_file()
        return False
    def get_current_archive_path(self) -> Optional[Path]:
        """現在開いているアーカイブファイルのパスを取得"""
        return self.current_archive_path
    def get_current_directory_files(self) -> List[Path]:
        """現在のファイルと同じディレクトリのファイル一覧を取得"""
        if not self.current_files:
            return []
        current_file = self.current_files[self.current_index]
        # 仮想的なパスの処理
        if VirtualPathHandler.is_virtual_path(current_file):
            current_dir = VirtualPathHandler.get_archive_parent_dir(current_file)
            if not current_dir:
                return []
        else:
            # 通常のファイルパスの処理
            if isinstance(current_file, str):
                current_file = Path(current_file)
            current_dir = current_file.parent
        
        # 設定に応じてディレクトリアクセス方式を決定
        should_keep_handles = self._should_keep_archive_handles()
        logger.debug(get_log_text("debug_directory_listing_handle_management", 
                                 directory=current_dir, keep_handles=should_keep_handles))
        
        try:
            if should_keep_handles:
                # 従来方式：Path.glob()を使用（ディレクトリハンドル保持）
                return sorted([
                    f for f in current_dir.glob('*')
                    if f.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS or
                       f.suffix.lower() in self.SUPPORTED_ARCHIVE_EXTENSIONS or
                       f.is_dir()
                ], key=natural_sort_key)
            else:
                # 新方式：os.listdir()を使用（ディレクトリハンドル即座解放）
                import os
                result = []
                try:
                    for name in os.listdir(str(current_dir)):
                        file_path = current_dir / name
                        # 軽量チェック
                        if (file_path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS or
                            file_path.suffix.lower() in self.SUPPORTED_ARCHIVE_EXTENSIONS or
                            self._is_likely_directory(file_path)):
                            result.append(file_path)
                except OSError as e:
                    logger.warning(get_log_text("debug_directory_listing_failed", directory=current_dir, error=e))
                    return []
                return sorted(result, key=natural_sort_key)
        except Exception as e:
            logger.error(get_log_text("debug_directory_listing_error", directory=current_dir, error=e))
            return []
    
    def _is_likely_directory(self, path: Path) -> bool:
        """ディレクトリかどうかを軽量チェック（is_dir()回避）"""
        try:
            # 拡張子がない場合はディレクトリの可能性が高い
            return path.suffix == ""
        except Exception:
            return False
    def get_comic_files_in_directory(self, directory: Path) -> List[Path]:
        """指定されたディレクトリ内のコミックファイル（ファイルとフォルダ）を自然順序でソートして取得"""
        comic_files = []
        
        # 設定に応じてディレクトリアクセス方式を決定
        should_keep_handles = self._should_keep_archive_handles()
        logger.debug(get_log_text("debug_comic_scan_handle_management", 
                                 directory=directory, keep_handles=should_keep_handles))
        
        try:
            if should_keep_handles:
                # 従来方式：Path.glob()を使用（ディレクトリハンドル保持）
                for file_path in directory.glob('*'):
                    if file_path.is_file():
                        # 画像ファイルまたはアーカイブファイル（コミック）をフィルタリング
                        if (file_path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS or 
                            ArchiveInfo.is_archive_file(str(file_path))):
                            # アーカイブファイルの場合、サポートされているかチェック
                            if ArchiveInfo.is_archive_file(str(file_path)):
                                if self.is_archive_supported(file_path):
                                    comic_files.append(file_path)
                            else:
                                comic_files.append(file_path)
                    elif file_path.is_dir():
                        # フォルダは無条件でコミック単位として扱う
                        comic_files.append(file_path)
            else:
                # 新方式：os.listdir()を使用（ディレクトリハンドル即座解放）
                import os
                try:
                    for name in os.listdir(str(directory)):
                        file_path = directory / name
                        # 軽量チェック
                        if (file_path.suffix.lower() in self.SUPPORTED_IMAGE_EXTENSIONS or 
                            ArchiveInfo.is_archive_file(str(file_path))):
                            # アーカイブファイルの場合、サポートされているかチェック
                            if ArchiveInfo.is_archive_file(str(file_path)):
                                if self.is_archive_supported(file_path):
                                    comic_files.append(file_path)
                            else:
                                comic_files.append(file_path)
                        elif self._is_likely_directory(file_path):
                            # フォルダは無条件でコミック単位として扱う
                            comic_files.append(file_path)
                except OSError as e:
                    logger.warning(get_log_text("debug_comic_scan_failed", directory=directory, error=e))
        except Exception as e:
            logger.error(get_log_text("file_handler_error_scanning_directory", directory=directory, error=e))
        
        # 自然順序でソート
        comic_files.sort(key=natural_sort_key)
        return comic_files
    def get_next_comic_file(self, current_path: Path) -> Optional[Path]:
        """現在のファイルの次のコミックファイルを取得"""
        try:
            # 現在のファイルが存在するディレクトリを取得
            if VirtualPathHandler.is_virtual_path(str(current_path)):
                current_dir = VirtualPathHandler.get_archive_parent_dir(str(current_path))
                if not current_dir:
                    return None
                # アーカイブファイルのパスを取得
                result = VirtualPathHandler.parse_virtual_path(str(current_path))
                if result:
                    archive_path, _ = result
                    current_path = archive_path
                else:
                    return None
            else:
                current_dir = current_path.parent

            # ディレクトリ内のコミックファイル一覧を取得
            comic_files = self.get_comic_files_in_directory(current_dir)
            
            if not comic_files:
                return None

            # 現在のファイルのインデックスを見つける
            try:
                current_index = comic_files.index(current_path)
                # 次のファイルのインデックス
                next_index = (current_index + 1) % len(comic_files)
                return comic_files[next_index] if next_index != current_index else None
            except ValueError:
                # 現在のファイルがリストにない場合、最初のファイルを返す
                return comic_files[0] if comic_files else None

        except Exception as e:
            logger.error(get_log_text("file_handler_error_getting_next_comic", current_path=current_path, error=e))
            return None
    def get_prev_comic_file(self, current_path: Path) -> Optional[Path]:
        """現在のファイルの前のコミックファイルを取得"""
        try:
            # 現在のファイルが存在するディレクトリを取得
            if VirtualPathHandler.is_virtual_path(str(current_path)):
                current_dir = VirtualPathHandler.get_archive_parent_dir(str(current_path))
                if not current_dir:
                    return None
                # アーカイブファイルのパスを取得
                result = VirtualPathHandler.parse_virtual_path(str(current_path))
                if result:
                    archive_path, _ = result
                    current_path = archive_path
                else:
                    return None
            else:
                current_dir = current_path.parent

            # ディレクトリ内のコミックファイル一覧を取得
            comic_files = self.get_comic_files_in_directory(current_dir)
            
            if not comic_files:
                return None

            # 現在のファイルのインデックスを見つける
            try:
                current_index = comic_files.index(current_path)
                # 前のファイルのインデックス
                prev_index = (current_index - 1) % len(comic_files)
                return comic_files[prev_index] if prev_index != current_index else None
            except ValueError:
                # 現在のファイルがリストにない場合、最後のファイルを返す
                return comic_files[-1] if comic_files else None

        except Exception as e:
            logger.error(get_log_text("file_handler_error_getting_prev_comic", current_path=current_path, error=e))
            return None
    def close(self):
        """リソースを解放"""
        if self.current_archive:
            try:
                self.current_archive.close()
                logger.info(get_log_text("debug_archive_handle_closed", archive_path=self.current_archive_path))
            except Exception as e:
                logger.warning(get_log_text("debug_archive_handle_close_failed", error=e))
            finally:
                self.current_archive = None
        
        # アーカイブメタデータキャッシュをクリア
        if hasattr(self, 'archive_metadata_cache'):
            self.archive_metadata_cache.clear()
            
        # 一時ディレクトリのクリーンアップ
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
            self.temp_dir = None
    def __del__(self):
        self._prefetch_queue.put((float('inf'), None))  # ワーカーを停止
        self._image_queue.put(None)
        self._executor.shutdown(wait=False)
    def set_on_error_occurred(self, callback):
        """
        エラー発生時に呼ばれるコールバックを登録する。
        callback: func(error_type: str, error_message: str, archive_path: str)
        """
        self._on_error_occurred = callback
    def set_on_image_loaded(self, callback):
        """
        画像取得完了時に呼ばれるコールバックを登録する。
        callback: func(file: str, image: PIL.Image)
        """
        self._on_image_loaded = callback

    def set_archive_password_provider(self, callback):
        """暗号化ファイルのパスワードをUIから取得するコールバック。callback(file_path) -> bool"""
        self._archive_password_provider = callback

    def set_pdf_password_provider(self, callback):
        self.set_archive_password_provider(callback)

    def _ensure_archive_unlocked(self, file_path: str) -> bool:
        if get_session_password(file_path) is not None:
            return True
        if self._archive_password_provider:
            return bool(self._archive_password_provider(file_path))
        from ez_co.handlers.archive_password import is_encrypted, set_session_password, try_unlock
        if not is_encrypted(file_path):
            set_session_password(file_path, "")
            return True
        if try_unlock(file_path, ""):
            set_session_password(file_path, "")
            return True
        return False

    def _unlock_pdf(self, pdf_path: str) -> bool:
        return self._ensure_archive_unlocked(pdf_path)
    def _start_prefetch_thread(self):
        """プリフェッチスレッドを開始"""
        if self._prefetch_thread is None or not self._prefetch_thread.is_alive():
            self._prefetch_running = True
            self._prefetch_thread = threading.Thread(target=self._prefetch_worker, daemon=True)
            self._prefetch_thread.start()
    def _prefetch_worker(self):
        """プリフェッチワーカースレッド"""
        while self._prefetch_running:
            try:
                file = self._prefetch_queue.get(timeout=0.1)
                if file is None:
                    continue
                cache_key = f"archive:{file}" if self.current_archive else file
                # プリフェッチ中のファイルをチェック
                with self._prefetch_lock:
                    if cache_key in self._prefetch_in_progress:
                        continue
                    self._prefetch_in_progress.add(cache_key)
                try:
                    self._load_image(file, cache_key)
                finally:
                    with self._prefetch_lock:
                        self._prefetch_in_progress.discard(cache_key)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(get_log_text("file_handler_prefetch_worker_error", error=e))
    def get_total_pages(self) -> int:
        """総ページ数を取得"""
        return len(self.current_files) if self.current_files else 0
    def go_to_page(self, page_index: int) -> bool:
        """指定されたページに移動（0ベースのインデックス）"""
        if not self.current_files:
            return False
        if 0 <= page_index < len(self.current_files):
            self.current_index = page_index
            result = self._open_current_file()
            if result:
                # ページ移動後にプリフェッチを実行
                self._prefetch_around(self.current_index)
                logger.info(get_log_text("debug_go_to_page_prefetch_started", page_index=page_index))
            return result
        return False 
    def _create_temp_dir(self):
        """一時ディレクトリを作成"""
        # ファイルハンドル非保持モードでは一時ディレクトリを作成しない
        if not self._should_keep_archive_handles():
            logger.info(get_log_text("file_handler_temp_dir_skipped_no_handle_mode"))
            self.temp_dir = None
            return
            
        try:
            self.temp_dir = Path(tempfile.mkdtemp(prefix="creader_"))
            logger.info(get_log_text("file_handler_temp_dir_created", temp_dir=self.temp_dir))
        except Exception as e:
            logger.error(get_log_text("file_handler_temp_dir_failed", error=e))
            self.temp_dir = None
    def _should_keep_archive_handles(self) -> bool:
        """アーカイブファイルハンドルを保持するかどうかを判定"""
        if not self.config:
            return False  # 設定がない場合はデフォルトで保持しない
        return self.config.debug.get("keep_archive_handles", False)
    
    def _parse_cache_size(self) -> int:
        """設定からキャッシュサイズを解析してバイト数で返す"""
        try:
            if not self.config or not hasattr(self.config, 'cache'):
                # 設定がない場合はデフォルト値（256MB）
                default_size = "256MB"
                logger.info(get_log_text("debug_cache_size_no_config", default_size=default_size))
                return humanfriendly.parse_size(default_size)
            
            cache_config = self.config.cache
            memory_limit = cache_config.get("memory_limit", "256MB")
            
            # 文字列形式をhumanfriendlyでパース
            if isinstance(memory_limit, str):
                cache_bytes = humanfriendly.parse_size(memory_limit)
                logger.info(get_log_text("debug_cache_size_parsed", memory_limit=memory_limit, cache_bytes=cache_bytes))
                return cache_bytes
            else:
                # 従来の数値形式（MB）の場合
                cache_mb = int(memory_limit)
                cache_bytes = cache_mb * 1024 * 1024
                logger.info(get_log_text("debug_cache_size_legacy", cache_mb=cache_mb, cache_bytes=cache_bytes))
                return cache_bytes
                
        except Exception as e:
            # パースに失敗した場合はデフォルト値（256MB）
            default_bytes = 256 * 1024 * 1024
            logger.error(get_log_text("debug_cache_size_parse_error", error=e, default_bytes=default_bytes))
            return default_bytes
    
    def _check_file_accessibility(self, target_index: int) -> bool:
        """指定されたインデックスのファイルがアクセス可能かチェック"""
        if target_index < 0 or target_index >= len(self.current_files):
            logger.warning(get_log_text("debug_check_file_accessibility", index=target_index, file="OUT_OF_RANGE"))
            return False
        
        file = self.current_files[target_index]
        logger.info(get_log_text("debug_check_file_accessibility", index=target_index, file=file))
        
        # デバッグ情報を出力
        logger.info(get_log_text("debug_current_files_list", current_files=self.current_files))
        logger.info(get_log_text("debug_cache_keys_list", cache_keys=list(self.image_cache.keys())))
        
        # キャッシュにある場合はアクセス可能とみなす
        if VirtualPathHandler.is_virtual_path(file):
            result = VirtualPathHandler.parse_virtual_path(file)
            if result:
                archive_path, filename = result
                # パスを正規化してキャッシュキーとして使用
                normalized_archive_path = str(Path(archive_path).resolve())
                cache_key = f"{normalized_archive_path}|{filename}"
                logger.debug(get_log_text("debug_file_accessibility_cache_miss", cache_key=cache_key))
                
                if cache_key in self.image_cache:
                    logger.debug(get_log_text("debug_file_accessibility_cache_hit", cache_key=cache_key))
                    logger.debug(get_log_text("debug_file_accessibility_result", result=True))
                    return True
                
                logger.debug(get_log_text("debug_file_accessibility_cache_miss", cache_key=cache_key))
                # アーカイブファイルの存在チェック
                archive_exists = Path(archive_path).exists()
                logger.debug(get_log_text("debug_file_accessibility_file_exists", exists=archive_exists, path=archive_path))
                
                if not archive_exists:
                    archive_name = Path(archive_path).name
                    error_msg = get_log_text("file_handler_folder_access_failed", 
                                           directory=archive_path, error="Archive file not found")
                    logger.error(error_msg)
                    self._notify_error("archive_no_longer_accessible", error_msg, str(archive_path))
                    logger.debug(get_log_text("debug_file_accessibility_result", result=False))
                    return False
                
                logger.debug(get_log_text("debug_file_accessibility_result", result=True))
                return True
            
            logger.debug(get_log_text("debug_file_accessibility_result", result=False))
            return False
        else:
            # 通常のファイル - パスを正規化
            cache_key = str(Path(file).resolve())
            
            if cache_key in self.image_cache:
                logger.debug(get_log_text("debug_file_accessibility_cache_hit", cache_key=cache_key))
                logger.debug(get_log_text("debug_file_accessibility_result", result=True))
                return True
            
            logger.debug(get_log_text("debug_file_accessibility_cache_miss", cache_key=cache_key))
            
            # ファイルまたはフォルダの存在チェック
            file_path = Path(file)
            file_exists = file_path.exists()
            logger.debug(get_log_text("debug_file_accessibility_file_exists", exists=file_exists, path=file_path))
            
            if not file_exists:
                error_msg = get_log_text("file_handler_folder_access_failed", 
                                       directory=file_path, error="File or folder not found")
                logger.error(error_msg)
                self._notify_error("file_no_longer_accessible", error_msg, str(file_path))
                logger.debug(get_log_text("debug_file_accessibility_result", result=False))
                return False
            
            # フォルダの場合、アクセス権限をチェック
            if file_path.is_dir():
                try:
                    # フォルダ内の読み取りテスト
                    import os
                    os.listdir(str(file_path))
                except (PermissionError, OSError) as e:
                    error_msg = get_log_text("file_handler_folder_access_failed", 
                                           directory=file_path, error=f"Cannot access folder: {e}")
                    logger.error(error_msg)
                    self._notify_error("folder_access_failed", error_msg, str(file_path))
                    logger.debug(get_log_text("debug_file_accessibility_result", result=False))
                    return False
            
            logger.debug(get_log_text("debug_file_accessibility_result", result=True))
            return True
    def _notify_error(self, error_type: str, error_message: str, archive_path: str):
        """エラーをメインスレッドに通知"""
        if self._on_error_occurred:
            try:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: self._on_error_occurred(error_type, error_message, archive_path))
            except Exception as e:
                logger.error(get_log_text("debug_failed_to_call_error_callback", error=e))
    def _process_zip_archive_sync(self, archive_path_str: str, filename: str) -> Optional[Image.Image]:
        """ZIPアーカイブの処理（同期的、セッションチェックなし）"""
        with open_zip(archive_path_str, 'r') as archive:
            apply_zip_password(archive, archive_path_str)
            # アーカイブ内のファイル名を検索
            archive_names = archive.namelist()
            target_filename = None
            logger.debug(get_log_text("file_handler_looking_for_file", filename=filename))
            logger.debug(get_log_text("file_handler_archive_contains_files", file_count=len(archive_names)))
            
            # ファイル名のパス区切り文字を正規化（バックスラッシュをスラッシュに変換）
            normalized_filename = filename.replace('\\', '/')

            # ファイル名の検索ロジック（既存のロジックを使用）
            # 注意: filenameはVirtualPathHandler.parse_virtual_pathで既に正規化されている
            decoded_filename = self._decode_zip_filename(normalized_filename)
            for archive_name in archive_names:
                decoded_archive_name = self._decode_zip_filename(archive_name)
                if decoded_archive_name == decoded_filename:
                    target_filename = archive_name
                    logger.debug(get_log_text("file_handler_found_exact_match", archive_name=archive_name, decoded_name=decoded_archive_name))
                    break
            
            if not target_filename and filename in archive_names:
                target_filename = filename
                logger.debug(get_log_text("file_handler_found_original_match", filename=filename))
            
            if not target_filename:
                for archive_name in archive_names:
                    decoded_archive_name = self._decode_zip_filename(archive_name)
                    if decoded_archive_name == filename:
                        target_filename = archive_name
                        logger.debug(get_log_text("file_handler_found_decoded_match", archive_name=archive_name, decoded_name=decoded_archive_name))
                        break
            
            if not target_filename:
                filename_ext = Path(filename).suffix.lower()
                filename_stem = Path(filename).stem
                # ファイル名に英字が含まれている場合は数値マッチングをスキップ（完全一致が必要）
                has_letters = any(c.isalpha() for c in filename_stem)
                if not has_letters:
                    # 英字が含まれていない場合のみ数値マッチングを試行
                    for archive_name in archive_names:
                        if Path(archive_name).suffix.lower() == filename_ext:
                            try:
                                filename_num = int(''.join(filter(str.isdigit, filename_stem)))
                                archive_stem = Path(archive_name).stem
                                archive_num = int(''.join(filter(str.isdigit, archive_stem)))
                                # アーカイブファイル名にも英字が含まれていない場合のみマッチ
                                archive_has_letters = any(c.isalpha() for c in archive_stem)
                                if filename_num == archive_num and not archive_has_letters:
                                    target_filename = archive_name
                                    logger.debug(get_log_text("file_handler_found_numeric_match", archive_name=archive_name, archive_num=archive_num))
                                    break
                            except (ValueError, AttributeError):
                                pass
            
            if target_filename:
                logger.debug(get_log_text("file_handler_opening_file", file=target_filename))
                with archive.open(target_filename) as image_file:
                    image = Image.open(image_file)
                    image.load()
                    return image
            else:
                error_msg = get_log_text("debug_file_not_found_in_archive", filename=filename)
                logger.error(error_msg)
                logger.error(get_log_text("file_handler_available_files", files=archive_names[:10]))
                self._notify_error("file_not_in_archive", error_msg, archive_path_str)
                return None

    def _process_zip_archive(self, archive_path_str: str, filename: str, session_id: int = None) -> Optional[Image.Image]:
        """ZIPアーカイブの処理（非同期用、セッションチェックあり）"""
        if session_id is None:
            session_id = self._get_current_session_id()
        if not self._is_session_active(session_id):
            logger.info(get_log_text("debug_process_zip_archive_session_cancelled", archive_path=archive_path_str, session_id=session_id))
            return None
        return self._process_zip_archive_sync(archive_path_str, filename)

    def _process_7z_archive_sync(self, archive_path_str: str, filename: str, internal_name: str) -> Optional[Image.Image]:
        """7ZIPアーカイブの処理（同期的、セッションチェックなし）"""
        with py7zr.SevenZipFile(archive_path_str, 'r', password=seven_zip_password_arg(archive_path_str)) as archive:
            try:
                archive_names = archive.getnames()
                target_filename = None
                logger.debug(get_log_text("file_handler_looking_for_file", filename=filename))
                logger.debug(get_log_text("file_handler_archive_contains_files", file_count=len(archive_names)))
                
                decoded_filename = self._decode_archive_filename(filename, internal_name)
                for archive_name in archive_names:
                    decoded_archive_name = self._decode_archive_filename(archive_name, internal_name)
                    if decoded_archive_name == decoded_filename:
                        target_filename = archive_name
                        logger.debug(get_log_text("file_handler_found_exact_match", archive_name=archive_name, decoded_name=decoded_archive_name))
                        break
                
                if not target_filename and filename in archive_names:
                    target_filename = filename
                    logger.debug(get_log_text("file_handler_found_original_match", filename=filename))
                
                if target_filename:
                    logger.debug(get_log_text("file_handler_opening_file", file=target_filename))
                    extracted_files = archive.read([target_filename])
                    if target_filename in extracted_files:
                        extracted_file = extracted_files[target_filename].read()
                        image = Image.open(io.BytesIO(extracted_file))
                        image.load()
                        return image

                    error_msg = get_log_text("debug_file_not_found_in_7z_archive", filename=target_filename)
                    logger.error(error_msg)
                    self._notify_error("file_not_in_archive", error_msg, archive_path_str)
                    return None
                else:
                    error_msg = get_log_text("debug_file_not_found_in_7z_archive", filename=filename)
                    logger.error(error_msg)
                    logger.error(get_log_text("file_handler_available_files", files=archive_names[:10]))
                    self._notify_error("file_not_in_archive", error_msg, archive_path_str)
                    return None
            except Exception as e:
                error_msg = get_log_text("debug_failed_to_read_from_7z_archive", error=e)
                logger.error(error_msg)
                self._notify_error("processing_failed", error_msg, archive_path_str)
                return None

    def _process_7z_archive(self, archive_path_str: str, filename: str, internal_name: str, session_id: int = None) -> Optional[Image.Image]:
        """7ZIPアーカイブの処理（非同期用、セッションチェックあり）"""
        if session_id is None:
            session_id = self._get_current_session_id()
        if not self._is_session_active(session_id):
            logger.info(get_log_text("debug_process_7z_archive_session_cancelled", archive_path=archive_path_str, session_id=session_id))
            return None
        return self._process_7z_archive_sync(archive_path_str, filename, internal_name)

    def _process_rar_archive(self, archive_path_str: str, filename: str, internal_name: str, session_id: int = None) -> Optional[Image.Image]:
        """RARアーカイブの処理（非同期用、セッションチェックあり）"""
        if session_id is None:
            session_id = self._get_current_session_id()
        if not self._is_session_active(session_id):
            logger.info(get_log_text("debug_process_rar_archive_session_cancelled", archive_path=archive_path_str, session_id=session_id))
            return None
        return self._process_rar_archive_sync(archive_path_str, filename, internal_name)

    def _process_rar_archive_sync(self, archive_path_str: str, filename: str, internal_name: str) -> Optional[Image.Image]:
        """RARアーカイブの処理（同期的、セッションチェックなし）"""
        with rarfile.RarFile(archive_path_str, 'r') as archive:
            apply_rar_password(archive, archive_path_str)
            archive_names = archive.namelist()
            target_filename = None
            logger.debug(get_log_text("file_handler_looking_for_file", filename=filename))
            logger.debug(get_log_text("file_handler_archive_contains_files", file_count=len(archive_names)))
            
            normalized_filename = filename.replace('\\', '/')
            decoded_filename = self._decode_archive_filename(normalized_filename, internal_name)
            
            for archive_name in archive_names:
                normalized_archive_name = archive_name.replace('\\', '/')
                decoded_archive_name = self._decode_archive_filename(normalized_archive_name, internal_name)
                if decoded_archive_name == decoded_filename:
                    target_filename = archive_name
                    logger.debug(get_log_text("file_handler_found_exact_match", archive_name=archive_name, decoded_name=decoded_archive_name))
                    break
            
            if not target_filename:
                for archive_name in archive_names:
                    normalized_archive_name = archive_name.replace('\\', '/')
                    if normalized_archive_name == normalized_filename:
                        target_filename = archive_name
                        logger.debug(get_log_text("file_handler_found_normalized_match", archive_name=archive_name))
                        break
            
            if not target_filename and filename in archive_names:
                target_filename = filename
                logger.debug(get_log_text("file_handler_found_original_match", filename=filename))
            
            if not target_filename:
                filename_only = Path(normalized_filename).name
                for archive_name in archive_names:
                    normalized_archive_name = archive_name.replace('\\', '/')
                    archive_filename_only = Path(normalized_archive_name).name
                    if archive_filename_only == filename_only:
                        target_filename = archive_name
                        logger.debug(get_log_text("file_handler_found_filename_only_match", archive_name=archive_name))
                        break
            
            if target_filename:
                logger.debug(get_log_text("file_handler_opening_file", file=target_filename))
                with archive.open(target_filename) as image_file:
                    image = Image.open(image_file)
                    image.load()
                    return image
            else:
                error_msg = get_log_text("debug_file_not_found_in_rar_archive", filename=filename)
                logger.error(error_msg)
                logger.error(get_log_text("file_handler_available_files", files=archive_names[:10]))
                self._notify_error("file_not_in_archive", error_msg, archive_path_str)
                return None

    def _process_tar_archive_sync(self, archive_path_str: str, filename: str, internal_name: str) -> Optional[Image.Image]:
        """TARアーカイブの処理（同期的、セッションチェックなし）"""
        with tarfile.open(archive_path_str, 'r') as archive:
            archive_names = archive.getnames()
            target_filename = None
            logger.debug(get_log_text("file_handler_looking_for_file", filename=filename))
            logger.debug(get_log_text("file_handler_archive_contains_files", file_count=len(archive_names)))
            
            decoded_filename = self._decode_archive_filename(filename, internal_name)
            for archive_name in archive_names:
                decoded_archive_name = self._decode_archive_filename(archive_name, internal_name)
                if decoded_archive_name == decoded_filename:
                    target_filename = archive_name
                    logger.debug(get_log_text("file_handler_found_exact_match", archive_name=archive_name, decoded_name=decoded_archive_name))
                    break
            
            if not target_filename and filename in archive_names:
                target_filename = filename
                logger.debug(get_log_text("file_handler_found_original_match", filename=filename))
            
            if target_filename:
                logger.debug(get_log_text("file_handler_opening_file", file=target_filename))
                with archive.extractfile(target_filename) as image_file:
                    image = Image.open(image_file)
                    image.load()
                    return image
            else:
                error_msg = get_log_text("debug_file_not_found_in_tar_archive", filename=filename)
                logger.error(error_msg)
                logger.error(get_log_text("file_handler_available_files", files=archive_names[:10]))
                self._notify_error("file_not_in_archive", error_msg, archive_path_str)
                return None

    def _process_tar_archive(self, archive_path_str: str, filename: str, internal_name: str, session_id: int = None) -> Optional[Image.Image]:
        """TARアーカイブの処理（非同期用、セッションチェックあり）"""
        if session_id is None:
            session_id = self._get_current_session_id()
        if not self._is_session_active(session_id):
            logger.info(get_log_text("debug_process_tar_archive_session_cancelled", archive_path=archive_path_str, session_id=session_id))
            return None
        return self._process_tar_archive_sync(archive_path_str, filename, internal_name) 