"""対象: ez_co.ui.viewer.viewer_pane"""

from ez_co.config import Config
from ez_co.ui.viewer.viewer_pane import ViewerPane


def test_dispose_closes_handler_once(qapp):
    """dispose を二度呼ぶと close が二回になる、または handler 参照が残る。"""
    pane = ViewerPane(Config())

    class Handler:
        """close の回数を数える file handler の代わり。"""

        def __init__(self):
            """close 回数を 0 にする。"""
            self.closed = 0

        def close(self):
            """close が呼ばれた回数を増やす。"""
            self.closed += 1

    handler = Handler()
    pane.file_handler = handler

    pane.dispose()
    pane.dispose()

    assert handler.closed == 1
    assert pane.file_handler is None
