"""仮想的なパス（archive://path|filename または archive:\path|filename）を処理するユーティリティクラス"""
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
from ez_co.enums.archives import ArchiveInfo, ArchiveType
from ez_co.enums.images import ImageInfo
from ez_co.enums.encodings import EncodingInfo
from ez_co.utils.language_manager import get_text, get_log_text
logger = logging.getLogger(__name__)
class VirtualPathHandler:
    """仮想的なパス（archive://path|filename または archive:\path|filename）を処理するユーティリティクラス"""
    @staticmethod
    def is_virtual_path(path: Union[str, Path]) -> bool:
        """パスが仮想的なパスかどうかを判定"""
        path_str = str(path)
        return path_str.startswith("archive://") or path_str.startswith("archive:\\")
    @staticmethod
    def parse_virtual_path(path: Union[str, Path]) -> Optional[Tuple[Path, str]]:
        """仮想的なパスを解析してアーカイブパスとファイル名を取得"""
        path_str = str(path)
        if not VirtualPathHandler.is_virtual_path(path_str):
            return None
        # archive://path|filename または archive:\path|filename の形式を解析
        if path_str.startswith("archive://"):
            archive_info = path_str[9:]  # "archive://" を除去
        elif path_str.startswith("archive:\\"):
            archive_info = path_str[9:]  # "archive:\" を除去
        else:
            # logger.error(get_log_text("virtual_path_invalid_format", path=path))
            return None
        if "|" in archive_info:
            archive_path_str, filename = archive_info.split("|", 1)
            # パスを正規化（バックスラッシュをスラッシュに変換）
            archive_path_str = archive_path_str.replace('\\', '/')
            # Windowsのドライブ文字の前の余分なスラッシュを削除
            if archive_path_str.startswith('/') and len(archive_path_str) > 2 and archive_path_str[2] == ':':
                archive_path_str = archive_path_str[1:]
            archive_path = Path(archive_path_str)
            # ファイル名も正規化（バックスラッシュをスラッシュに変換）
            normalized_filename = filename.replace('\\', '/')
            # logger.debug(get_log_text("debug_parse_virtual_path", path_str=path_str, archive_path=archive_path, filename=filename))
            return archive_path, normalized_filename
        else:
            # logger.error(get_log_text("virtual_path_invalid_format", path=path))
            return None
    @staticmethod
    def create_virtual_path(archive_path: Union[str, Path], filename: str) -> str:
        """仮想的なパスを作成"""
        return f"archive://{archive_path}|{filename}"
    @staticmethod
    def get_archive_parent_dir(path: Union[str, Path]) -> Optional[Path]:
        """仮想パスからアーカイブファイルの親ディレクトリを取得"""
        result = VirtualPathHandler.parse_virtual_path(path)
        if result:
            archive_path, _ = result
            return archive_path.parent
        return None
