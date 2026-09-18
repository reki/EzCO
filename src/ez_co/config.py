import locale
from PySide6.QtGui import QFontDatabase
from typing import Dict, Any, List
from ez_co.enums.arrows import Arrow
from ez_co.filters.builtin import BUILTIN_FILTER_ID, default_basic_settings, normalize_basic_settings
from ez_co.enums.archives import ArchiveInfo, ArchiveType
from ez_co.enums.actions import Actions
from ez_co.enums.mouse_buttons import MouseButtons
from ez_co.enums.keyboard_keys import KeyboardKeys, ModifierKeys
from ez_co.enums.fonts import FontFamilyManager

class OverrideDict(dict):
    """ランタイムオーバーライドを考慮する辞書プロキシ"""
    def __init__(self, original_dict: dict, config_instance, section_name: str):
        super().__init__(original_dict)
        self._config = config_instance
        self._section_name = section_name
    
    def __getitem__(self, key):
        key_path = f"{self._section_name}.{key}"
        if self._config.is_runtime_overridden(key_path):
            return self._config.get_runtime_override(key_path)
        return super().__getitem__(key)
    
    def get(self, key, default=None):
        key_path = f"{self._section_name}.{key}"
        if self._config.is_runtime_overridden(key_path):
            return self._config.get_runtime_override(key_path)
        return super().get(key, default)


def default_filters() -> dict:
    return {
        "pipe": [],
        "settings": {
            BUILTIN_FILTER_ID: default_basic_settings(),
        },
    }


def normalize_filter_pipe(raw) -> list:
    if not isinstance(raw, list):
        return []
    seen = set()
    pipe = []
    for item in raw:
        public_id = str(item or "").strip()
        if not public_id or public_id in seen:
            continue
        seen.add(public_id)
        pipe.append(public_id)
    return pipe


def normalize_filter_settings(raw) -> dict:
    incoming = raw if isinstance(raw, dict) else {}
    return {
        BUILTIN_FILTER_ID: normalize_basic_settings(incoming.get(BUILTIN_FILTER_ID)),
    }


def normalize_filters(raw) -> dict:
    data = raw if isinstance(raw, dict) else {}
    return {
        "pipe": normalize_filter_pipe(data.get("pipe")),
        "settings": normalize_filter_settings(data.get("settings")),
    }


