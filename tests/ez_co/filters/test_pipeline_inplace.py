"""対象: ez_co.filters.pipeline — process の in-place でも原画は変わらない。"""
from PIL import Image

from ez_co.filters.pipeline import apply_pipe
from ez_co.filters.registry import FilterRecord, FilterRegistry


def test_inplace_process_does_not_mutate_original():
    """process が受け取った画像を塗っても、渡した原画の画素は残り、結果だけが塗られる。"""
    original = Image.new("RGB", (4, 4), (1, 2, 3))
    snapshot = list(original.getdata())
    registry = FilterRegistry()

    def mutate(image, context):
        """画像全体を単色で塗り替える。

        Args:
            image: 塗り替える画像。
            context: フィルタのコンテキスト。

        Returns:
            塗り替えた画像。
        """
        image.paste((9, 9, 9), (0, 0, 4, 4))
        return image

    registry.register(
        FilterRecord("plugin:com.example.x:fill", "com.example.x", "fill", "Fill", mutate)
    )
    result = apply_pipe(original, ["plugin:com.example.x:fill"], registry=registry)
    assert result is not original
    assert list(original.getdata()) == snapshot
    assert list(result.getdata()) == [(9, 9, 9)] * 16
