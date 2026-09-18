"""対象: ez_co.ui.viewer.image_view — ジェスチャーのウィンドウアクション委譲。"""
from ez_co.config import Config
from ez_co.ui.viewer.image_view import ImageView


def test_reopen_last_file_gesture_delegates_to_window(qapp, monkeypatch):
    called = []
    view = ImageView(config=Config())

    class _Window:
        def run_window_action(self, action):
            called.append(action)
            return True

    monkeypatch.setattr(view, "window", lambda: _Window())
    view._fire_action("reopen_last_file")
    assert called == ["reopen_last_file"]
