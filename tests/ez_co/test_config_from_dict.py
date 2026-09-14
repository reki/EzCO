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


def test_from_dict_fills_missing_sections():
    config = Config.from_dict({})
    assert "width" in config.window
    assert "extension_handlers" in config.plugins
