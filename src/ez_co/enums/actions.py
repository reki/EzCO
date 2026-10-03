"""操作アクションの定数と割り当て候補。"""
from enum import Enum
from ez_co.utils.language_manager import get_text

class Actions(Enum):
    """アクション定数"""
    # 新しいウィンドウを開くアクション
    NEW_WINDOW = "new_window"
    # 新しいタブでファイルを開くアクション
    OPEN_FILE_IN_NEW_TAB = "open_file_in_new_tab"
    # フォルダを開くアクション
    OPEN_FOLDER = "open_folder"
    # セッションを保存するアクション
    SAVE_SESSION = "save_session"
    # 新しいタブを開くアクション
    NEW_TAB = "new_tab"
    # タブを閉じるアクション
    CLOSE_TAB = "close_tab"
    # 閉じたタブを開き直すアクション
    REOPEN_CLOSED_TAB = "reopen_closed_tab"
    # 次のタブへ移るアクション
    NEXT_TAB = "next_tab"
    # 前のタブへ移るアクション
    PREV_TAB = "prev_tab"
    # 先頭のタブへ移るアクション
    FIRST_TAB = "first_tab"
    # 末尾のタブへ移るアクション
    LAST_TAB = "last_tab"
    # 1番目のタブを表示するアクション
    SHOW_TAB_1 = "show_tab_1"
    # 2番目のタブを表示するアクション
    SHOW_TAB_2 = "show_tab_2"
    # 3番目のタブを表示するアクション
    SHOW_TAB_3 = "show_tab_3"
    # 4番目のタブを表示するアクション
    SHOW_TAB_4 = "show_tab_4"
    # 5番目のタブを表示するアクション
    SHOW_TAB_5 = "show_tab_5"
    # 6番目のタブを表示するアクション
    SHOW_TAB_6 = "show_tab_6"
    # 7番目のタブを表示するアクション
    SHOW_TAB_7 = "show_tab_7"
    # 8番目のタブを表示するアクション
    SHOW_TAB_8 = "show_tab_8"
    # 9番目のタブを表示するアクション
    SHOW_TAB_9 = "show_tab_9"
    # アプリを終了するアクション
    CLOSE_APP = "close_app"
    # 次のページへ移るアクション
    NEXT_PAGE = "next_page"
    # 前のページへ移るアクション
    PREV_PAGE = "prev_page"
    # 先頭ページへ移るアクション
    FIRST_PAGE = "first_page"
    # 末尾ページへ移るアクション
    LAST_PAGE = "last_page"
    # 次のファイルへ移るアクション
    NEXT_FILE = "next_file"
    # 前のファイルへ移るアクション
    PREV_FILE = "prev_file"
    # 次のコミックへ移るアクション
    NEXT_COMIC = "next_comic"
    # 前のコミックへ移るアクション
    PREV_COMIC = "prev_comic"
    # 拡大するアクション
    ZOOM_IN = "zoom_in"
    # 縮小するアクション
    ZOOM_OUT = "zoom_out"
    # 倍率を戻すアクション
    RESET_ZOOM = "reset_zoom"
    # 右へ回転するアクション
    ROTATE_RIGHT = "rotate_right"
    # 左へ回転するアクション
    ROTATE_LEFT = "rotate_left"
    # 全画面を切り替えるアクション
    FULLSCREEN = "fullscreen"
    # 最小表示を切り替えるアクション
    MIN_SCALE_TOGGLE = "min_scale_toggle"
    # 画像一覧を開くアクション
    IMAGE_LIST = "image_list"
    # 最前面表示を切り替えるアクション
    ALWAYS_ON_TOP = "always_on_top"
    # 最後に開いたファイルを開き直すアクション
    REOPEN_LAST_FILE = "reopen_last_file"
    # ブックマークを切り替えるアクション
    TOGGLE_BOOKMARK = "toggle_bookmark"
    # ブックマーク欄の表示を切り替えるアクション
    TOGGLE_BOOKMARK_DOCK = "toggle_bookmark_dock"
    # 履歴欄の表示を切り替えるアクション
    TOGGLE_HISTORY_DOCK = "toggle_history_dock"
    # 画像スライド欄の表示を切り替えるアクション
    TOGGLE_IMAGE_SLIDE_DOCK = "toggle_image_slide_dock"
    # タブ一覧欄の表示を切り替えるアクション
    TOGGLE_TAB_LIST_DOCK = "toggle_tab_list_dock"
    # マウスロックを切り替えるアクション
    TOGGLE_MOUSE_LOCK = "toggle_mouse_lock"
    # ページスライダーを開くアクション
    PAGE_SLIDER_DIALOG = "page_slider_dialog"
    # 画像スライドのサイドバーを開くアクション
    IMAGE_SLIDE_SIDEBAR = "image_slide_sidebar"
    # 単ページ表示にするアクション
    PAGE_MODE_SINGLE = "page_mode_single"
    # 右開きの見開きにするアクション
    PAGE_MODE_SPREAD_RIGHT = "page_mode_spread_right"
    # 左開きの見開きにするアクション
    PAGE_MODE_SPREAD_LEFT = "page_mode_spread_left"
    # 見開きを切り替えるアクション
    TOGGLE_SPREAD = "toggle_spread"
    # 拡大中の移動をページ単位にするアクション
    ZOOM_NAVIGATION_PAGE = "zoom_navigation_page"
    # 拡大中の移動を左方向にするアクション
    ZOOM_NAVIGATION_LEFT = "zoom_navigation_left"
    # 拡大中の移動を右方向にするアクション
    ZOOM_NAVIGATION_RIGHT = "zoom_navigation_right"
    # マウスロックを押しているあいだ保つアクション
    HOLD_MOUSE_LOCK = "hold_mouse_lock"


