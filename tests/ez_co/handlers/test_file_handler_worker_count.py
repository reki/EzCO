"""対象: ez_co.handlers.file_handler"""
import pytest

from ez_co.config import Config
from ez_co.handlers.file_handler import FileHandler


pytestmark = pytest.mark.usefixtures("qapp")


def test_multiple_handlers_share_process_fixed_effective_worker_count():
    """起動時に固めた実効ワーカー数は、その後の設定変更後に作ったハンドラも含め全員が同じになる。"""
    config = Config()
    config.cache["image_loader_workers"] = 4
    config.freeze_image_loader_workers(logical_cpu_count=40)
    handlers = []
    try:
        handlers.append(FileHandler(config))
        handlers.append(FileHandler(config))
        config.cache["image_loader_workers"] = 8
        handlers.append(FileHandler(config))

        assert [
            handler._scheduler.snapshot()["worker_count"]
            for handler in handlers
        ] == [4, 4, 4]
    finally:
        for handler in handlers:
            handler.close()
