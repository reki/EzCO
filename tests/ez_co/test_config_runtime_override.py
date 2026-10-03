"""対象: ez_co.config — ランタイムオーバーライド。"""
import pytest

from ez_co.config import Config

pytestmark = pytest.mark.usefixtures("qapp")


def test_runtime_override_wins_on_read_not_to_dict():
    """実行中オーバーライドは読み取りでは 12 になり、保存辞書は元の閾値のまま。"""
    config = Config()
    original = config.viewer["gesture_threshold"]
    config.set_runtime_override("viewer.gesture_threshold", 12)
    assert config.viewer["gesture_threshold"] == 12
    assert config.is_runtime_overridden("viewer.gesture_threshold") is True
    assert config.to_dict()["viewer"]["gesture_threshold"] == original
