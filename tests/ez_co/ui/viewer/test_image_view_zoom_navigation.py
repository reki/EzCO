"""対象: ez_co.ui.viewer.image_view — 拡大時の読書順ナビゲーション。"""
import pytest
from PIL import Image
from PySide6.QtCore import QPoint, QSize

from ez_co.config import Config
from ez_co.ui.viewer.image_view import ImageView

pytestmark = pytest.mark.usefixtures("qapp")


def _walk(mode: str):
    current = QPoint(-900 if mode == "left" else 900, 700)
    positions = [QPoint(current)]
    while True:
        target = ImageView.calculate_zoom_navigation_offset(
            current, 900, 700, 800, 600, mode, "next"
        )
        if target is None:
            return positions
        positions.append(target)
        current = target


def test_left_mode_moves_across_then_down():
    positions = _walk("left")
    assert positions[:5] == [
        QPoint(-900, 700),
        QPoint(-100, 700),
        QPoint(700, 700),
        QPoint(900, 700),
        QPoint(-900, 100),
    ]
    assert positions[-1] == QPoint(900, -700)


def test_right_mode_is_horizontally_mirrored():
    left = _walk("left")
    right = _walk("right")
    assert right == [QPoint(-point.x(), point.y()) for point in left]


@pytest.mark.parametrize("mode", ["left", "right"])
def test_previous_follows_the_complete_sequence_in_reverse(mode):
    positions = _walk(mode)
    current = QPoint(positions[-1])
    reversed_positions = [QPoint(current)]
    while True:
        target = ImageView.calculate_zoom_navigation_offset(
            current, 900, 700, 800, 600, mode, "previous"
        )
        if target is None:
            break
        reversed_positions.append(target)
        current = target
    assert reversed_positions == list(reversed(positions))


def test_exact_fit_does_not_pan():
    assert (
        ImageView.calculate_zoom_navigation_offset(
            QPoint(), 0, 0, 800, 600, "left", "next"
        )
        is None
    )


def test_geometry_uses_rotated_display_coordinates():
    view = ImageView(config=Config())
    displayed, max_x, max_y = view._zoom_navigation_geometry(
        QSize(1200, 800), QSize(800, 600), 2.0, 90
    )
    assert displayed == QSize(800, 1200)
    assert (max_x, max_y) == (0, 300)


def test_one_pixel_remainder_is_clamped_to_edge():
    assert ImageView._axis_positions(0, 801, 800) == [0, 800, 801]


@pytest.mark.parametrize(
    ("mode", "start", "end"),
    [
        ("left", QPoint(-900, 0), QPoint(900, 0)),
        ("right", QPoint(900, 0), QPoint(-900, 0)),
    ],
)
def test_horizontal_only_reaches_edge_before_page_turn(mode, start, end):
    current = QPoint(start)
    while True:
        target = ImageView.calculate_zoom_navigation_offset(
            current, 900, 0, 800, 600, mode, "next"
        )
        if target is None:
            break
        current = target
    assert current == end


@pytest.mark.parametrize("mode", ["left", "right"])
def test_vertical_only_moves_top_to_bottom(mode):
    current = QPoint(0, 700)
    positions = [QPoint(current)]
    while True:
        target = ImageView.calculate_zoom_navigation_offset(
            current, 0, 700, 800, 600, mode, "next"
        )
        if target is None:
            break
        positions.append(target)
        current = target
    assert positions == [
        QPoint(0, 700),
        QPoint(0, 100),
        QPoint(0, -500),
        QPoint(0, -700),
    ]


@pytest.mark.parametrize(
    ("mode", "direction", "expected"),
    [
        ("left", "next", QPoint(-100, 200)),
        ("left", "previous", QPoint(100, -200)),
        ("right", "next", QPoint(100, 200)),
        ("right", "previous", QPoint(-100, -200)),
    ],
)
def test_page_transition_starts_at_reading_order_corner(
    monkeypatch, mode, direction, expected
):
    config = Config()
    config.viewer["zoom_navigation_mode"] = mode
    view = ImageView(config=config)
    monkeypatch.setattr(
        view, "_zoom_navigation_geometry", lambda *args, **kwargs: (QSize(1000, 1000), 100, 200)
    )
    monkeypatch.setattr(view, "update_image_display", lambda: None)
    view.zoom_factor = 2.0
    view.prepare_page_transition(direction)
    view.set_image(Image.new("RGB", (10, 10)))
    assert view.image_offset == expected
    assert view._pending_zoom_navigation_direction is None


def test_pending_transition_is_consumed_once_and_does_not_leak_to_jump(monkeypatch):
    config = Config()
    config.viewer["zoom_navigation_mode"] = "left"
    view = ImageView(config=config)
    monkeypatch.setattr(
        view, "_zoom_navigation_geometry", lambda *args, **kwargs: (QSize(1000, 1000), 100, 200)
    )
    monkeypatch.setattr(view, "update_image_display", lambda: None)
    view.zoom_factor = 2.0

    view.prepare_page_transition("previous")
    view.set_image(Image.new("RGB", (10, 10)))
    assert view.image_offset == QPoint(100, -200)

    view.image_offset = QPoint(12, 34)
    view.set_image(Image.new("RGB", (20, 20)))
    assert view.image_offset == QPoint(12, 34)

    view.prepare_page_transition("next")
    view.cancel_pending_zoom_navigation()
    view.image_offset = QPoint(56, 78)
    view.set_image(Image.new("RGB", (30, 30)))
    assert view.image_offset == QPoint(56, 78)
