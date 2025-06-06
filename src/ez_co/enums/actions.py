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
    TOGGLE_PRODUCT_INFO_DOCK = "toggle_product_info_dock"
    TOGGLE_TAB_LIST_DOCK = "toggle_tab_list_dock"
    TOGGLE_MOUSE_LOCK = "toggle_mouse_lock"
    PAGE_SLIDER_DIALOG = "page_slider_dialog"
    IMAGE_SLIDE_SIDEBAR = "image_slide_sidebar"
    PAGE_MODE_SINGLE = "page_mode_single"
    PAGE_MODE_SPREAD_RIGHT = "page_mode_spread_right"
    PAGE_MODE_SPREAD_LEFT = "page_mode_spread_left"
    TOGGLE_SPREAD = "toggle_spread"


def get_action_display_name(action_name: str) -> str:
    """アクションの表示名を取得"""
    return get_text(f"actions.{action_name}")

# アクション名リスト（後方互換性のため）
ACTION_LIST = [action.value for action in Actions]

# 後方互換性のための辞書（非推奨）
def get_actions_dict():
    """後方互換性のための辞書を取得（非推奨）"""
    return {action: get_action_display_name(action) for action in ACTION_LIST}

ACTIONS = get_actions_dict() 