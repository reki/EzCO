"""対象: ez_co.ui.main_window — 旧アクションIDの実行互換。"""
from ez_co.ui.main_window import MainWindow


class _Window:
    """旧アクション ID の実行先になるウィンドウの代わり。"""

    # プラグインセッションを持たない。
    plugin_session = None

    def __init__(self):
        """実行された操作名の列を空にする。"""
        self.called = []

    def toggle_image_slide_dock(self):
        """正規のサイドバー操作として記録する。"""
        self.called.append("image_slide_sidebar")

    def __getattr__(self, _name):
        """未定義の操作は何もしない関数として返す。

        Args:
            _name: 探した属性名。

        Returns:
            引数を捨てる呼び出し可能。
        """
        return lambda *args, **kwargs: None


def test_legacy_image_slide_action_runs_canonical_handler():
    """旧 ID が正規のサイドバー操作に届かず、実行結果が成功にならない。"""
    window = _Window()
    assert MainWindow.run_window_action(window, "toggle_image_slide_dock")
    assert window.called == ["image_slide_sidebar"]
