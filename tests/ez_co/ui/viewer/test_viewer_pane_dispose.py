"""対象: ez_co.ui.viewer.viewer_pane"""

from ez_co.config import Config
from ez_co.ui.viewer.viewer_pane import ViewerPane


def test_dispose_closes_handler_once(qapp):
    pane = ViewerPane(Config())

    class Handler:
        def __init__(self):
            self.closed = 0

        def close(self):
            self.closed += 1

    handler = Handler()
    pane.file_handler = handler

    pane.dispose()
    pane.dispose()

    assert handler.closed == 1
    assert pane.file_handler is None
