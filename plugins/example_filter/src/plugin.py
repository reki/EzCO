"""EzCo 向け表示フィルターサンプル。

ホストは Class() のあと load(root, get_text, host) を渡す。

    root
        プラグイン ZIP 内のリソース。このサンプルでは使わない。
    get_text(key, **kwargs)
        プラグイン resources/langs/{言語}.json を優先し、なければ本体の文言。
    host
        register_filter / register_config_json / get_config。
        ez_co は import しない。Host は process の context には入らない。

ホストが呼ぶもの:
    load(root, get_text, host)
        引数を保持する。register_config_json はここでよい。
    setup()
        台帳へフィルターを載せる。登録しただけでは process は呼ばれない。
        ユーザーがフィルターメニューで有効化した公開 ID だけが pipe に入る。
    teardown()
        任意。sidebar / action / listener / filter 台帳は本体の clear_plugin が外す。
        ここには QThread や timer など所有物だけ書く。off / unregister は書かない。

このサンプル固有:
    開いている画像に色とラベルを重ねる（本番では不要）。
    文字サイズは int_range。sync=True でスライダー操作後 0.5 秒アイドルして保存し、
    reload=True で本体が reload_current する。process から Config API で
    フィルター処理を呼ばない。値は get_config で読むだけ。
"""
from overlay import overlay_image

# このフィルターのローカル ID。
_FILTER_ID = "overlay"
# フォントサイズ設定のキー。
_FONT_SIZE_KEY = "font_size"
# フォントサイズの既定。
_FONT_SIZE_DEFAULT = 36
# フォントサイズの下限。
_FONT_SIZE_MIN = 16
# フォントサイズの上限。
_FONT_SIZE_MAX = 96


class ExampleFilterPlugin:
    """表示中の画像に色とラベルを重ねるフィルター。"""

    def __init__(self):
        """root、get_text、host の入れ物を空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None

    def load(self, root, get_text, host):
        """引数を保持し、設定 JSON を登録する。

        Args:
            root: プラグインルート。このサンプルでは使わない。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
        self.root = root
        self.get_text = get_text
        self.host = host
        # 無効化してもスキーマは残るので load で登録してよい。
        self.host.register_config_json("fields.json")

    def setup(self):
        """overlay フィルターを台帳へ登録する。"""
        # 公開 ID は plugin:com.ezco.example.filter:overlay
        self.host.register_filter(
            _FILTER_ID,
            "{filter_title}",
            self._overlay,
        )

    def _overlay(self, image, context):
        """設定の文字サイズでラベルを重ねた画像を返す。

        Args:
            image: 加工する画像。
            context: path、page、size。加工には使わない。

        Returns:
            色とラベルを重ねた画像。
        """
        # context は path / page / size。Host は入らない。
        # 原画キャッシュのオブジェクトは渡されない（working copy）。
        _ = context
        size = _font_size(self.host.get_config(_FONT_SIZE_KEY, _FONT_SIZE_DEFAULT))
        label = f"{self.get_text('watermark')}  {size}px"
        return overlay_image(image, label, size)


def _font_size(value):
    """設定値をフォントサイズの上下限に収める。

    Args:
        value: 設定値。

    Returns:
        範囲内の整数。整数にできなければ既定。
    """
    try:
        size = int(value)
    except (TypeError, ValueError):
        # 整数にできなければ既定サイズを返す。
        return _FONT_SIZE_DEFAULT
    return max(_FONT_SIZE_MIN, min(_FONT_SIZE_MAX, size))
