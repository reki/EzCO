"""対象: ez_co.main"""
import logging

import pytest

from ez_co import main as main_module


def test_log_build_id_writes_version_and_64_hex(monkeypatch: pytest.MonkeyPatch, caplog):
    """起動ログにバージョンと 64 桁のビルド ID が出る。"""
    full = "12" * 32
    monkeypatch.setattr(main_module, "load_app_info", lambda: {"version": "1.2.3"})
    monkeypatch.setattr(main_module, "current_build_id", lambda: full)
    caplog.set_level(logging.INFO, logger="ez_co.main")

    main_module.log_build_id()

    assert f"version=1.2.3" in caplog.text
    assert f"build_id={full}" in caplog.text
    assert len(full) == 64
