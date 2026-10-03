"""対象: ez_co.filters.pipeline — 空 pipe と identity は同一オブジェクト。"""
from PIL import Image

from ez_co.filters.builtin import BUILTIN_FILTER_ID, register_builtin
from ez_co.filters.pipeline import apply_pipe
from ez_co.filters.registry import FilterRecord, FilterRegistry


def _image():
    """比較用の小さな RGB 画像を作る。

    Returns:
        単色の RGB 画像。
    """
    return Image.new("RGB", (4, 4), (10, 20, 30))


def test_empty_pipe_returns_same_object():
    """空の pipe は登録済みフィルタを呼ばず、渡した画像そのものを返す。"""
    image = _image()
    registry = FilterRegistry()
    calls = []

    def process(current, context):
        """呼び出しを数えて、受け取った画像をそのまま返す。

        Args:
            current: 処理中の画像。
            context: フィルタのコンテキスト。

        Returns:
            受け取った画像。
        """
        calls.append(1)
        return current

    registry.register(
        FilterRecord("plugin:com.example.x:sharp", "com.example.x", "sharp", "Sharp", process)
    )
    result = apply_pipe(image, [], registry=registry)
    assert result is image
    assert calls == []


def test_process_outside_pipe_is_not_called():
    """pipe に無い ID では process を呼ばず、渡した画像そのものを返す。"""
    image = _image()
    registry = FilterRegistry()
    calls = []

    def process(current, context):
        """呼び出しを数えて、受け取った画像をそのまま返す。

        Args:
            current: 処理中の画像。
            context: フィルタのコンテキスト。

        Returns:
            受け取った画像。
        """
        calls.append(1)
        return current

    registry.register(
        FilterRecord("plugin:com.example.x:sharp", "com.example.x", "sharp", "Sharp", process)
    )
    result = apply_pipe(image, ["plugin:com.example.x:other"], registry=registry)
    assert result is image
    assert calls == []


def test_unregistered_pipe_ids_do_not_copy():
    """未登録 ID だけの pipe はコピーせず、渡した画像そのものを返す。"""
    image = _image()
    result = apply_pipe(image, ["plugin:missing:x"], registry=FilterRegistry())
    assert result is image


def test_builtin_identity_only_does_not_copy():
    """既定の builtin だけならコピーせず、渡した画像そのものを返す。"""
    image = _image()
    registry = FilterRegistry()
    register_builtin(registry)
    result = apply_pipe(
        image,
        [BUILTIN_FILTER_ID],
        builtin_settings={
            "brightness": 0,
            "contrast": 0,
            "gamma": 1.0,
            "grayscale": False,
        },
        registry=registry,
    )
    assert result is image
