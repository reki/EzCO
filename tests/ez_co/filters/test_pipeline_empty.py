"""対象: ez_co.filters.pipeline — 空 pipe と identity は同一オブジェクト。"""
from PIL import Image

from ez_co.filters.builtin import BUILTIN_FILTER_ID, register_builtin
from ez_co.filters.pipeline import apply_pipe
from ez_co.filters.registry import FilterRecord, FilterRegistry


def _image():
    return Image.new("RGB", (4, 4), (10, 20, 30))


def test_empty_pipe_returns_same_object():
    image = _image()
    registry = FilterRegistry()
    calls = []

    def process(current, context):
        calls.append(1)
        return current

    registry.register(
        FilterRecord("plugin:com.example.x:sharp", "com.example.x", "sharp", "Sharp", process)
    )
    result = apply_pipe(image, [], registry=registry)
    assert result is image
    assert calls == []


def test_process_outside_pipe_is_not_called():
    image = _image()
    registry = FilterRegistry()
    calls = []

    def process(current, context):
        calls.append(1)
        return current

    registry.register(
        FilterRecord("plugin:com.example.x:sharp", "com.example.x", "sharp", "Sharp", process)
    )
    result = apply_pipe(image, ["plugin:com.example.x:other"], registry=registry)
    assert result is image
    assert calls == []


def test_unregistered_pipe_ids_do_not_copy():
    image = _image()
    result = apply_pipe(image, ["plugin:missing:x"], registry=FilterRegistry())
    assert result is image


def test_builtin_identity_only_does_not_copy():
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
