"""EzCo 向け表示フィルターサンプル。

ホストは必ず次で生成する。
    ExampleFilterPlugin(root, get_text, host)

    root
        プラグイン ZIP 内のリソース。このサンプルでは使わない。
    get_text(key, **kwargs)
        プラグイン langs/{言語}.json を優先し、なければ本体の文言。
    host
        register_filter / register_config / get_config。
        ez_co は import しない。Host は process の context には入らない。

ホストが呼ぶもの:
    setup()
        台帳へフィルターを載せる。登録しただけでは process は呼ばれない。
        ユーザーがフィルターメニューで有効化した公開 ID だけが pipe に入る。
    teardown()
        任意。掃除の正は本体の clear_plugin。ここでも unregister しておく。

このサンプル固有:
    開いている画像に色とラベルを重ねる（本番では不要）。
    文字サイズは int_range。sync=True でスライダー操作後 0.5 秒アイドルして保存し、
    reload=True で本体が reload_current する。process から Config API で
    フィルター処理を呼ばない。値は get_config で読むだけ。
"""
from overlay import overlay_image

_FILTER_ID = "overlay"
_FONT_SIZE_KEY = "font_size"
_FONT_SIZE_DEFAULT = 36
_FONT_SIZE_MIN = 16
_FONT_SIZE_MAX = 96


class ExampleFilterPlugin:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        # 無効化してもスキーマは残るので __init__ で登録してよい。
        self.host.register_config(
            _FONT_SIZE_KEY,
            "int_range",
            default=_FONT_SIZE_DEFAULT,
            label=self.get_text("font_size"),
            description=self.get_text("font_size_help"),
            minimum=_FONT_SIZE_MIN,
            maximum=_FONT_SIZE_MAX,
            step=1,
            sync=True,
            reload=True,
        )

    def setup(self):
        # 公開 ID は plugin:com.ezco.example.filter:overlay
        self.host.register_filter(
            _FILTER_ID,
            self.get_text("filter_title"),
            self._overlay,
        )

    def teardown(self):
        self.host.unregister_filter(_FILTER_ID)

    def _overlay(self, image, context):
        # context は path / page / size。Host は入らない。
        # 原画キャッシュのオブジェクトは渡されない（working copy）。
        _ = context
        size = _font_size(self.host.get_config(_FONT_SIZE_KEY, _FONT_SIZE_DEFAULT))
        label = f"{self.get_text('watermark')}  {size}px"
        return overlay_image(image, label, size)


def _font_size(value):
    try:
        size = int(value)
    except (TypeError, ValueError):
        return _FONT_SIZE_DEFAULT
    return max(_FONT_SIZE_MIN, min(_FONT_SIZE_MAX, size))