class Config:
    def __init__(self):
        # ランタイムオーバーライド用の辞書（コマンドライン引数で指定された設定）
        self.runtime_overrides = {}
        
        self.window = {
            "width": 800,
            "height": 600,
            "x": 100,
            "y": 100,
            "auto_resize": False,
            "min_width": 400,
            "min_height": 300,
            "always_on_top": False,
            "save_window_state": True,
            "maximize_on_startup": False,
            "maximized": False,
            "dock_state": "",
        }
        self.viewer = {
            "background_color": "#c0ffc0",
            "fit_to_window": False,
            "fit_to_window_minimum": True,
            "mouse_lock": False,
            "mouse_lock_hide_cursor": True,
            "image_move_sensitivity": 2.0,
            "gesture_threshold": 50,
            "mouse_repeat_initial_delay": 100,  # ms - 長押し時の最初の間隔
            "mouse_repeat_acceleration_start": 100,  # ms - 加速開始時刻
            "mouse_repeat_min_interval": 30,  # ms - 最小間隔
            "page_mode": "single",  # single / spread_left / spread_right
            "zoom_navigation_mode": "page",  # page / left / right
            "spread_selected_as_axis": False,  # 両開き時、選択ページを軸に N と N+1 を表示
            "spread_toggle_preference": "keep_previous",  # keep_previous / prefer_right / prefer_left
            "last_spread_mode": "spread_right",  # 両開き／単ページ切替用の前回両開き方向
            "drop_opens_new_tab": False,
            "open_archives_in_own_tab": True,
            "open_folders_in_own_tab": False,
            "show_tabs_in_fullscreen": False,
            "show_page_slider_in_fullscreen": False,
        }
        self.cache = {
            "memory_limit": "256MB",
            "prefetch_pages": 15,
            "optimize_large_images": True,
            "optimize_threshold": "50MB",
            "optimize_max_resolution": 4000
        }
        self.history = {
            "max_count": 20,
            "restore_page_on_reopen": False,
            "open_last_file_on_startup": False
        }
        # 言語設定
        self.language = {
            "code": "system"
        }
        # デバッグ設定
        self.debug = {
            "enabled": False,
            "keep_archive_handles": False,
            "cache_archive_metadata": True,
            "show_error_log": False,
        }
        # アーカイブ設定をenumから初期化
        self.archive = {"enabled": True}
        for archive_type in ArchiveInfo.get_all_archive_types():
            config_key = ArchiveInfo.get_config_key(archive_type)
            self.archive[config_key] = True
        
        self.shortcuts = {
            Actions.NEXT_PAGE.value: [MouseButtons.LEFT.value, KeyboardKeys.RIGHT.value, KeyboardKeys.SPACE.value],
            Actions.PREV_PAGE.value: [MouseButtons.RIGHT.value, KeyboardKeys.V.value, KeyboardKeys.LEFT.value],
            Actions.NEXT_FILE.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.RIGHT.value}"],
            Actions.PREV_FILE.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.LEFT.value}"],
            Actions.NEXT_COMIC.value: [KeyboardKeys.W.value],
            Actions.PREV_COMIC.value: [KeyboardKeys.Q.value],
            Actions.ZOOM_IN.value: [MouseButtons.WHEEL_DOWN.value],
            Actions.ZOOM_OUT.value: [MouseButtons.WHEEL_UP.value],
            Actions.RESET_ZOOM.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_0.value}"],
            Actions.ROTATE_RIGHT.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.R.value}"],
            Actions.ROTATE_LEFT.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.O.value}"],
            Actions.FULLSCREEN.value: [KeyboardKeys.RETURN.value],
            Actions.CLOSE_APP.value: [KeyboardKeys.E.value],
            Actions.MIN_SCALE_TOGGLE.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.M.value}"],
            Actions.ALWAYS_ON_TOP.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.T.value}"],
            Actions.IMAGE_LIST.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.L.value}"],
            Actions.REOPEN_LAST_FILE.value: [KeyboardKeys.R.value],
            Actions.TOGGLE_BOOKMARK_DOCK.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.B.value}"],
            Actions.TOGGLE_HISTORY_DOCK.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.H.value}"],
            Actions.TOGGLE_BOOKMARK.value: [f"{ModifierKeys.CTRL.value}+{ModifierKeys.SHIFT.value}+{KeyboardKeys.B.value}"],
            Actions.NEW_WINDOW.value: [f"{ModifierKeys.CTRL.value}+{ModifierKeys.SHIFT.value}+{KeyboardKeys.N.value}"],
            Actions.TOGGLE_MOUSE_LOCK.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.K.value}"],
            Actions.OPEN_FILE_IN_NEW_TAB.value: [f"{ModifierKeys.CTRL.value}+{ModifierKeys.SHIFT.value}+{KeyboardKeys.O.value}"],
            Actions.SAVE_SESSION.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.S.value}"],
            Actions.NEW_TAB.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.T.value}"],
            Actions.CLOSE_TAB.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.W.value}"],
            Actions.REOPEN_CLOSED_TAB.value: [f"{ModifierKeys.CTRL.value}+{ModifierKeys.SHIFT.value}+{KeyboardKeys.T.value}"],
            Actions.NEXT_TAB.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.PAGE_DOWN.value}"],
            Actions.PREV_TAB.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.PAGE_UP.value}"],
            Actions.FIRST_TAB.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.HOME.value}"],
            Actions.LAST_TAB.value: [
                f"{ModifierKeys.CTRL.value}+{KeyboardKeys.END.value}",
                f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_0.value}",
            ],
            Actions.SHOW_TAB_1.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_1.value}"],
            Actions.SHOW_TAB_2.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_2.value}"],
            Actions.SHOW_TAB_3.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_3.value}"],
            Actions.SHOW_TAB_4.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_4.value}"],
            Actions.SHOW_TAB_5.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_5.value}"],
            Actions.SHOW_TAB_6.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_6.value}"],
            Actions.SHOW_TAB_7.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_7.value}"],
            Actions.SHOW_TAB_8.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_8.value}"],
            Actions.SHOW_TAB_9.value: [f"{ModifierKeys.CTRL.value}+{KeyboardKeys.KEY_9.value}"],
        }
        self.gesture_map = {
            Arrow.LEFT.value: Actions.PREV_COMIC.value,
            Arrow.RIGHT.value: Actions.NEXT_COMIC.value,
            Arrow.DOWN.value: Actions.CLOSE_APP.value,
            Arrow.DOWN.value + Arrow.RIGHT.value: Actions.FULLSCREEN.value,
            Arrow.UP.value + Arrow.DOWN.value: Actions.REOPEN_LAST_FILE.value,
            Arrow.RIGHT.value + Arrow.LEFT.value: Actions.FIRST_PAGE.value,
            Arrow.LEFT.value + Arrow.RIGHT.value: Actions.LAST_PAGE.value,
            Arrow.DOWN.value + Arrow.RIGHT.value + Arrow.LEFT.value: Actions.PAGE_SLIDER_DIALOG.value
        }
        # 言語コード取得してデフォルトフォントを決定
        lang_code = locale.getdefaultlocale()[0]
        
        # FontFamilyManagerを使用してデフォルトフォントを取得
        default_font = FontFamilyManager.get_default_font_for_language(lang_code)
        self.ui_font = {
            "font_family": default_font,
            "font_size": 10,
            "font_color": "#00008d",
            "bg_color": "#ffffff",
            "alpha": 150
        }
        
        # 画像一覧ダイアログ設定
        self.image_list = {
            "close_after_select": True
        }
        self.plugins = {
            "extension_handlers": {},
            "dialog": {},
            "enabled": {},
            "source_choice": {},
        }
        self.filters = default_filters()
        
        # 設定辞書をオーバーライド対応に変換
        self._apply_override_proxies()
    
    def _apply_override_proxies(self):
        """設定辞書をオーバーライド対応プロキシに変換"""
        self.window = OverrideDict(self.window, self, "window")
        self.viewer = OverrideDict(self.viewer, self, "viewer")
        self.cache = OverrideDict(self.cache, self, "cache")
        self.history = OverrideDict(self.history, self, "history")
        self.language = OverrideDict(self.language, self, "language")
        self.debug = OverrideDict(self.debug, self, "debug")
        self.archive = OverrideDict(self.archive, self, "archive")
        self.ui_font = OverrideDict(self.ui_font, self, "ui_font")
        self.image_list = OverrideDict(self.image_list, self, "image_list")
        self.plugins = OverrideDict(self.plugins, self, "plugins")
        self.filters = OverrideDict(self.filters, self, "filters")
    
    @classmethod
    def get_default_config(cls) -> Dict[str, Any]:
        """デフォルト設定の辞書を取得"""
        config = cls()
        return config.to_dict()
    # ユーザーが消した割り当てを、起動時にデフォルトで埋め戻さない
    _USER_ASSIGNMENT_SECTIONS = ("shortcuts", "gesture_map")

    @classmethod
    def merge_with_defaults(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """YAMLデータとデフォルト設定をマージして不足項目を追加"""
        default_config = cls.get_default_config()
        merged_config = {}
        # トップレベルのセクションをマージ
        for section_name, default_section in default_config.items():
            if section_name in data:
                incoming = data[section_name]
                # ショートカット／ジェスチャーは保存内容をそのまま使う
                if section_name in cls._USER_ASSIGNMENT_SECTIONS:
                    merged_config[section_name] = dict(incoming) if isinstance(incoming, dict) else incoming
                elif isinstance(default_section, dict) and isinstance(incoming, dict):
                    merged_section = default_section.copy()
                    merged_section.update(incoming)
                    merged_config[section_name] = merged_section
                else:
                    merged_config[section_name] = incoming
            else:
                # セクションが存在しない場合はデフォルトを追加
                merged_config[section_name] = default_section
        return merged_config

    @staticmethod
    def _resolve_last_spread_mode(original_data: Dict[str, Any], viewer_data: Dict[str, Any]) -> str:
        """前回の両開き方向を復元する。未保存なら現在の両開き、それも無ければ右。"""
        original_viewer = original_data.get("viewer") if isinstance(original_data, dict) else None
        saved = None
        if isinstance(original_viewer, dict) and "last_spread_mode" in original_viewer:
            saved = original_viewer.get("last_spread_mode")
        if saved in ("spread_left", "spread_right"):
            return saved
        page_mode = viewer_data.get("page_mode")
        if page_mode in ("spread_left", "spread_right"):
            return page_mode
        return "spread_right"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Config':
        # デフォルト設定とマージして不足項目を追加
        merged_data = cls.merge_with_defaults(data)
        config = cls()
        if "window" in merged_data:
            window_data = merged_data["window"]
            config.window.update({
                "width": window_data.get("width", 800),
                "height": window_data.get("height", 600),
                "x": window_data.get("x", 100),
                "y": window_data.get("y", 100),
                "auto_resize": window_data.get("auto_resize", False),
                "min_width": window_data.get("min_width", 400),
                "min_height": window_data.get("min_height", 300),
                "always_on_top": window_data.get("always_on_top", False),
                "save_window_state": window_data.get("save_window_state", True),
                "maximize_on_startup": window_data.get("maximize_on_startup", False),
                "maximized": bool(window_data.get("maximized", False)),
                "dock_state": str(window_data.get("dock_state") or ""),
            })
        if "viewer" in merged_data:
            viewer_data = merged_data["viewer"]
            config.viewer.update({
                "background_color": viewer_data.get("background_color", "#c0ffc0"),
                "fit_to_window": viewer_data.get("fit_to_window", False),
                "fit_to_window_minimum": viewer_data.get("fit_to_window_minimum", True),
                "mouse_lock": viewer_data.get("mouse_lock", False),
                "mouse_lock_hide_cursor": viewer_data.get("mouse_lock_hide_cursor", True),
                "image_move_sensitivity": viewer_data.get("image_move_sensitivity", 2.0),
                "gesture_threshold": viewer_data.get("gesture_threshold", 50),
                "mouse_repeat_initial_delay": viewer_data.get("mouse_repeat_initial_delay", 100),
                "mouse_repeat_acceleration_start": viewer_data.get("mouse_repeat_acceleration_start", 100),
                "mouse_repeat_min_interval": viewer_data.get("mouse_repeat_min_interval", 30),
                "page_mode": viewer_data.get("page_mode", "single") if viewer_data.get("page_mode") in ("single", "spread_left", "spread_right") else "single",
                "zoom_navigation_mode": (
                    viewer_data.get("zoom_navigation_mode", "page")
                    if viewer_data.get("zoom_navigation_mode") in ("page", "left", "right")
                    else "page"
                ),
                "spread_selected_as_axis": bool(
                    viewer_data.get(
                        "spread_selected_as_axis",
                        viewer_data.get("spread_cover_single", False),
                    )
                ),
                "spread_toggle_preference": (
                    viewer_data.get("spread_toggle_preference", "keep_previous")
                    if viewer_data.get("spread_toggle_preference") in ("keep_previous", "prefer_right", "prefer_left")
                    else "keep_previous"
                ),
                "last_spread_mode": cls._resolve_last_spread_mode(data, viewer_data),
                "drop_opens_new_tab": bool(viewer_data.get("drop_opens_new_tab", False)),
                "open_archives_in_own_tab": bool(viewer_data.get("open_archives_in_own_tab", True)),
                "open_folders_in_own_tab": bool(viewer_data.get("open_folders_in_own_tab", False)),
                "show_tabs_in_fullscreen": bool(viewer_data.get("show_tabs_in_fullscreen", False)),
                "show_page_slider_in_fullscreen": bool(viewer_data.get("show_page_slider_in_fullscreen", False)),
            })
        if "cache" in merged_data:
            cache_data = merged_data["cache"]
            config.cache.update(cache_data)
            # デフォルト値を設定（不足している場合）
            if "optimize_large_images" not in cache_data:
                config.cache["optimize_large_images"] = True
            if "optimize_threshold" not in cache_data:
                config.cache["optimize_threshold"] = "50MB"
            if "optimize_max_resolution" not in cache_data:
                config.cache["optimize_max_resolution"] = 4000
        if "history" in merged_data:
            history_data = merged_data["history"]
            config.history.update({
                "max_count": min(99, max(1, history_data.get("max_count", 20))),
                "restore_page_on_reopen": history_data.get("restore_page_on_reopen", False),
                "open_last_file_on_startup": history_data.get("open_last_file_on_startup", False)
            })
        if "language" in merged_data:
            language_data = merged_data["language"]
            config.language.update({
                "code": language_data.get("code", "system")
            })
        if "debug" in merged_data:
            debug_data = merged_data["debug"]
            config.debug.update({
                "enabled": debug_data.get("enabled", False),
                "keep_archive_handles": debug_data.get("keep_archive_handles", False),
                "cache_archive_metadata": debug_data.get("cache_archive_metadata", True),
                "show_error_log": debug_data.get("show_error_log", False),
            })
        if "archive" in merged_data:
            archive_data = merged_data["archive"]
            config.archive.update({
                "enabled": archive_data.get("enabled", True)
            })
            # 各アーカイブタイプの設定をenumから取得
            for archive_type in ArchiveInfo.get_all_archive_types():
                config_key = ArchiveInfo.get_config_key(archive_type)
                config.archive[config_key] = archive_data.get(config_key, True)
        
        if "shortcuts" in merged_data:
            loaded_shortcuts = merged_data["shortcuts"]
            if isinstance(loaded_shortcuts, dict):
                config.shortcuts = dict(loaded_shortcuts)
            else:
                config.shortcuts = {}
        if "gesture_map" in merged_data:
            loaded_gestures = merged_data["gesture_map"]
            if isinstance(loaded_gestures, dict):
                config.gesture_map = dict(loaded_gestures)
            else:
                config.gesture_map = {}
        if "ui_font" in merged_data:
            config.ui_font = merged_data["ui_font"]
        if "image_list" in merged_data:
            config.image_list = merged_data["image_list"]
        if "plugins" in merged_data:
            from ez_co.plugins.api import normalize_extension
            plugins_data = merged_data["plugins"] if isinstance(merged_data["plugins"], dict) else {}
            handlers = plugins_data.get("extension_handlers", {})
            if not isinstance(handlers, dict):
                handlers = {}
            dialog = plugins_data.get("dialog", {})
            if not isinstance(dialog, dict):
                dialog = {}
            enabled = plugins_data.get("enabled", {})
            if not isinstance(enabled, dict):
                enabled = {}
            source_choice = plugins_data.get("source_choice", {})
            if not isinstance(source_choice, dict):
                source_choice = {}
            normalized_choice = {}
            for key, value in source_choice.items():
                plugin_id = str(key).strip()
                if not plugin_id:
                    continue
                if isinstance(value, str):
                    source = value.strip()
                    if source:
                        normalized_choice[plugin_id] = {"source": source, "seen": []}
                    continue
                if not isinstance(value, dict):
                    continue
                source = str(value.get("source") or "").strip()
                if not source:
                    continue
                seen = value.get("seen")
                if not isinstance(seen, list):
                    seen = []
                normalized_choice[plugin_id] = {
                    "source": source,
                    "seen": [str(item) for item in seen],
                }
            config.plugins.update({
                "extension_handlers": {
                    normalize_extension(str(key)): str(value).strip()
                    for key, value in handlers.items()
                    if str(key).strip() and str(value).strip()
                },
                "dialog": dialog,
                "enabled": {
                    str(key).strip(): bool(value)
                    for key, value in enabled.items()
                    if str(key).strip()
                },
                "source_choice": normalized_choice,
            })
        if "filters" in merged_data:
            config.filters.update(normalize_filters(merged_data.get("filters")))
        
        # 設定辞書をオーバーライド対応に変換
        config._apply_override_proxies()
        return config
    def to_dict(self, exclude_runtime_overrides: bool = True) -> dict:
        """設定を辞書形式で返す
        
        Args:
            exclude_runtime_overrides: ランタイムオーバーライドを除外するかどうか
        """
        # プロキシを通さずに元の辞書データを取得
        def get_original_dict(proxy_dict):
            if isinstance(proxy_dict, OverrideDict):
                return dict(proxy_dict)  # 元の辞書部分のみを返す
            return proxy_dict
        
        result = {
            "window": get_original_dict(self.window),
            "viewer": get_original_dict(self.viewer),
            "cache": get_original_dict(self.cache),
            "history": get_original_dict(self.history),
            "language": get_original_dict(self.language),
            "debug": get_original_dict(self.debug),
            "archive": get_original_dict(self.archive),
            "shortcuts": self.shortcuts,
            "gesture_map": self.gesture_map,
            "ui_font": get_original_dict(self.ui_font),
            "image_list": get_original_dict(self.image_list),
            "plugins": get_original_dict(self.plugins),
            "filters": get_original_dict(self.filters),
        }
        
        return result
    def set_runtime_override(self, key_path: str, value: Any):
        """ランタイムオーバーライドを設定する
        
        Args:
            key_path: 'section.key' 形式のキーパス（例: 'archive.enabled'）
            value: 設定する値
        """
        self.runtime_overrides[key_path] = value
    
    def get_runtime_override(self, key_path: str) -> Any:
        """ランタイムオーバーライドを取得する
        
        Args:
            key_path: 'section.key' 形式のキーパス
            
        Returns:
            オーバーライドされた値、または None（オーバーライドされていない場合）
        """
        return self.runtime_overrides.get(key_path)
    
    def is_runtime_overridden(self, key_path: str) -> bool:
        """指定されたキーパスがランタイムオーバーライドされているかチェック
        
        Args:
            key_path: 'section.key' 形式のキーパス
            
        Returns:
            オーバーライドされている場合 True
        """
        return key_path in self.runtime_overrides
    
    def apply_dict(self, data: Dict[str, Any]):
        """辞書の内容をこのインスタンスへ上書きする（ランタイムオーバーライドは維持）"""
        loaded = Config.from_dict(data)
        runtime = dict(self.runtime_overrides)
        section_names = (
            "window", "viewer", "cache", "history", "language",
            "debug", "archive", "ui_font", "image_list", "plugins", "filters",
        )
        for name in section_names:
            current = getattr(self, name)
            incoming = dict(getattr(loaded, name))
            if isinstance(current, OverrideDict):
                current.clear()
                current.update(incoming)
            else:
                setattr(self, name, incoming)
        self.shortcuts = dict(loaded.shortcuts) if loaded.shortcuts else {}
        self.gesture_map = dict(loaded.gesture_map) if loaded.gesture_map else {}
        self.runtime_overrides = runtime

    @staticmethod
    def strip_profile_section(data: Dict[str, Any]) -> Dict[str, Any]:
        """旧config.yamlのprofile節を除いたコピーを返す"""
        if not isinstance(data, dict):
            return {}
        cleaned = dict(data)
        cleaned.pop("profile", None)
        return cleaned