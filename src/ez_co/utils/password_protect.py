"""Windows DPAPI で文字列を暗号化・復号する。"""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
from typing import Optional


class DATA_BLOB(ctypes.Structure):
    """CryptProtectData に渡すバイト列。"""
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


# 暗号化時に UI を出さないフラグ
CRYPTPROTECT_UI_FORBIDDEN = 0x01


def _as_blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    """バイト列を DATA_BLOB と、そのバッファにする。

    Args:
        data: 包むバイト列

    Returns:
        DATA_BLOB と、生存させておくバッファ
    """
    buffer = ctypes.create_string_buffer(data, len(data))
    blob = DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))
    return blob, buffer


def encrypt_secret(plaintext: str) -> str:
    """文字列を DPAPI で暗号化し、Base64 にする。

    Args:
        plaintext: 暗号化する文字列

    Returns:
        Base64 の暗号文

    Raises:
        OSError: CryptProtectData に失敗したとき
    """
    raw = plaintext.encode("utf-8")
    in_blob, buffer = _as_blob(raw)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptProtectData failed")
    try:
        protected = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        del buffer


def decrypt_secret(token: str) -> Optional[str]:
    """Base64 の DPAPI 暗号文を文字列に戻す。

    Args:
        token: Base64 の暗号文

    Returns:
        復号した文字列。空、または失敗したときは None
    """
    if not token:
        return None
    try:
        raw = base64.b64decode(token)
    except Exception:
        # Base64 でなければ復号できないので None を返す
        return None
    in_blob, buffer = _as_blob(raw)
    out_blob = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(out_blob),
    ):
        return None
    try:
        plain = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        return plain.decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        del buffer
