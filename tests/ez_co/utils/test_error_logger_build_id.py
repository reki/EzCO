"""対象: ez_co.utils.error_logger"""
from pathlib import Path

import pytest

from ez_co.utils import app_info
from ez_co.utils.error_logger import initialize_error_logger, report_error


def _report(tmp_path: Path, exc: Exception) -> str:
    logger = initialize_error_logger(tmp_path)
    try:
        raise exc
    except Exception as error:
        report_error("unhandled", error)
    return logger.log_file.read_text(encoding="utf-8")


def test_error_log_starts_with_version_and_64_hex_then_traceback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    full = "ab" * 32
    monkeypatch.setattr(
        app_info,
        "build_id_error_header",
        lambda: f"EzCo version=9.9.9\nBuild id={full}",
    )

    text = _report(tmp_path, RuntimeError("boom"))

    assert f"EzCo version=9.9.9\nBuild id={full}" in text
    position = text.index(f"Build id={full}")
    assert "Traceback (most recent call last):" in text[position:]
    assert "RuntimeError: boom" in text


def test_traceback_remains_when_build_id_cannot_be_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    def fail():
        raise OSError("unavailable")

    monkeypatch.setattr(app_info, "build_id_error_header", fail)

    text = _report(tmp_path, ValueError("still here"))

    assert "Build id=" not in text
    assert "ValueError: still here" in text
    assert "Traceback (most recent call last):" in text
