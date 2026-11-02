"""対象: ez_co.ui.viewer.image_view — サイズが付いてからの画像表示。"""
import pytest
from PIL import Image
from PySide6.QtCore import Qt

from ez_co.ui.viewer.image_view import ImageView

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


def test_pixmap_appears_after_the_label_gets_a_size(qapp):
    """サイズ0で表示更新を抜けると、ラベルにサイズが付いても画像が空のままになる。"""
    view = ImageView()
    view.image_label.setFixedSize(0, 0)
    view.set_image(Image.new("RGB", (8, 8), "red"))
    empty = view.image_label.pixmap()
    assert empty is None or empty.isNull()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    view.image_label.setFixedSize(80, 60)
    view.resize(120, 100)
    view.show()
    qapp.processEvents()
    shown = view.image_label.pixmap()
    assert shown is not None and not shown.isNull()


def test_large_image_does_not_lock_minimum_size(qapp):
    """大きい画像を出すと、面の最小幅か最小高さが今の面より小さくならない。"""
    view = ImageView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    view.resize(400, 300)
    view.show()
    qapp.processEvents()
    view.set_image(Image.new("RGB", (1800, 2400), "red"))
    qapp.processEvents()
    hint = view.minimumSizeHint()
    assert hint.width() < view.width()
    assert hint.height() < view.height()
    assert hint.width() < 1800
    assert hint.height() < 2400
