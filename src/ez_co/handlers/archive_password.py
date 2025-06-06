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

PASSWORD_ARCHIVE_TYPES = {
    ArchiveType.ZIP,
    ArchiveType.CBZ,
    ArchiveType.SEVEN_ZIP,
    ArchiveType.RAR,
    ArchiveType.CBR,
    ArchiveType.PDF,
}


def normalize_archive_path(file_path: str) -> str:
    return str(Path(file_path).resolve())


def get_session_password(file_path: str) -> Optional[str]:
    return _session_passwords.get(normalize_archive_path(file_path))


def set_session_password(file_path: str, password: str) -> None:
    _session_passwords[normalize_archive_path(file_path)] = password


def supports_password(file_path: str) -> bool:
    archive_type = ArchiveInfo.get_archive_type_by_path(file_path)
    return archive_type in PASSWORD_ARCHIVE_TYPES


def zip_password_bytes(file_path: str) -> Optional[bytes]:
    password = get_session_password(file_path)
    if not password:
        return None
    return password.encode("utf-8")


def open_zip(file_path, mode: str = "r"):
    # pyzipper.ZipFile は標準zipfile相当。AES(ZipCrypto以外)は AESZipFile が必要。
    return pyzipper.AESZipFile(file_path, mode)


def apply_zip_password(archive, file_path: str) -> None:
    password = zip_password_bytes(file_path)
    if password:
        archive.setpassword(password)


def seven_zip_password_arg(file_path: str) -> Optional[str]:
    return get_session_password(file_path) or None


def apply_rar_password(archive: rarfile.RarFile, file_path: str) -> None:
    password = get_session_password(file_path)
    if password:
        archive.setpassword(password)


def is_encrypted(file_path: str) -> bool:
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
        logger.debug(get_log_text("debug_archive_password_detect_failed", file_path=file_path, error=exc))
        return False
    return False


def try_unlock(file_path: str, password: str) -> bool:
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
        logger.debug(get_log_text("debug_archive_password_rejected", file_path=file_path, error=exc))
        return False
    return True


def _zip_is_encrypted(file_path: str) -> bool:
    with open_zip(file_path, "r") as archive:
        return any(info.flag_bits & 0x1 for info in archive.infolist() if not info.is_dir())


def _try_unlock_zip(file_path: str, password: str) -> bool:
    pwd = password.encode("utf-8") if password else None
    with open_zip(file_path, "r") as archive:
        encrypted = [info for info in archive.infolist() if (info.flag_bits & 0x1) and not info.is_dir()]
        if not encrypted:
            return True
        archive.read(encrypted[0], pwd=pwd)
        return True


def _seven_zip_is_encrypted(file_path: str) -> bool:
    try:
        with py7zr.SevenZipFile(file_path, "r") as archive:
            return bool(archive.needs_password())
    except Exception:
        return True


def _try_unlock_seven_zip(file_path: str, password: str) -> bool:
    with py7zr.SevenZipFile(file_path, "r", password=password or None) as archive:
        if not archive.needs_password():
            return True
        names = [name for name in archive.getnames() if name and not name.endswith("/")]
        if names:
            archive.read([names[0]])
        return True


def _rar_is_encrypted(file_path: str) -> bool:
    try:
        with rarfile.RarFile(file_path, "r") as archive:
            return bool(archive.needs_password())
    except Exception:
        return True


def _try_unlock_rar(file_path: str, password: str) -> bool:
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
    reader = PdfReader(file_path)
    try:
        return bool(reader.is_encrypted)
    finally:
        reader.close()


def _try_unlock_pdf(file_path: str, password: str) -> bool:
    reader = PdfReader(file_path)
    try:
        if not reader.is_encrypted:
            return True
        return bool(reader.decrypt(password))
    finally:
        reader.close()
