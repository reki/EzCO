"""対象: ez_co.ui.main_window — 旧アクションIDの実行互換。"""
from ez_co.ui.main_window import MainWindow


class _Window:
    plugin_session = None

    def __init__(self):
        self.called = []

    def toggle_image_slide_dock(self):
        self.called.append("image_slide_sidebar")

    def __getattr__(self, _name):
        return lambda *args, **kwargs: None


def test_legacy_image_slide_action_runs_canonical_handler():
    window = _Window()
    assert MainWindow.run_window_action(window, "toggle_image_slide_dock")
    assert window.called == ["image_slide_sidebar"]
