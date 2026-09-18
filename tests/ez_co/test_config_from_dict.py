"""対象: ez_co.config — from_dict。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_from_dict_applies_viewer_and_plugins():
    config = Config.from_dict(
        {
            "viewer": {"background_color": "#112233", "gesture_threshold": 80},
            "plugins": {
                "source_choice": {
                    "com.example.x": {"source": "one", "seen": ["one", "two"]},
                },
                "extension_handlers": {"PNG": "none"},
            },
        }
    )
    assert config.viewer["background_color"] == "#112233"
    assert config.viewer["gesture_threshold"] == 80
    assert config.plugins["source_choice"]["com.example.x"]["source"] == "one"
    assert config.plugins["extension_handlers"][".png"] == "none"


@pytest.mark.parametrize("mode", ["page", "left", "right"])
def test_from_dict_keeps_zoom_navigation_mode(mode):
    config = Config.from_dict({"viewer": {"zoom_navigation_mode": mode}})
    assert config.viewer["zoom_navigation_mode"] == mode


def test_from_dict_falls_back_for_invalid_zoom_navigation_mode():
    config = Config.from_dict({"viewer": {"zoom_navigation_mode": "vertical"}})
    assert config.viewer["zoom_navigation_mode"] == "page"


def test_from_dict_fills_missing_sections():
    config = Config.from_dict({})
    assert "width" in config.window
    assert "extension_handlers" in config.plugins
    assert config.filters["pipe"] == []
    assert config.filters["settings"]["builtin:basic"]["gamma"] == 1.0


def test_from_dict_normalizes_filters_pipe_and_builtin_settings():
    config = Config.from_dict(
        {
            "filters": {
                "pipe": ["builtin:basic", "builtin:basic", "plugin:com.example.x:sharp", ""],
                "settings": {
                    "builtin:basic": {"brightness": 12, "gamma": 1},
                    "plugin:com.example.x:sharp": {"amount": 3},
                },
            }
        }
    )
    assert config.filters["pipe"] == ["builtin:basic", "plugin:com.example.x:sharp"]
    assert config.filters["settings"]["builtin:basic"]["brightness"] == 12
    assert config.filters["settings"]["builtin:basic"]["contrast"] == 0
    assert config.filters["settings"]["builtin:basic"]["gamma"] == 1.0
    assert "plugin:com.example.x:sharp" not in config.filters["settings"]
