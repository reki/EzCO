from enum import Enum
from ez_co.utils.language_manager import get_text

class Actions(Enum):
    """アクション定数"""
    NEW_WINDOW = "new_window"
    OPEN_FILE_IN_NEW_TAB = "open_file_in_new_tab"
    OPEN_FOLDER = "open_folder"
    SAVE_SESSION = "save_session"
    NEW_TAB = "new_tab"
    CLOSE_TAB = "close_tab"
    REOPEN_CLOSED_TAB = "reopen_closed_tab"
    NEXT_TAB = "next_tab"
    PREV_TAB = "prev_tab"
    FIRST_TAB = "first_tab"
    LAST_TAB = "last_tab"
    SHOW_TAB_1 = "show_tab_1"
    SHOW_TAB_2 = "show_tab_2"
    SHOW_TAB_3 = "show_tab_3"
    SHOW_TAB_4 = "show_tab_4"
    SHOW_TAB_5 = "show_tab_5"
    SHOW_TAB_6 = "show_tab_6"
    SHOW_TAB_7 = "show_tab_7"
    SHOW_TAB_8 = "show_tab_8"
    SHOW_TAB_9 = "show_tab_9"
    CLOSE_APP = "close_app"
    NEXT_PAGE = "next_page"
    PREV_PAGE = "prev_page"
    FIRST_PAGE = "first_page"
    LAST_PAGE = "last_page"
    NEXT_FILE = "next_file"
    PREV_FILE = "prev_file"
    NEXT_COMIC = "next_comic"
    PREV_COMIC = "prev_comic"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    RESET_ZOOM = "reset_zoom"
    ROTATE_RIGHT = "rotate_right"
    ROTATE_LEFT = "rotate_left"
    FULLSCREEN = "fullscreen"
    MIN_SCALE_TOGGLE = "min_scale_toggle"
    IMAGE_LIST = "image_list"
    ALWAYS_ON_TOP = "always_on_top"
    REOPEN_LAST_FILE = "reopen_last_file"
    TOGGLE_BOOKMARK = "toggle_bookmark"
    TOGGLE_BOOKMARK_DOCK = "toggle_bookmark_dock"
    TOGGLE_HISTORY_DOCK = "toggle_history_dock"
    TOGGLE_IMAGE_SLIDE_DOCK = "toggle_image_slide_dock"
    TOGGLE_TAB_LIST_DOCK = "toggle_tab_list_dock"
    TOGGLE_MOUSE_LOCK = "toggle_mouse_lock"
    PAGE_SLIDER_DIALOG = "page_slider_dialog"
    IMAGE_SLIDE_SIDEBAR = "image_slide_sidebar"
    PAGE_MODE_SINGLE = "page_mode_single"
    PAGE_MODE_SPREAD_RIGHT = "page_mode_spread_right"
    PAGE_MODE_SPREAD_LEFT = "page_mode_spread_left"
    TOGGLE_SPREAD = "toggle_spread"
    ZOOM_NAVIGATION_PAGE = "zoom_navigation_page"
    ZOOM_NAVIGATION_LEFT = "zoom_navigation_left"
    ZOOM_NAVIGATION_RIGHT = "zoom_navigation_right"
    HOLD_MOUSE_LOCK = "hold_mouse_lock"


ACTION_LIST = [action.value for action in Actions]


def _plugin_host():
    try:
        from ez_co.plugins.manager import get_plugin_manager
        return get_plugin_manager().host
    except Exception:
        return None


def list_assignable_actions() -> list:
    """ショートカット／ジェスチャーに出せる本体 + 有効プラグインのアクション。"""
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
    """押下／解放が必要なアクションを除いたジェスチャー候補。"""
    return [action for action in list_assignable_actions() if action != Actions.HOLD_MOUSE_LOCK.value]


def list_bound_gesture_actions(assigned_ids) -> list:
    known = list_gesture_assignable_actions()
    seen = set(known)
    return known + [action for action in assigned_ids if action not in seen]


def find_action_by_display_name(text: str):
    for action in list_assignable_actions():
        if get_action_display_name(action) == text:
            return action
    return None


def find_gesture_action_by_display_name(text: str):
    for action in list_gesture_assignable_actions():
        if get_action_display_name(action) == text:
            return action
    return None


def is_known_action(action_name: str) -> bool:
    name = str(action_name or "")
    if not name:
        return False
    if name in ACTION_LIST or name in list_assignable_actions():
        return True
    host = _plugin_host()
    return host is not None and host.resolve_action(name) is not None


def list_bound_actions(assigned_ids) -> list:
    """割り当て済みを、候補順のあと未登録分を付けて返す。"""
    known = list_assignable_actions()
    seen = set(known)
    extra = [action for action in assigned_ids if action not in seen]
    return known + extra


_ACTION_TEXT_KEYS = {
    "close_app": "ui.exit",
    "zoom_navigation_page": "ui.zoom_navigation_page",
    "zoom_navigation_left": "ui.zoom_navigation_left",
    "zoom_navigation_right": "ui.zoom_navigation_right",
    "hold_mouse_lock": "ui.hold_mouse_lock",
}


def get_action_display_name(action_name: str) -> str:
    """アクションの表示名を取得"""
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
    """後方互換性のための辞書を取得（非推奨）"""
    return {action: get_action_display_name(action) for action in list_assignable_actions()}

ACTIONS = {action: get_action_display_name(action) for action in ACTION_LIST} 