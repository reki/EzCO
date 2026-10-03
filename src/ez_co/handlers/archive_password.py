"""暗号化アーカイブ／PDFのパスワード検出とセッション保持。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import py7zr
import pyzipper
import rarfile
from pypdf import PdfReader

from ez_co.enums.archives import ArchiveInfo, ArchiveType
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)

_session_passwords: dict[str, str] = {}

# パスワードを尋ねるアーカイブ種別
PASSWORD_ARCHIVE_TYPES = {
    ArchiveType.ZIP,
    ArchiveType.CBZ,
    ArchiveType.SEVEN_ZIP,
    ArchiveType.RAR,
    ArchiveType.CBR,
    ArchiveType.PDF,
}


def normalize_archive_path(file_path: str) -> str:
    """アーカイブパスを解決して比較用の文字列にする。

    Args:
        file_path: 対象ファイルのパス。

    Returns:
        解決したパスの文字列。
    """
    return str(Path(file_path).resolve())


def get_session_password(file_path: str) -> Optional[str]:
    """セッションに保存したパスワードを返す。

    Args:
        file_path: 対象ファイルのパス。

    Returns:
        保存されていればその文字列。無ければ None。
    """
    return _session_passwords.get(normalize_archive_path(file_path))


def set_session_password(file_path: str, password: str) -> None:
    """セッションへパスワードを保存する。

    Args:
        file_path: 対象ファイルのパス。
        password: 保存するパスワード。
    """
    _session_passwords[normalize_archive_path(file_path)] = password


def zip_password_bytes(file_path: str) -> Optional[bytes]:
    """ZIP に渡すパスワードバイト列を返す。

    Args:
        file_path: 対象ファイルのパス。

    Returns:
        セッションにあれば UTF-8 のバイト列。空や未設定なら None。
    """
    password = get_session_password(file_path)
    if not password:
        return None
    return password.encode("utf-8")


def open_zip(file_path, mode: str = "r"):
    """ZIP を AESZipFile で開く。

    Args:
        file_path: 開く ZIP のパス。
        mode: 開くモード。

    Returns:
        開いたアーカイブ。
    """
    # pyzipper.ZipFile は標準zipfile相当。AES(ZipCrypto以外)は AESZipFile が必要。
    return pyzipper.AESZipFile(file_path, mode)


def apply_zip_password(archive, file_path: str) -> None:
    """セッションのパスワードがあれば ZIP に設定する。

    Args:
        archive: 開いている ZIP。
        file_path: パスワードを引くファイルのパス。
    """
    password = zip_password_bytes(file_path)
    if password:
        archive.setpassword(password)


def seven_zip_password_arg(file_path: str) -> Optional[str]:
    """7z を開くときに渡すパスワードを返す。

    Args:
        file_path: 対象ファイルのパス。

    Returns:
        セッションにあればその文字列。空や未設定なら None。
    """
    return get_session_password(file_path) or None


def apply_rar_password(archive: rarfile.RarFile, file_path: str) -> None:
    """セッションのパスワードがあれば RAR に設定する。

    Args:
        archive: 開いている RAR。
        file_path: パスワードを引くファイルのパス。
    """
    password = get_session_password(file_path)
    if password:
        archive.setpassword(password)


def is_encrypted(file_path: str) -> bool:
    """アーカイブまたは PDF が暗号化されているか返す。

    Args:
        file_path: 対象ファイルのパス。

    Returns:
        暗号化されていれば真。対応外か、判定に失敗したときは偽。
    """
    archive_type = ArchiveInfo.get_archive_type_by_path(file_path)
    try:
        if archive_type in (ArchiveType.ZIP, ArchiveType.CBZ):
            return _zip_is_encrypted(file_path)
        if archive_type == ArchiveType.SEVEN_ZIP:
            return _seven_zip_is_encrypted(file_path)
        if archive_type in (ArchiveType.RAR, ArchiveType.CBR):
            return _rar_is_encrypted(file_path)
        if archive_type == ArchiveType.PDF:
            return _pdf_is_encrypted(file_path)
    except Exception as exc:
        # 判定に失敗したらデバッグログを残して、暗号化されていないものとして偽を返す
        logger.debug(get_log_text("debug_archive_password_detect_failed", file_path=file_path, error=exc))
        return False
    return False


def try_unlock(file_path: str, password: str) -> bool:
    """パスワードで暗号化を解けるか試す。

    Args:
        file_path: 対象ファイルのパス。
        password: 試すパスワード。

    Returns:
        解ければ真。対応外の形式は真。失敗したときは偽。
    """
    archive_type = ArchiveInfo.get_archive_type_by_path(file_path)
    try:
        if archive_type in (ArchiveType.ZIP, ArchiveType.CBZ):
            return _try_unlock_zip(file_path, password)
        if archive_type == ArchiveType.SEVEN_ZIP:
            return _try_unlock_seven_zip(file_path, password)
        if archive_type in (ArchiveType.RAR, ArchiveType.CBR):
            return _try_unlock_rar(file_path, password)
        if archive_type == ArchiveType.PDF:
            return _try_unlock_pdf(file_path, password)
    except Exception as exc:
        # 解錠に失敗したらデバッグログを残して偽を返す
        logger.debug(get_log_text("debug_archive_password_rejected", file_path=file_path, error=exc))
        return False
    return True


def _zip_is_encrypted(file_path: str) -> bool:
    """ZIP 内のファイルに暗号化フラグがあるか返す。

    Args:
        file_path: ZIP のパス。

    Returns:
        ディレクトリ以外で暗号化フラグが立っていれば真。
    """
    with open_zip(file_path, "r") as archive:
        return any(info.flag_bits & 0x1 for info in archive.infolist() if not info.is_dir())


def _try_unlock_zip(file_path: str, password: str) -> bool:
    """パスワードで ZIP の暗号化エントリを読めるか試す。

    Args:
        file_path: ZIP のパス。
        password: 試すパスワード。

    Returns:
        暗号化エントリが無いか、最初の1件を読めれば真。
    """
    pwd = password.encode("utf-8") if password else None
    with open_zip(file_path, "r") as archive:
        encrypted = [info for info in archive.infolist() if (info.flag_bits & 0x1) and not info.is_dir()]
        if not encrypted:
            return True
        archive.read(encrypted[0], pwd=pwd)
        return True


def _seven_zip_is_encrypted(file_path: str) -> bool:
    """7z がパスワードを要求するか返す。

    Args:
        file_path: 7z のパス。

    Returns:
        パスワードが必要なら真。開けないときも真。
    """
    try:
        with py7zr.SevenZipFile(file_path, "r") as archive:
            return bool(archive.needs_password())
    except Exception:
        # 7z を開けなければ、パスワードが要るものとして真を返す
        return True


def _try_unlock_seven_zip(file_path: str, password: str) -> bool:
    """パスワードで 7z を開けるか試す。

    Args:
        file_path: 7z のパス。
        password: 試すパスワード。

    Returns:
        パスワードが不要か、最初のファイルを読めれば真。
    """
    with py7zr.SevenZipFile(file_path, "r", password=password or None) as archive:
        if not archive.needs_password():
            return True
        names = [name for name in archive.getnames() if name and not name.endswith("/")]
        if names:
            archive.read([names[0]])
        return True


def _rar_is_encrypted(file_path: str) -> bool:
    """RAR がパスワードを要求するか返す。

    Args:
        file_path: RAR のパス。

    Returns:
        パスワードが必要なら真。開けないときも真。
    """
    try:
        with rarfile.RarFile(file_path, "r") as archive:
            return bool(archive.needs_password())
    except Exception:
        # RAR を開けなければ、パスワードが要るものとして真を返す
        return True


def _try_unlock_rar(file_path: str, password: str) -> bool:
    """パスワードで RAR を開けるか試す。

    Args:
        file_path: RAR のパス。
        password: 試すパスワード。

    Returns:
        パスワードが不要か、最初のファイルを読めれば真。
    """
    with rarfile.RarFile(file_path, "r") as archive:
        archive.setpassword(password)
        if not archive.needs_password():
            return True
        for info in archive.infolist():
            if info.isdir():
                continue
            archive.read(info)
            return True
        return True


def _pdf_is_encrypted(file_path: str) -> bool:
    """PDF が暗号化されているか返す。

    Args:
        file_path: PDF のパス。

    Returns:
        暗号化されていれば真。
    """
    reader = PdfReader(file_path)
    try:
        return bool(reader.is_encrypted)
    finally:
        reader.close()


def _try_unlock_pdf(file_path: str, password: str) -> bool:
    """パスワードで PDF を解けるか試す。

    Args:
        file_path: PDF のパス。
        password: 試すパスワード。

    Returns:
        暗号化されていなければ真。暗号化されていれば復号の成否。
    """
    reader = PdfReader(file_path)
    try:
        if not reader.is_encrypted:
            return True
        return bool(reader.decrypt(password))
    finally:
        reader.close()
