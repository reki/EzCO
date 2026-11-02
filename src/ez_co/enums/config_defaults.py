"""設定の初期値。生成後はメンバーも中の値も書き換えられない。"""
from enum import Enum


class ConfigDefault(Enum):
    """初期値を持つ列挙。同じ値でも別メンバーのままにする。"""

    def __new__(cls, value):
        """メンバーを作り、初期値を別枠に置く。

        Args:
            value: 初期値。

        Returns:
            まだ生成途中のメンバー。
        """
        member = object.__new__(cls)
        member._value_ = object()
        member._default = value
        return member

    def __init_subclass__(cls, **kwargs):
        """サブクラスのメンバーを、生成が終わったあとに閉じる。

        Args:
            **kwargs: Enum が渡す追加引数。
        """
        super().__init_subclass__(**kwargs)
        for member in cls:
            object.__setattr__(member, "_sealed", True)

    def __setattr__(self, name, value):
        """生成後の代入を拒否する。

        Args:
            name: 属性名。
            value: 代入する値。

        Raises:
            AttributeError: 生成後の代入。
        """
        if getattr(self, "_sealed", False):
            raise AttributeError("設定の初期値は変更できない")
        object.__setattr__(self, name, value)

    @property
    def default(self):
        """初期値を返す。

        Returns:
            生成時の値。
        """
        return self._default



class WindowDefaults(ConfigDefault):
    """ウィンドウ設定の初期値。"""

    # 起動時の幅。
    WIDTH = 800
    # 起動時の高さ。
    HEIGHT = 600
    # 起動時の左位置。
    X = 100
    # 起動時の上位置。
    Y = 100
    # 画像に合わせてウィンドウサイズを変える初期値。
    AUTO_RESIZE = False
    # 幅の下限。
    MIN_WIDTH = 400
    # 高さの下限。
    MIN_HEIGHT = 300
    # 最前面の初期値。
    ALWAYS_ON_TOP = False
    # 終了時にウィンドウ状態を保存する初期値。
    SAVE_WINDOW_STATE = True
    # 起動時に最大化する初期値。
    MAXIMIZE_ON_STARTUP = False
    # 前回最大化だったかの初期値。
    MAXIMIZED = False
    # ドック配置の初期値。
    DOCK_STATE = ""



class ViewerDefaults(ConfigDefault):
    """閲覧設定の初期値。"""

    # 画像の背景色。
    BACKGROUND_COLOR = "#c0ffc0"
    # ウィンドウに合わせる初期値。
    FIT_TO_WINDOW = False
    # 合わせたときの最小倍率を 100% にする初期値。
    FIT_TO_WINDOW_MINIMUM = True
    # マウスロックの初期値。
    MOUSE_LOCK = False
    # マウスロック中にカーソルを隠す初期値。
    MOUSE_LOCK_HIDE_CURSOR = True
    # 画像移動の感度。
    IMAGE_MOVE_SENSITIVITY = 2.0
    # ジェスチャーと判定する移動量。
    GESTURE_THRESHOLD = 50
    # 長押しの最初の間隔。
    MOUSE_REPEAT_INITIAL_DELAY = 100
    # 長押しの加速が始まる時刻。
    MOUSE_REPEAT_ACCELERATION_START = 100
    # 長押しの最短間隔。
    MOUSE_REPEAT_MIN_INTERVAL = 30
    # ページの並び。
    PAGE_MODE = "single"
    # 拡大中の移動。
    ZOOM_NAVIGATION_MODE = "page"
    # 両開きで選択ページを軸にする初期値。
    SPREAD_SELECTED_AS_AXIS = False
    # 両開きへ戻すときの向き。
    SPREAD_TOGGLE_PREFERENCE = "keep_previous"
    # 前回の両開き方向。
    LAST_SPREAD_MODE = "spread_right"
    # ドロップで新しいタブを開く初期値。
    DROP_OPENS_NEW_TAB = False
    # アーカイブを別タブで開く初期値。
    OPEN_ARCHIVES_IN_OWN_TAB = True
    # フォルダを別タブで開く初期値。
    OPEN_FOLDERS_IN_OWN_TAB = False
    # 全画面でもタブバーを出す初期値。
    SHOW_TABS_IN_FULLSCREEN = False
    # 全画面でもページスライダーを出す初期値。
    SHOW_PAGE_SLIDER_IN_FULLSCREEN = False
    # カレントタブの色。
    CURRENT_TAB_COLOR = "#d5822f"
    # カレントタブの透過度。
    CURRENT_TAB_ALPHA = 45
    # カレントタブを左から右へ薄くする初期値。
    CURRENT_TAB_GRADIENT = True



class CacheDefaults(ConfigDefault):
    """キャッシュ設定の初期値。"""

    # メモリ上限の表記。
    MEMORY_LIMIT = "256MB"
    # 先読みするページ数。
    PREFETCH_PAGES = 5
    # 大きい画像を縮小する初期値。
    OPTIMIZE_LARGE_IMAGES = True
    # 縮小を始めるサイズの表記。
    OPTIMIZE_THRESHOLD = "50MB"
    # 縮小後の長辺。
    OPTIMIZE_MAX_RESOLUTION = 4000



class HistoryDefaults(ConfigDefault):
    """履歴設定の初期値。"""

    # 履歴の件数。
    MAX_COUNT = 20
    # 開き直したときページを戻す初期値。
    RESTORE_PAGE_ON_REOPEN = False
    # 起動時に前回のファイルを開く初期値。
    OPEN_LAST_FILE_ON_STARTUP = False



class LanguageDefaults(ConfigDefault):
    """言語設定の初期値。"""

    # 表示言語。system は OS の言語。
    CODE = "system"



class DebugDefaults(ConfigDefault):
    """デバッグ設定の初期値。"""

    # デバッグ出力の初期値。
    ENABLED = False
    # アーカイブのハンドルを保持する初期値。
    KEEP_ARCHIVE_HANDLES = False
    # アーカイブのメタデータをキャッシュする初期値。
    CACHE_ARCHIVE_METADATA = True
    # エラーログを出す初期値。
    SHOW_ERROR_LOG = False



class UiFontDefaults(ConfigDefault):
    """ポップアップフォントの初期値。フォント名は言語から決める。"""

    # 文字サイズ。
    FONT_SIZE = 10
    # 文字色。
    FONT_COLOR = "#00008d"
    # 背景色。
    BG_COLOR = "#ffffff"
    # 透過度。
    ALPHA = 150



class ImageListDefaults(ConfigDefault):
    """画像一覧の初期値。"""

    # 選んだあと閉じる初期値。
    CLOSE_AFTER_SELECT = True