# 旧アクション ID から現在の ID への対応
LEGACY_ACTION_ALIASES = {
    Actions.TOGGLE_IMAGE_SLIDE_DOCK.value: Actions.IMAGE_SLIDE_SIDEBAR.value,
}

# 割り当てに使う現在のアクション ID
ACTION_LIST = [
    action.value for action in Actions
    if action.value not in LEGACY_ACTION_ALIASES
]


def canonical_action_id(action_name: str) -> str:
    """旧アクション名を現在の ID に揃える。

    Args:
        action_name: 調べるアクション名。

    Returns:
        別名があれば対応する ID。無ければ渡された名前。空なら空文字。
    """
    name = str(action_name or "")
    return LEGACY_ACTION_ALIASES.get(name, name)


def _plugin_host():
    """プラグインマネージャの host を返す。

    Returns:
        取得できれば host。失敗すれば None。
    """
    try:
        from ez_co.plugins.manager import get_plugin_manager
        return get_plugin_manager().host
    except Exception:
        # プラグインマネージャを取れなければ None を返す
        return None


def list_assignable_actions() -> list:
    """ショートカット／ジェスチャーに出せる本体と有効プラグインのアクションを返す。

    Returns:
        プラグインの別名と重ならない本体 ID のあとに、プラグインの公開 ID を続けた列。
    """
    host = _plugin_host()
    plugin_ids = []
    aliased = set()
    if host is not None:
        for item in host.list_actions():
            plugin_ids.append(item.public_id)
            aliased.update(item.aliases)
    builtin = [action for action in ACTION_LIST if action not in aliased]
    return builtin + plugin_ids


def list_gesture_assignable_actions() -> list:
    """押下／解放が必要なアクションを除いたジェスチャー候補を返す。

    Returns:
        ジェスチャーに割り当てられるアクション。
    """
    return [action for action in list_assignable_actions() if action != Actions.HOLD_MOUSE_LOCK.value]


def list_bound_gesture_actions(assigned_ids) -> list:
    """ジェスチャー候補のあとに、未登録の割り当て済みを付けて返す。

    Args:
        assigned_ids: すでに割り当てられているアクション ID。

    Returns:
        候補の列に、その中に無い割り当て済み ID を続けた列。
    """
    known = list_gesture_assignable_actions()
    seen = set(known)
    return known + [action for action in assigned_ids if action not in seen]


def find_action_by_display_name(text: str):
    """表示名が一致する割り当て可能アクションを返す。

    Args:
        text: 比較する表示名。

    Returns:
        一致したアクション ID。無ければ None。
    """
    for action in list_assignable_actions():
        if get_action_display_name(action) == text:
            return action
    return None


def find_gesture_action_by_display_name(text: str):
    """表示名が一致するジェスチャー候補を返す。

    Args:
        text: 比較する表示名。

    Returns:
        一致したアクション ID。無ければ None。
    """
    for action in list_gesture_assignable_actions():
        if get_action_display_name(action) == text:
            return action
    return None


def is_known_action(action_name: str) -> bool:
    """既知のアクションかどうかを返す。

    Args:
        action_name: 調べるアクション名。

    Returns:
        空でなく、別名、本体一覧、割り当て候補、プラグイン解決のいずれかに当たれば True。
    """
    name = str(action_name or "")
    if not name:
        return False
    if name in LEGACY_ACTION_ALIASES or name in ACTION_LIST or name in list_assignable_actions():
        return True
    host = _plugin_host()
    return host is not None and host.resolve_action(name) is not None


def list_bound_actions(assigned_ids) -> list:
    """割り当て済みを、候補順のあと未登録分を付けて返す。

    Args:
        assigned_ids: すでに割り当てられているアクション ID。

    Returns:
        割り当て候補のあとに、その中に無い割り当て済み ID を続けた列。
    """
    known = list_assignable_actions()
    seen = set(known)
    extra = [action for action in assigned_ids if action not in seen]
    return known + extra


# 表示名が actions. 以外になる文言キー
_ACTION_TEXT_KEYS = {
    "close_app": "ui.exit",
    "zoom_navigation_page": "ui.zoom_navigation_page",
    "zoom_navigation_left": "ui.zoom_navigation_left",
    "zoom_navigation_right": "ui.zoom_navigation_right",
    "hold_mouse_lock": "ui.hold_mouse_lock",
}


def get_action_display_name(action_name: str) -> str:
    """アクションの表示名を取得する。

    Args:
        action_name: 表示名を引くアクション名。

    Returns:
        プラグインのラベルがあればそれ。無ければ画面文言。
    """
    action_name = canonical_action_id(action_name)
    host = _plugin_host()
    if host is not None:
        label = host.action_label(action_name)
        if label:
            return label
    preferred = _ACTION_TEXT_KEYS.get(action_name, f"ui.{action_name}")
    text = get_text(preferred)
    if text != preferred:
        return text
    return get_text(f"actions.{action_name}")


# 後方互換性のための辞書（非推奨）
def get_actions_dict():
    """後方互換性のための辞書を取得する（非推奨）。

    Returns:
        割り当て可能アクションから表示名への辞書。
    """
    return {action: get_action_display_name(action) for action in list_assignable_actions()}

# アクション ID から表示名への対応
ACTIONS = {action: get_action_display_name(action) for action in ACTION_LIST}
