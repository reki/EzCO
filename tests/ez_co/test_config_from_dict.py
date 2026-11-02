"""対象: ez_co.config — from_dict。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_from_dict_applies_viewer_and_plugins():
    """渡した背景色と閾値とソース選択が入り、拡張子は小文字のドット付きで none になる。"""
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
    """page、left、right のズーム移動は渡した値のまま残る。"""
    config = Config.from_dict({"viewer": {"zoom_navigation_mode": mode}})
    assert config.viewer["zoom_navigation_mode"] == mode


def test_from_dict_falls_back_for_invalid_zoom_navigation_mode():
    """知らないズーム移動は page に戻る。"""
    config = Config.from_dict({"viewer": {"zoom_navigation_mode": "vertical"}})
    assert config.viewer["zoom_navigation_mode"] == "page"


def test_from_dict_turns_a_missing_tab_gradient_on():
    """カレントタブのグラデーションは、キーが無いとオフになり、明示したオフがオンになる。"""
    missing = Config.from_dict({"viewer": {"current_tab_color": "#112233"}})
    off = Config.from_dict({"viewer": {"current_tab_gradient": False}})
    assert missing.viewer["current_tab_gradient"] is True
    assert off.viewer["current_tab_gradient"] is False


def test_from_dict_fills_missing_sections():
    """空の辞書でもウィンドウ幅と拡張子ハンドラが埋まり、フィルタ pipe は空で gamma は 1.0 になる。"""
    config = Config.from_dict({})
    assert "width" in config.window
    assert "extension_handlers" in config.plugins
    assert config.filters["pipe"] == []
    assert config.filters["settings"]["builtin:basic"]["gamma"] == 1.0


def test_from_dict_normalizes_filters_pipe_and_builtin_settings():
    """pipe は重複と空欄を落とし、builtin の不足項目は既定で埋まり、プラグイン設定は残さない。"""
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
