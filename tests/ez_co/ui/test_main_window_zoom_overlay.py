"""対象: ez_co.ui.main_window — ズーム表示ラベルの生存判定。"""
from types import SimpleNamespace

import pytest
import shiboken6
from PySide6.QtWidgets import QLabel

from ez_co.ui.main_window import MainWindow

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_missing_overlay_is_invalid():
    """ズーム表示ラベルが無いウィンドウを生存と見なす。"""
    assert MainWindow._is_zoom_overlay_valid(SimpleNamespace()) is False


def test_living_label_is_valid():
    """破棄前の QLabel を破棄済みと見なす。"""
    label = QLabel()
    fake = SimpleNamespace(_zoom_overlay_label=label)
    assert MainWindow._is_zoom_overlay_valid(fake) is True


def test_deleted_label_is_invalid():
    """shiboken で破棄したラベルを、まだ生存していると見なす。"""
    label = QLabel()
    fake = SimpleNamespace(_zoom_overlay_label=label)
    shiboken6.delete(label)
    assert MainWindow._is_zoom_overlay_valid(fake) is False


def test_hide_ignores_deleted_label():
    """破棄済みのズーム表示を隠すとき、削除済みオブジェクトへ触れて落ちる。"""
    label = QLabel()
    fake = SimpleNamespace(_zoom_overlay_label=label)
    fake._is_zoom_overlay_valid = lambda: MainWindow._is_zoom_overlay_valid(fake)
    shiboken6.delete(label)
    MainWindow._hide_zoom_overlay(fake)
