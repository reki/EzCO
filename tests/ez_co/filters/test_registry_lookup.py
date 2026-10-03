"""対象: ez_co.filters.registry — ビルドイン ID もプラグイン ID も同じ get / apply。"""
from PIL import Image

from ez_co.filters.builtin import BUILTIN_FILTER_ID, register_builtin
from ez_co.filters.pipeline import apply_pipe
from ez_co.filters.registry import FilterRecord, FilterRegistry


def test_builtin_and_plugin_ids_share_lookup_and_apply():
    """組み込み ID とプラグイン ID は同じ get で引け、両方を通すと原画は残して結果の左上だけ赤になる。"""
    registry = FilterRegistry()
    register_builtin(registry)

    def mark(image, context):
        """左上の画素を赤にする。

        Args:
            image: 印を付ける画像。
            context: フィルタのコンテキスト。

        Returns:
            印を付けた画像。
        """
        image.putpixel((0, 0), (255, 0, 0))
        return image

    plugin_id = "plugin:com.example.x:mark"
    registry.register(FilterRecord(plugin_id, "com.example.x", "mark", "Mark", mark))
    assert registry.get(BUILTIN_FILTER_ID).public_id == BUILTIN_FILTER_ID
    assert registry.get(plugin_id).plugin_id == "com.example.x"
    image = Image.new("RGB", (2, 2), (0, 0, 0))
    result = apply_pipe(
        image,
        [BUILTIN_FILTER_ID, plugin_id],
        builtin_settings={"brightness": 0, "contrast": 0, "gamma": 1.0, "grayscale": False},
        registry=registry,
    )
    assert result is not image
    assert result.getpixel((0, 0)) == (255, 0, 0)
    assert image.getpixel((0, 0)) == (0, 0, 0)
