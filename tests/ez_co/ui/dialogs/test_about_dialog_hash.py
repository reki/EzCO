"""対象: ez_co.ui.dialogs.about_dialog"""
import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from ez_co.ui.dialogs import about_dialog
from ez_co.ui.dialogs.about_dialog import AboutDialog
from ez_co.utils.language_manager import get_text

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_dialog_shows_16_digits_and_tooltip_keeps_64(monkeypatch: pytest.MonkeyPatch):
    """画面のビルド識別が先頭16文字以外になり、ツールチップから64文字が消える。"""
    full = "ab" * 32
    monkeypatch.setattr(about_dialog, "current_build_id", lambda: full)
    dialog = AboutDialog()
    try:
        shown = [
            label
            for label in dialog.findChildren(QLabel)
            if label.text() == full[:16]
        ]
        assert len(shown) == 1
        assert shown[0].toolTip() == full
    finally:
        dialog.close()


def test_empty_build_id_adds_no_row(monkeypatch: pytest.MonkeyPatch):
    """ビルド識別が空なのに、日英どちらかの見出し行が増える。"""
    monkeypatch.setattr(about_dialog, "current_build_id", lambda: "")
    dialog = AboutDialog()
    try:
        texts = [label.text() for label in dialog.findChildren(QLabel)]
        assert "ビルド識別" not in texts
        assert "Build id" not in texts
    finally:
        dialog.close()


def test_copy_text_uses_the_full_build_id(monkeypatch: pytest.MonkeyPatch):
    """コピー文が16文字の省略になり、64文字の識別子かバージョン行が欠ける。"""
    full = "ab" * 32
    monkeypatch.setattr(about_dialog, "current_build_id", lambda: full)
    dialog = AboutDialog()
    try:
        text = dialog.copy_text()
        label = get_text("ui.about_hash")
        assert f"{label}: {full}" in text
        assert f"{label}: {full[:16]}\n" not in text + "\n"
        assert get_text("ui.version") + ":" in text
    finally:
        dialog.close()


def test_copy_button_writes_the_same_text_to_the_clipboard(
    monkeypatch: pytest.MonkeyPatch,
):
    """コピーボタンが copy_text と違う文を書き、全文の識別子がクリップボードに無い。"""
    full = "cd" * 32
    monkeypatch.setattr(about_dialog, "current_build_id", lambda: full)
    dialog = AboutDialog()
    try:
        button = next(
            widget
            for widget in dialog.findChildren(QPushButton)
            if widget.text() == get_text("ui.error_log_copy")
        )
        button.click()
        clipboard = QApplication.clipboard()
        assert clipboard is not None
        assert clipboard.text() == dialog.copy_text()
        assert full in clipboard.text()
    finally:
        dialog.close()
