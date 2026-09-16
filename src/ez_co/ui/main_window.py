from typing import List, Optional
from pathlib import Path
import os
import logging
import subprocess
import sys
import webbrowser
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout,
    QFileDialog, QMessageBox, QInputDialog,
    QApplication, QSpinBox, QLabel, QDockWidget,
    QDialog, QDialogButtonBox, QFormLayout, QColorDialog,
    QTabWidget,
)
from PySide6.QtCore import Qt, QTimer, QRect, QEvent, QPoint, QByteArray
from PySide6.QtGui import (
    QAction, QActionGroup, QPainter, QColor, QDragEnterEvent, QDropEvent,
    QFont, QCursor, QKeySequence,
)
from ez_co.config import Config
from ez_co.filters.builtin import BUILTIN_FILTER_ID, register_builtin
from ez_co.filters.pipeline import apply_pipe
from ez_co.filters.registry import get_filter_registry
from ez_co.handlers.file_handler import FileHandler
from ez_co.utils.database import DatabaseManager
from ez_co.ui.viewer.viewer_pane import ViewerPane
from ez_co.handlers.session_file import (
    SESSION_SUFFIX,
    is_session_file,
    load_session,
    save_session,
)
from ez_co.gestures.mouse_gesture import MouseGesture
from ez_co.ui.dialogs.settings_dialog import SettingsDialog
from ez_co.ui.plugins.plugin_dialog import PluginDialog
from ez_co.ui.dialogs.shortcut_dialog import ShortcutDialog
from ez_co.ui.dialogs.image_list_dialog import ImageListDialog
from ez_co.ui.dialogs.gesture_dialog import GestureDialog
from ez_co.ui.dialogs.about_dialog import AboutDialog
from ez_co.ui.docks.bookmark_toolbar import BookmarkToolbar
from ez_co.ui.docks.history_toolbar import HistoryToolbar
from ez_co.ui.docks.tab_list_toolbar import TabListToolbar
from ez_co.ui.dialogs.bookmark_dialog import BookmarkDialog
from ez_co.ui.docks.image_slide_sidebar import ImageSlideSidebar
from ez_co.ui.docks.page_slider import PageSlider
from ez_co.ui.dialogs.pdf_password_dialog import CLOSE_APP_RESULT, ArchivePasswordDialog
from ez_co.ui.viewer.viewer_tab_bar import ViewerTabBar
from ez_co.utils.path_utils import get_project_root, is_nuitka
from ez_co.enums.actions import get_action_display_name, Actions
from ez_co.enums.mouse_buttons import MouseButtons, MOUSE_BUTTON_VALUES
from ez_co.enums.keyboard_keys import key_to_string
from ez_co.enums.archives import ArchiveInfo
from ez_co.enums.images import ImageInfo
from ez_co.utils.language_manager import get_text, get_log_text, get_log_text
from ez_co.enums.entry_types import EntryType
logger = logging.getLogger(__name__)


class GestureOverlayWidget(QWidget):
    """ジェスチャーやメッセージ表示用のオーバーレイWidget"""
    def __init__(self, parent=None):
        logger.debug(get_log_text("main_window_gesture_overlay_init", parent=parent))
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self._message = None
        self._rect = None
        self.hide()
    def show_message(self, message, rect=None):
        logger.debug(get_log_text("main_window_gesture_overlay_show_message", message=message, rect=rect))
        self._message = message
        self._rect = rect
        self.show()
        self.raise_()
        self.update()
    def hide_message(self):
        logger.debug(get_log_text("main_window_gesture_overlay_hide_message"))
        self._message = None
        self.hide()
    def showEvent(self, event):
        logger.debug(get_log_text("main_window_gesture_overlay_show_event", is_visible=self.isVisible(), geometry=self.geometry(), parent=self.parent(), window=self.window(), object_name=self.objectName()))
        super().showEvent(event)
    def hideEvent(self, event):
        logger.debug(get_log_text("main_window_gesture_overlay_hide_event", is_visible=self.isVisible(), geometry=self.geometry(), parent=self.parent(), window=self.window(), object_name=self.objectName()))
        super().hideEvent(event)
    def raise_(self):
        logger.debug(get_log_text("main_window_gesture_overlay_raise", is_visible=self.isVisible(), geometry=self.geometry()))
        super().raise_()
    def setGeometry(self, rect):
        logger.debug(get_log_text("main_window_gesture_overlay_set_geometry", rect=rect))
        super().setGeometry(rect)
    def paintEvent(self, event):
        logger.debug(get_log_text("main_window_gesture_overlay_paint_event", message=self._message, rect=self._rect, is_visible=self.isVisible(), geometry=self.geometry(), parent=self.parent(), window=self.window(), object_name=self.objectName()))
        if not self._message:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # 設定値取得
        config = None
        main_window = self.parent()
        if hasattr(main_window, 'config'):
            config = main_window.config
        ui_font = getattr(config, 'ui_font', {}) if config else {}
        font_family = ui_font.get('font_family', 'Meiryo')
        font_size = ui_font.get('font_size', 18)
        font_color = ui_font.get('font_color', '#0000ff')
        bg_color = ui_font.get('bg_color', '#ffffff')
        alpha = ui_font.get('alpha', 170)
        # 色に透過度を合成
        def color_with_alpha(base, a):
            c = QColor(base)
            c.setAlpha(a)
            return c
        # 画像表示部のgeometry取得
        image_view = getattr(main_window, 'image_view', None)
        if image_view:
            # ImageViewの左上をオーバーレイ座標系で取得
            top_left = image_view.mapTo(main_window, image_view.rect().topLeft())
            overlay_top_left = self.mapFromParent(top_left)
            base_x, base_y = overlay_top_left.x(), overlay_top_left.y()
        else:
            base_x, base_y = 20, 20
        # テキストサイズ計算
        font = QFont(font_family, font_size)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.horizontalAdvance(self._message)
        text_height = metrics.height()
        # マージン（パディング）を広めに設定
        margin_x = 32
        margin_y = 20
        box_width = text_width + margin_x * 2
        box_height = text_height + margin_y * 2
        # 画像エリアの左上（メニュー下）に表示
        rect = QRect(base_x + 8, base_y + 8, box_width, box_height)
        # 透過色対応
        painter.setBrush(color_with_alpha(bg_color, alpha))
        painter.setPen(Qt.NoPen)
        painter.drawRect(rect)
        painter.setPen(color_with_alpha(font_color, alpha))
        # テキストはマージン分だけ内側に描画
        text_rect = QRect(rect.left() + margin_x, rect.top() + margin_y, text_width, text_height)
        painter.drawText(text_rect, Qt.AlignLeft | Qt.AlignVCenter, self._message)
        painter.end()
class MainWindow(QMainWindow):
    """メインウィンドウ"""
    def __init__(self, config: Config, db_manager=None, plugin_session=None):
        """閲覧ウィンドウを組み立てる。プラグインのロードは main が attach する。"""
        super().__init__()
        self.config = config
        self.is_fullscreen = False
        self.db_manager = db_manager or DatabaseManager(config)
        if db_manager is not None:
            self.db_manager.config = config
        self._closed_tabs = []
        self._closing = False
        self._window_was_maximized = bool(config.window.get("maximized", False))
        self._pending_maximize = False
        self._fullscreen_restore = None
        from ez_co.ui.plugins.plugin_session import PluginSession
        self.plugin_session = plugin_session or PluginSession()
        # マウスロック関連
        self.mouse_locked = False
        self.mouse_lock_center = None
        self.original_cursor = None
        self.gesture_active = False  # ジェスチャーがアクティブかどうか
        self.mouse_lock_movement = QPoint(0, 0)  # マウスロック時の累積移動量
        # UIの初期化
        self.setup_ui()
        # ショートカットの設定
        self.setup_shortcuts()
        self.gesture_overlay = GestureOverlayWidget(self)
        self.gesture_overlay.setGeometry(self.rect())
        self.gesture_overlay.raise_()
        # レイアウト変更時にもgeometryを合わせる
        self.resizeEvent = self._resizeEvent_with_overlay

    def plugin_current(self, key: str):
        """プラグイン向けの現在 path / folder / page。"""
        if key == "folder":
            return self.get_current_folder_path()
        if key == "path":
            if self.file_handler and self.file_handler.current_files:
                current = self.file_handler.current_files[self.file_handler.current_index]
                return str(current)
            return None
        if key == "page":
            return getattr(self, "current_page", None)
        return None

    def plugin_app_config(self):
        """プラグインへ渡すアプリ設定の辞書。"""
        return self.config.to_dict()

    def save_plugin_profile_config(self):
        """重複選択など、プラグイン関連のプロファイル設定を保存する。"""
        if self.db_manager:
            self.db_manager.save_profile_config(
                self.db_manager.current_profile,
                self.config.to_dict(),
            )

    def reload_current_for_plugin(self, page=None):
        """プラグインから現在タブを再読み込みする。"""
        return bool(self._reload_current_pane_files(page))

    def _plugin_settings_visible(self) -> bool:
        """設定メニューにプラグイン設定を出すか。"""
        session = getattr(self, "plugin_session", None)
        if session is not None:
            return session.consent_accepted()
        return False

    def _notify_plugin_current_changed(self):
        """開いているファイルの変化をプラグインへ渡す。"""
        session = getattr(self, "plugin_session", None)
        if session is not None:
            session.notify_current_changed()

    def _readd_plugin_sidebar_actions(self):
        """サイドバーメニューにプラグイン用アクションを載せ直す。"""
        session = getattr(self, "plugin_session", None)
        if session is not None:
            session.readd_sidebar_actions()

    @property
    def current_pane(self) -> Optional[ViewerPane]:
        if not hasattr(self, "tab_widget"):
            return None
        widget = self.tab_widget.currentWidget()
        return widget if isinstance(widget, ViewerPane) else None

    def _iter_panes(self):
        if not hasattr(self, "tab_widget"):
            return
        for index in range(self.tab_widget.count()):
            widget = self.tab_widget.widget(index)
            if isinstance(widget, ViewerPane):
                yield widget

    def _pane_get(self, name, default=None):
        pane = self.current_pane
        return getattr(pane, name, default) if pane is not None else default

    def _pane_set(self, name, value):
        pane = self.current_pane
        if pane is not None:
            setattr(pane, name, value)

    @property
    def file_handler(self):
        return self._pane_get("file_handler")

    @file_handler.setter
    def file_handler(self, value):
        self._pane_set("file_handler", value)

    @property
    def image_view(self):
        pane = self.current_pane
        return pane.image_view if pane is not None else None

    @property
    def current_file_path(self):
        return self._pane_get("current_file_path")

    @current_file_path.setter
    def current_file_path(self, value):
        self._pane_set("current_file_path", value)

    @property
    def base_dir_path(self):
        return self._pane_get("base_dir_path")

    @base_dir_path.setter
    def base_dir_path(self, value):
        self._pane_set("base_dir_path", value)

    @property
    def current_rotation_angle(self):
        return self._pane_get("current_rotation_angle", 0)

    @current_rotation_angle.setter
    def current_rotation_angle(self, value):
        self._pane_set("current_rotation_angle", value)

    @property
    def current_page(self):
        return self._pane_get("current_page", 1)

    @current_page.setter
    def current_page(self, value):
        self._pane_set("current_page", value)

    @property
    def total_pages(self):
        return self._pane_get("total_pages", 0)

    @total_pages.setter
    def total_pages(self, value):
        self._pane_set("total_pages", value)

    @property
    def _spread_force_single(self):
        return self._pane_get("_spread_force_single", False)

    @_spread_force_single.setter
    def _spread_force_single(self, value):
        self._pane_set("_spread_force_single", value)

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text('app_name'))
        # メニューバーの設定
        self.setup_menu()
        # 常に手前に表示フラグ反映
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.config.window.get("always_on_top", False))
        # メインウィジェットの設定
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        self.setAcceptDrops(True)
        # レイアウトの設定
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBar(ViewerTabBar(self.tab_widget))
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.tabCloseRequested.connect(self._close_tab_at)
        layout.addWidget(self.tab_widget)
        self.tab_widget.blockSignals(True)
        self._add_tab(switch=True)
        self.tab_widget.blockSignals(False)
        self.tab_widget.currentChanged.connect(self._on_tab_changed)
        self.tab_widget.tabBar().tabMoved.connect(lambda *_: self._refresh_tab_list())
        self._sync_tab_bar()
        # ツールバーの設定
        self.setup_toolbars()
        # ステータスバーの設定
        self.setup_status_bar()
        self._apply_window_geometry()
        
        # マウスジェスチャーの設定
        self.mouse_gesture = MouseGesture(self.config)
        self.mouse_gesture.set_target_widget(self)
        
        # ダイアログの参照
        self.image_list_dialog = None

    def _first_keyboard_shortcut(self, action_name: str):
        """アクションに割り当てた最初のキーボードショートカット。"""
        for shortcut in self.config.shortcuts.get(action_name, []) or []:
            if shortcut and shortcut not in MOUSE_BUTTON_VALUES:
                return shortcut
        return None

    def _apply_action_shortcut(self, action: QAction, action_name: str):
        shortcut = self._first_keyboard_shortcut(action_name)
        if not shortcut:
            return
        action.setShortcut(QKeySequence(shortcut))
        action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)

    def setup_menu(self):
        """メニューバーの設定"""
        menubar = self.menuBar()
        # ファイルメニュー
        file_menu = menubar.addMenu(get_text("ui.file"))
        # 開くアクション
        open_action = QAction(get_text("ui.open_file") + '(&O)', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.open_file)
        file_menu.addAction(open_action)
        open_new_tab_action = QAction(get_text("ui.open_file_in_new_tab"), self)
        open_new_tab_action.triggered.connect(self.open_file_in_new_tab)
        self._apply_action_shortcut(open_new_tab_action, Actions.OPEN_FILE_IN_NEW_TAB.value)
        file_menu.addAction(open_new_tab_action)
        open_folder_action = QAction(get_text("ui.open_folder"), self)
        open_folder_action.triggered.connect(self.open_folder)
        self._apply_action_shortcut(open_folder_action, Actions.OPEN_FOLDER.value)
        file_menu.addAction(open_folder_action)
        # 最後のファイルを開くアクション
        open_last_action = QAction(get_text("ui.reopen_last_file") + '(&L)', self)
        open_last_action.triggered.connect(self.open_last_file)
        self._apply_action_shortcut(open_last_action, Actions.REOPEN_LAST_FILE.value)
        file_menu.addAction(open_last_action)
        # 新規ウィンドウアクション
        new_window_action = QAction(get_text("ui.new_window") + '(&N)', self)
        new_window_action.triggered.connect(self.new_window)
        self._apply_action_shortcut(new_window_action, Actions.NEW_WINDOW.value)
        file_menu.addAction(new_window_action)
        self.save_session_action = QAction(get_text("ui.save_session"), self)
        self.save_session_action.triggered.connect(self.save_session_as)
        self._apply_action_shortcut(self.save_session_action, Actions.SAVE_SESSION.value)
        file_menu.addAction(self.save_session_action)
        file_menu.aboutToShow.connect(self._update_save_session_action)
        self._update_save_session_action()
        # 区切り線
        file_menu.addSeparator()
        self.next_comic_action = QAction(get_text("ui.next_comic"), self)
        self.next_comic_action.triggered.connect(self.next_comic)
        self._apply_action_shortcut(self.next_comic_action, Actions.NEXT_COMIC.value)
        file_menu.addAction(self.next_comic_action)
        self.prev_comic_action = QAction(get_text("ui.prev_comic"), self)
        self.prev_comic_action.triggered.connect(self.prev_comic)
        self._apply_action_shortcut(self.prev_comic_action, Actions.PREV_COMIC.value)
        file_menu.addAction(self.prev_comic_action)
        file_menu.addSeparator()
        self.exit_action = QAction(get_text("ui.exit"), self)
        self.exit_action.triggered.connect(self.close_application)
        self._apply_action_shortcut(self.exit_action, Actions.CLOSE_APP.value)
        file_menu.addAction(self.exit_action)
        # 表示メニュー
        view_menu = menubar.addMenu(get_text("ui.view"))
        self.fullscreen_action = QAction(get_text("ui.fullscreen"), self)
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self._apply_action_shortcut(self.fullscreen_action, Actions.FULLSCREEN.value)
        view_menu.addAction(self.fullscreen_action)
        self.show_tabs_in_fullscreen_action = QAction(get_text("ui.show_tabs_in_fullscreen"), self)
        self.show_tabs_in_fullscreen_action.setCheckable(True)
        self.show_tabs_in_fullscreen_action.setChecked(self.config.viewer.get("show_tabs_in_fullscreen", False))
        self.show_tabs_in_fullscreen_action.triggered.connect(self.toggle_show_tabs_in_fullscreen)
        view_menu.addAction(self.show_tabs_in_fullscreen_action)
        self.show_page_slider_in_fullscreen_action = QAction(get_text("ui.show_page_slider_in_fullscreen"), self)
        self.show_page_slider_in_fullscreen_action.setCheckable(True)
        self.show_page_slider_in_fullscreen_action.setChecked(
            self.config.viewer.get("show_page_slider_in_fullscreen", False)
        )
        self.show_page_slider_in_fullscreen_action.triggered.connect(self.toggle_show_page_slider_in_fullscreen)
        view_menu.addAction(self.show_page_slider_in_fullscreen_action)
        # 常に手前に表示
        self.always_on_top_action = QAction(get_text("ui.always_on_top"), self)
        self.always_on_top_action.setCheckable(True)
        self.always_on_top_action.setChecked(self.config.window.get("always_on_top", False))
        self.always_on_top_action.triggered.connect(self.toggle_always_on_top)
        self._apply_action_shortcut(self.always_on_top_action, Actions.ALWAYS_ON_TOP.value)
        view_menu.addAction(self.always_on_top_action)
        # 最小縮小率
        self.min_scale_action = QAction(get_text("ui.min_scale_toggle"), self)
        self.min_scale_action.setCheckable(True)
        self.min_scale_action.setChecked(self.config.viewer.get("fit_to_window_minimum", True))
        self.min_scale_action.triggered.connect(self.toggle_min_scale)
        self._apply_action_shortcut(self.min_scale_action, Actions.MIN_SCALE_TOGGLE.value)
        view_menu.addAction(self.min_scale_action)
        # マウスロック
        self.mouse_lock_action = QAction(get_text("ui.toggle_mouse_lock"), self)
        self.mouse_lock_action.setCheckable(True)
        self.mouse_lock_action.setChecked(self.config.viewer.get("mouse_lock", False))
        self.mouse_lock_action.triggered.connect(self.toggle_mouse_lock)
        self._apply_action_shortcut(self.mouse_lock_action, Actions.TOGGLE_MOUSE_LOCK.value)
        view_menu.addAction(self.mouse_lock_action)
        view_menu.addSeparator()
        # 画像回転
        self.rotate_right_action = QAction(get_text("ui.rotate_right"), self)
        self.rotate_right_action.triggered.connect(self.rotate_right)
        self._apply_action_shortcut(self.rotate_right_action, Actions.ROTATE_RIGHT.value)
        view_menu.addAction(self.rotate_right_action)
        self.rotate_left_action = QAction(get_text("ui.rotate_left"), self)
        self.rotate_left_action.triggered.connect(self.rotate_left)
        self._apply_action_shortcut(self.rotate_left_action, Actions.ROTATE_LEFT.value)
        view_menu.addAction(self.rotate_left_action)

        view_menu.addSeparator()
        self.comic_page_mode_group = QActionGroup(self)
        self.comic_page_mode_group.setExclusive(True)

        self.comic_single_action = QAction(get_text("ui.comic_single_page"), self)
        self.comic_single_action.setCheckable(True)
        self.comic_single_action.setData("single")
        self.comic_page_mode_group.addAction(self.comic_single_action)
        self._apply_action_shortcut(self.comic_single_action, Actions.PAGE_MODE_SINGLE.value)
        view_menu.addAction(self.comic_single_action)

        self.comic_spread_right_action = QAction(get_text("ui.comic_spread_right"), self)
        self.comic_spread_right_action.setCheckable(True)
        self.comic_spread_right_action.setData("spread_right")
        self.comic_page_mode_group.addAction(self.comic_spread_right_action)
        self._apply_action_shortcut(self.comic_spread_right_action, Actions.PAGE_MODE_SPREAD_RIGHT.value)
        view_menu.addAction(self.comic_spread_right_action)

        self.comic_spread_left_action = QAction(get_text("ui.comic_spread_left"), self)
        self.comic_spread_left_action.setCheckable(True)
        self.comic_spread_left_action.setData("spread_left")
        self.comic_page_mode_group.addAction(self.comic_spread_left_action)
        self._apply_action_shortcut(self.comic_spread_left_action, Actions.PAGE_MODE_SPREAD_LEFT.value)
        view_menu.addAction(self.comic_spread_left_action)

        page_mode = self.config.viewer.get("page_mode", "single")
        if page_mode == "spread_left":
            self.comic_spread_left_action.setChecked(True)
        elif page_mode == "spread_right":
            self.comic_spread_right_action.setChecked(True)
        else:
            self.comic_single_action.setChecked(True)
        self.comic_page_mode_group.triggered.connect(self.on_comic_page_mode_changed)

        self._setup_filter_menu(menubar)

        tab_menu = menubar.addMenu(get_text("ui.tab_menu"))
        new_tab_action = QAction(get_text("ui.new_tab"), self)
        new_tab_action.triggered.connect(self.new_tab)
        self._apply_action_shortcut(new_tab_action, Actions.NEW_TAB.value)
        tab_menu.addAction(new_tab_action)
        close_tab_action = QAction(get_text("ui.close_tab"), self)
        close_tab_action.triggered.connect(self.close_current_tab)
        self._apply_action_shortcut(close_tab_action, Actions.CLOSE_TAB.value)
        tab_menu.addAction(close_tab_action)
        self.reopen_tab_action = QAction(get_text("ui.reopen_closed_tab"), self)
        self.reopen_tab_action.triggered.connect(self.reopen_closed_tab)
        self._apply_action_shortcut(self.reopen_tab_action, Actions.REOPEN_CLOSED_TAB.value)
        tab_menu.addAction(self.reopen_tab_action)
        tab_menu.aboutToShow.connect(self._update_reopen_tab_action)
        tab_menu.addSeparator()
        prev_tab_action = QAction(get_text("ui.prev_tab"), self)
        prev_tab_action.triggered.connect(self.prev_tab)
        self._apply_action_shortcut(prev_tab_action, Actions.PREV_TAB.value)
        tab_menu.addAction(prev_tab_action)
        next_tab_action = QAction(get_text("ui.next_tab"), self)
        next_tab_action.triggered.connect(self.next_tab)
        self._apply_action_shortcut(next_tab_action, Actions.NEXT_TAB.value)
        tab_menu.addAction(next_tab_action)
        first_tab_action = QAction(get_text("ui.first_tab"), self)
        first_tab_action.triggered.connect(self.first_tab)
        self._apply_action_shortcut(first_tab_action, Actions.FIRST_TAB.value)
        tab_menu.addAction(first_tab_action)
        last_tab_action = QAction(get_text("ui.last_tab"), self)
        last_tab_action.triggered.connect(self.last_tab)
        self._apply_action_shortcut(last_tab_action, Actions.LAST_TAB.value)
        tab_menu.addAction(last_tab_action)
        self._update_reopen_tab_action()

        self._setup_profile_menu(menubar)

        # 機能／拡張メニュー
        extensions_menu = menubar.addMenu(get_text("ui.extensions"))
        
        # サイドバーサブメニュー
        self.sidebar_submenu = extensions_menu.addMenu(get_text("ui.sidebar"))
        
        # ブックマーク表示/非表示
        self.bookmark_action = QAction(get_text("ui.bookmarks"), self)
        self.bookmark_action.setCheckable(True)
        self.bookmark_action.triggered.connect(self.toggle_bookmark_dock)
        self._apply_action_shortcut(self.bookmark_action, Actions.TOGGLE_BOOKMARK_DOCK.value)
        self.sidebar_submenu.addAction(self.bookmark_action)
        
        # 履歴表示/非表示
        self.history_action = QAction(get_text("ui.history"), self)
        self.history_action.setCheckable(True)
        self.history_action.triggered.connect(self.toggle_history_dock)
        self._apply_action_shortcut(self.history_action, Actions.TOGGLE_HISTORY_DOCK.value)
        self.sidebar_submenu.addAction(self.history_action)

        self.tab_list_action = QAction(get_text("ui.tab_list"), self)
        self.tab_list_action.setCheckable(True)
        self.tab_list_action.triggered.connect(self.toggle_tab_list_dock)
        self._apply_action_shortcut(self.tab_list_action, Actions.TOGGLE_TAB_LIST_DOCK.value)
        self.sidebar_submenu.addAction(self.tab_list_action)
        
        # 画像スライドサイドバー表示/非表示
        self.image_slide_action = QAction(get_text("ui.image_slide"), self)
        self.image_slide_action.setCheckable(True)
        self.image_slide_action.triggered.connect(self.toggle_image_slide_dock)
        self._apply_action_shortcut(self.image_slide_action, Actions.IMAGE_SLIDE_SIDEBAR.value)
        self.sidebar_submenu.addAction(self.image_slide_action)
        
        self._readd_plugin_sidebar_actions()
        
        # セパレータ
        extensions_menu.addSeparator()
        
        # 画像一覧アクション
        self.image_list_action = QAction(get_text("ui.image_list"), self)
        self.image_list_action.triggered.connect(self.show_image_list_dialog)
        self._apply_action_shortcut(self.image_list_action, Actions.IMAGE_LIST.value)
        extensions_menu.addAction(self.image_list_action)
        
        self.page_slider_action = QAction(get_text("ui.page_slider_dialog"), self)
        self.page_slider_action.setCheckable(True)
        self.page_slider_action.triggered.connect(self.toggle_page_slider_dock)
        self._apply_action_shortcut(self.page_slider_action, Actions.PAGE_SLIDER_DIALOG.value)
        extensions_menu.addAction(self.page_slider_action)

        # 設定メニュー
        settings_menu = menubar.addMenu(get_text("ui.settings"))
        self.settings_action = QAction(get_text("ui.settings"), self)
        self.settings_action.triggered.connect(self.show_settings_dialog)
        settings_menu.addAction(self.settings_action)
        if self._plugin_settings_visible():
            self.plugin_settings_action = QAction(get_text("ui.plugin_settings"), self)
            self.plugin_settings_action.triggered.connect(self.show_plugin_dialog)
            settings_menu.addAction(self.plugin_settings_action)
        self.shortcut_action = QAction(get_text("ui.shortcut_settings"), self)
        self.shortcut_action.triggered.connect(self.show_shortcut_dialog)
        settings_menu.addAction(self.shortcut_action)
        self.gesture_action = QAction(get_text("ui.gesture_settings"), self)
        self.gesture_action.triggered.connect(self.show_gesture_dialog)
        settings_menu.addAction(self.gesture_action)
        
        # ヘルプメニュー
        help_menu = menubar.addMenu(get_text("ui.help"))
        
        self.manual_action = QAction(get_text("ui.open_manual"), self)
        self.manual_action.triggered.connect(self.open_manual)
        help_menu.addAction(self.manual_action)
        self.version_action = QAction(get_text("ui.version"), self)
        self.version_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(self.version_action)
        
        # 初期状態で拡張メニューを無効化
        self.update_extensions_menu_actions()
        
        # ランタイムオーバーライドが適用されている設定項目を非活性化
        self.apply_runtime_overrides_to_menu()
        if hasattr(self, "bookmark_dock"):
            self.bookmark_action.setChecked(self.bookmark_dock.isVisible())
            self.history_action.setChecked(self.history_dock.isVisible())
            self.tab_list_action.setChecked(self.tab_list_dock.isVisible())
            self.image_slide_action.setChecked(self.image_slide_dock.isVisible())
            if hasattr(self, "page_slider_dock"):
                self.page_slider_action.setChecked(self.page_slider_dock.isVisible())
            self._readd_plugin_sidebar_actions()

    def apply_runtime_overrides_to_menu(self):
        """ランタイムオーバーライドが適用されている設定項目に対応するメニューアクションを非活性化"""
        if not self.config:
            return
        
        # 常に手前に表示
        if self.config.is_runtime_overridden("window.always_on_top"):
            self.always_on_top_action.setEnabled(False)
            self.always_on_top_action.setToolTip(get_text("ui.runtime_override_tooltip"))
        
        # 最小縮小率
        if self.config.is_runtime_overridden("viewer.fit_to_window_minimum"):
            self.min_scale_action.setEnabled(False)
            self.min_scale_action.setToolTip(get_text("ui.runtime_override_tooltip"))
        
        # マウスロック
        if self.config.is_runtime_overridden("viewer.mouse_lock"):
            self.mouse_lock_action.setEnabled(False)
            self.mouse_lock_action.setToolTip(get_text("ui.runtime_override_tooltip"))

        if self.config.is_runtime_overridden("viewer.show_tabs_in_fullscreen"):
            self.show_tabs_in_fullscreen_action.setEnabled(False)
            self.show_tabs_in_fullscreen_action.setToolTip(get_text("ui.runtime_override_tooltip"))

        if self.config.is_runtime_overridden("viewer.show_page_slider_in_fullscreen"):
            self.show_page_slider_in_fullscreen_action.setEnabled(False)
            self.show_page_slider_in_fullscreen_action.setToolTip(get_text("ui.runtime_override_tooltip"))
        
        # ページ表示モード
        if self.config.is_runtime_overridden("viewer.page_mode"):
            tooltip = get_text("ui.runtime_override_tooltip")
            for action in (self.comic_single_action, self.comic_spread_left_action, self.comic_spread_right_action):
                action.setEnabled(False)
                action.setToolTip(tooltip)

        # プロファイル（CLI指定時は切替不可）
        if self.config.is_runtime_overridden("profile.current_profile"):
            tooltip = get_text("ui.runtime_override_tooltip")
            if hasattr(self, "add_profile_action"):
                self.add_profile_action.setEnabled(False)
                self.add_profile_action.setToolTip(tooltip)
            if hasattr(self, "manage_profiles_action"):
                self.manage_profiles_action.setEnabled(False)
                self.manage_profiles_action.setToolTip(tooltip)
            if hasattr(self, "profile_select_group"):
                for action in self.profile_select_group.actions():
                    action.setEnabled(False)
                    action.setToolTip(tooltip)

    def _setup_profile_menu(self, menubar):
        """プロファイルメニューを構築"""
        profile_menu = menubar.addMenu(get_text("ui.profile"))
        self.add_profile_action = QAction(get_text("ui.add_profile"), self)
        self.add_profile_action.triggered.connect(self.add_profile)
        profile_menu.addAction(self.add_profile_action)

        self.manage_profiles_action = QAction(get_text("ui.manage_profiles"), self)
        self.manage_profiles_action.triggered.connect(self.manage_profiles)
        profile_menu.addAction(self.manage_profiles_action)

        profile_menu.addSeparator()

        self.profile_select_group = QActionGroup(self)
        self.profile_select_group.setExclusive(True)
        current = self.db_manager.current_profile if self.db_manager else ""
        for name in self.db_manager.get_profiles() if self.db_manager else []:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setData(name)
            self.profile_select_group.addAction(action)
            profile_menu.addAction(action)
            action.setChecked(name == current)
            action.triggered.connect(lambda checked=False, profile=name: self.switch_profile(profile))
        self.profile_menu = profile_menu

    def add_profile(self):
        """プロファイルを追加"""
        if self.config.is_runtime_overridden("profile.current_profile"):
            return
        name, ok = QInputDialog.getText(self, get_text("ui.add_profile"), get_text("ui.enter_profile_name"))
        if not ok:
            return
        name = name.strip()
        if not name:
            QMessageBox.warning(self, get_text("ui.warning"), get_text("ui.profile_name_required"))
            return
        if self.db_manager.profile_exists(name):
            QMessageBox.warning(self, get_text("ui.warning"), get_text("ui.profile_name_exists"))
            return
        self.save_config()
        if self.db_manager.create_profile(name, self.config.to_dict()):
            QMessageBox.information(
                self,
                get_text("ui.success"),
                get_text("ui.profile_add_success").format(profile_name=name),
            )
            self.rebuild_menu()
        else:
            QMessageBox.critical(self, get_text("ui.error"), get_text("ui.profile_create_failed_msg"))

    def manage_profiles(self):
        """プロファイル管理ダイアログ"""
        if self.config.is_runtime_overridden("profile.current_profile"):
            return
        from ez_co.ui.dialogs.profile_manage_dialog import ProfileManageDialog
        dialog = ProfileManageDialog(self.db_manager, self)
        dialog.exec()
        if dialog.deleted_current:
            fallback = self.db_manager.get_default_protected_profile()
            self.switch_profile(fallback, persist=True, skip_save_current=True)
        else:
            self.rebuild_menu()

    def switch_profile(self, profile_name: str, persist: bool = True, skip_save_current: bool = False):
        """プロファイルを切り替え、設定をその場で適用する"""
        if not profile_name or not self.db_manager:
            return
        if self.config.is_runtime_overridden("profile.current_profile"):
            return
        if profile_name == self.db_manager.current_profile and not skip_save_current:
            return
        if not skip_save_current:
            self.save_config()
        if persist:
            self.db_manager.set_current_profile_persistent(profile_name)
        else:
            self.db_manager.set_current_profile(profile_name)
        data = self.db_manager.load_profile_config(profile_name)
        if data:
            self.config.apply_dict(data)
        else:
            self.config.apply_dict(Config().to_dict())
        self.apply_loaded_profile_config()
        self._reload_open_files_after_plugin_change()

    def apply_loaded_profile_config(self):
        """読み込んだプロファイル設定をUIへ反映する"""
        from ez_co.utils.language_manager import set_language
        try:
            set_language(self.config.language.get("code", "system"))
        except Exception:
            pass
        try:
            ui_font = self.config.ui_font
            font_family = ui_font.get("font_family")
            font_size = ui_font.get("font_size")
            if font_family and font_size:
                app = QApplication.instance()
                app_font = QFont(font_family, font_size)
                if app:
                    app.setFont(app_font)
                self.setFont(app_font)
        except Exception as e:
            logger.error(get_log_text("main_window_font_apply_failed", error=e))

        always_on_top = self.config.window.get("always_on_top", False)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, always_on_top)
        self.show()
        self.setMinimumSize(
            self.config.window.get("min_width", 400),
            self.config.window.get("min_height", 300),
        )

        for pane in self._iter_panes():
            pane.image_view.set_background_color(self.config.viewer.get("background_color", "#c0ffc0"))
            pane.image_view.set_config(self.config)
        if hasattr(self, "mouse_gesture") and self.mouse_gesture:
            new_threshold = self.config.viewer.get("gesture_threshold", 50)
            if hasattr(self.mouse_gesture, "set_threshold"):
                self.mouse_gesture.set_threshold(new_threshold)

        from ez_co.plugins.manager import get_plugin_manager
        manager = get_plugin_manager()
        if getattr(manager, "_loaded", False):
            manager.activate_ui(self.config)
        self.rebuild_menu()
        self.setup_shortcuts()
        if hasattr(self, "bookmark_toolbar"):
            self.bookmark_toolbar.refresh_bookmarks()
        if hasattr(self, "history_toolbar"):
            self.history_toolbar.refresh_history()
        self._clear_spread_force_single()
        if self.file_handler and self.file_handler.current_files:
            self.current_page = self.file_handler.current_index + 1
            self.update_image()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._update_image_slide_sidebar()
        self._restore_dock_state()

    def setup_toolbars(self):
        """ツールバーの設定"""
        # ブックマークツールバー
        self.bookmark_toolbar = BookmarkToolbar(config=self.config, db_manager=self.db_manager)
        self.bookmark_toolbar.bookmark_selected.connect(self.open_bookmark)
        bookmark_dock = QDockWidget(get_text("ui.bookmarks"), self)
        bookmark_dock.setObjectName("bookmark_dock")
        bookmark_dock.setWidget(self.bookmark_toolbar)
        bookmark_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, bookmark_dock)
        # 履歴ツールバー
        self.history_toolbar = HistoryToolbar(self.db_manager)
        self.history_toolbar.history_selected.connect(self.open_history)
        history_dock = QDockWidget(get_text("ui.history"), self)
        history_dock.setObjectName("history_dock")
        history_dock.setWidget(self.history_toolbar)
        history_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, history_dock)

        self.tab_list_toolbar = TabListToolbar()
        self.tab_list_toolbar.tab_activated.connect(self.tab_widget.setCurrentIndex)
        self.tab_list_toolbar.tab_close_requested.connect(self._close_tab_at)
        tab_list_dock = QDockWidget(get_text("ui.tab_list"), self)
        tab_list_dock.setObjectName("tab_list_dock")
        tab_list_dock.setWidget(self.tab_list_toolbar)
        tab_list_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, tab_list_dock)
        
        # 画像スライドサイドバー
        self.image_slide_sidebar = ImageSlideSidebar()
        self.image_slide_sidebar.page_selected.connect(self.on_image_slide_page_selected)
        image_slide_dock = QDockWidget(get_text("ui.image_slide"), self)
        image_slide_dock.setObjectName("image_slide_dock")
        image_slide_dock.setWidget(self.image_slide_sidebar)
        image_slide_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.addDockWidget(Qt.RightDockWidgetArea, image_slide_dock)

        self.page_slider = PageSlider(host=self, file_handler=self.file_handler)
        page_slider_dock = QDockWidget(get_text("ui.page_slider_dialog_title"), self)
        page_slider_dock.setObjectName("page_slider_dock")
        page_slider_dock.setWidget(self.page_slider)
        page_slider_dock.setAllowedAreas(Qt.TopDockWidgetArea | Qt.BottomDockWidgetArea)
        self.addDockWidget(Qt.BottomDockWidgetArea, page_slider_dock)
        self.page_slider.set_compact(True)
        
        # デフォルトでは非表示
        bookmark_dock.hide()
        history_dock.hide()
        tab_list_dock.hide()
        image_slide_dock.hide()
        page_slider_dock.hide()
        # メニューに表示/非表示のアクションを追加
        self.bookmark_dock = bookmark_dock
        self.history_dock = history_dock
        self.tab_list_dock = tab_list_dock
        self.image_slide_dock = image_slide_dock
        self.page_slider_dock = page_slider_dock
        
        # ドックウィジェットの表示/非表示状態とメニューアクションの同期
        bookmark_dock.visibilityChanged.connect(lambda visible: self.bookmark_action.setChecked(visible))
        history_dock.visibilityChanged.connect(lambda visible: self.history_action.setChecked(visible))
        tab_list_dock.visibilityChanged.connect(lambda visible: self.tab_list_action.setChecked(visible))
        image_slide_dock.visibilityChanged.connect(self.on_image_slide_dock_visibility_changed)
        page_slider_dock.visibilityChanged.connect(self._on_page_slider_dock_visibility_changed)
        page_slider_dock.topLevelChanged.connect(self._on_page_slider_floating)
        self._apply_sidebar_dock_corners()
        self._restore_dock_state()
        self._refresh_tab_list()
    def setup_status_bar(self):
        # ステータスバーは廃止
        pass
    def update_zoom_display(self, zoom_factor):
        # ImageView上に半透明ラベルで2～3秒だけ表示
        self.show_zoom_overlay(zoom_factor)
    def show_zoom_overlay(self, zoom_factor):
        if self.image_view is None:
            return
        if (
            not hasattr(self, '_zoom_overlay_label')
            or self._zoom_overlay_label.parent() is not self.image_view
        ):
            self._zoom_overlay_label = QLabel(self.image_view)
            # ここでsetStyleSheetはしない（後で必ず上書きするため）
            self._zoom_overlay_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._zoom_overlay_label.setAttribute(Qt.WA_TransparentForMouseEvents)
            if not hasattr(self, "_zoom_overlay_timer"):
                self._zoom_overlay_timer = QTimer(self)
                self._zoom_overlay_timer.setSingleShot(True)
            try:
                self._zoom_overlay_timer.timeout.disconnect()
            except TypeError:
                pass
            self._zoom_overlay_timer.timeout.connect(lambda: self._zoom_overlay_label.hide())
        percent = int(zoom_factor * 100)
        self._zoom_overlay_label.setText(f"{get_text('ui.zoom_factor')} {percent} %")
        self._zoom_overlay_label.adjustSize()
        w = self._zoom_overlay_label.width()
        h = self._zoom_overlay_label.height()
        iw = self.image_view.width()
        ih = self.image_view.height()
        margin = 20
        self._zoom_overlay_label.move(margin, ih - h - margin)
        self._zoom_overlay_label.show()
        self._zoom_overlay_timer.start(2000)
        ui_font = getattr(self.config, 'ui_font', {}) if self.config else {}
        font_family = ui_font.get('font_family', 'Meiryo')
        font_size = ui_font.get('font_size', 18)
        font_color = ui_font.get('font_color', '#0000ff')
        bg_color = ui_font.get('bg_color', '#ffffff')
        alpha = ui_font.get('alpha', 170)
        # CSS用rgba形式に変換
        def to_rgba(css_hex, a):
            c = QColor(css_hex)
            return f"rgba({c.red()},{c.green()},{c.blue()},{a/255:.3f})"
        style = f"background-color: {to_rgba(bg_color, alpha)}; color: {to_rgba(font_color, alpha)}; border-radius: 8px; font-size: {font_size}px; padding: 12px; font-family: {font_family};"
        # スタイルを一度リセットしてから新しいスタイルを適用
        self._zoom_overlay_label.setStyleSheet("")
        self._zoom_overlay_label.setStyleSheet(style)
    def toggle_min_scale(self):
        """最小縮小率の切り替え"""
        is_checked = self.min_scale_action.isChecked()
        self.config.viewer["fit_to_window_minimum"] = is_checked
        if is_checked:
            # オンになった瞬間100%にする
            self.image_view.zoom_factor = 1.0
            self.image_view.update_image_display()
        # 設定を保存
        self.save_config()

    def on_comic_page_mode_changed(self, action):
        """コミックのページ表示モードを変更"""
        self.apply_comic_page_mode(action.data())

    def apply_comic_page_mode(self, mode: str):
        """単ページ／両開きの表示モードを適用し、メニューと設定を同期する"""
        if mode not in ("single", "spread_left", "spread_right"):
            mode = "single"
        if self.config and self.config.is_runtime_overridden("viewer.page_mode"):
            return
        if not self.config:
            return
        self.config.viewer["page_mode"] = mode
        if mode in ("spread_left", "spread_right"):
            self.config.viewer["last_spread_mode"] = mode
        self._sync_comic_page_mode_menu(mode)
        self.save_config()
        self._clear_spread_force_single()
        if self.file_handler and self.file_handler.current_files:
            self.current_page = self.file_handler.current_index + 1
            self.update_image()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._update_image_slide_sidebar()

    def _sync_comic_page_mode_menu(self, mode: str):
        """表示メニューのページモードのチェックを合わせる"""
        if not hasattr(self, "comic_page_mode_group"):
            return
        self.comic_page_mode_group.blockSignals(True)
        if mode == "spread_left":
            self.comic_spread_left_action.setChecked(True)
        elif mode == "spread_right":
            self.comic_spread_right_action.setChecked(True)
        else:
            self.comic_single_action.setChecked(True)
        self.comic_page_mode_group.blockSignals(False)

    def _resolve_toggle_spread_mode(self) -> str:
        """両開き／単ページ切替で両開きにするときの向き"""
        preference = self.config.viewer.get("spread_toggle_preference", "keep_previous") if self.config else "keep_previous"
        if preference == "prefer_left":
            return "spread_left"
        if preference == "prefer_right":
            return "spread_right"
        last_mode = self.config.viewer.get("last_spread_mode") if self.config else None
        if last_mode not in ("spread_left", "spread_right"):
            return "spread_right"
        return last_mode

    def toggle_comic_spread(self):
        """両開きと単ページを切り替える"""
        if self._is_spread_mode():
            self.apply_comic_page_mode("single")
        else:
            self.apply_comic_page_mode(self._resolve_toggle_spread_mode())

    def handle_page_mode_action(self, action_name: str):
        """ショートカット／ジェスチャーからのページ表示モード操作"""
        if action_name == Actions.PAGE_MODE_SINGLE.value:
            self.apply_comic_page_mode("single")
        elif action_name == Actions.PAGE_MODE_SPREAD_RIGHT.value:
            self.apply_comic_page_mode("spread_right")
        elif action_name == Actions.PAGE_MODE_SPREAD_LEFT.value:
            self.apply_comic_page_mode("spread_left")
        elif action_name == Actions.TOGGLE_SPREAD.value:
            self.toggle_comic_spread()

    def _is_page_mode_action(self, action_name: str) -> bool:
        return action_name in (
            Actions.PAGE_MODE_SINGLE.value,
            Actions.PAGE_MODE_SPREAD_RIGHT.value,
            Actions.PAGE_MODE_SPREAD_LEFT.value,
            Actions.TOGGLE_SPREAD.value,
        )

    def _is_spread_mode(self) -> bool:
        """両開き表示かどうか"""
        if not self.config:
            return False
        return self.config.viewer.get("page_mode", "single") in ("spread_left", "spread_right")

    def _is_spread_selected_as_axis(self) -> bool:
        """両開きで選択ページを軸に N と N+1 を表示するか"""
        if not self.config:
            return False
        return bool(self.config.viewer.get("spread_selected_as_axis", False))

    def _clear_spread_force_single(self):
        """スライダー等で明示的にページを選んだときは単ページ固定を解除"""
        self._spread_force_single = False

    def _use_rtl_page_slider(self) -> bool:
        """ページスライダーを右始まりにするか。両開き（左）以外は右が先頭。"""
        return self.config.viewer.get("page_mode", "single") != "spread_left"

    def _spread_display_start(self, index: int) -> int:
        """見開き表示の先頭インデックス。選択ページは変えず、表示ペアだけ決める。"""
        if not self._is_spread_mode() or not self.file_handler or not self.file_handler.current_files:
            return index
        total = len(self.file_handler.current_files)
        if total <= 0:
            return index
        index = max(0, min(index, total - 1))
        if self._is_spread_selected_as_axis():
            # 選択ページが軸。N と N+1 を表示
            return index
        # 通常: 1か2→1-2、3か4→3-4。最終ページが奇数のときのみ単ページ
        if total % 2 == 1 and index == total - 1:
            return index
        return index - (index % 2)

    def _align_spread_index(self, index: int) -> int:
        """表示ペア先頭（互換用）。選択インデックスは変更しない。"""
        return self._spread_display_start(index)

    def _align_current_spread_index(self):
        """選択ページは維持し、current_page だけ同期する"""
        if not self.file_handler or not self.file_handler.current_files:
            return
        if hasattr(self, 'current_page'):
            self.current_page = self.file_handler.current_index + 1

    def _has_spread_pair(self) -> bool:
        """現在の選択が両開きの2ページ表示対象か"""
        if not self._is_spread_mode() or not self.file_handler or not self.file_handler.current_files:
            return False
        if self._spread_force_single:
            return False
        start = self._spread_display_start(self.file_handler.current_index)
        return start + 1 < len(self.file_handler.current_files)

    def _next_spread_index(self):
        """次の見開き（または単ページ）の先頭インデックス"""
        if not self.file_handler or not self.file_handler.current_files:
            return None
        total = len(self.file_handler.current_files)
        idx = self.file_handler.current_index
        if self._is_spread_selected_as_axis():
            if self._spread_force_single and idx == 0:
                return 1 if total > 1 else None
            candidate = idx + 2
            if 0 <= candidate < total:
                return candidate
            return None
        start = self._spread_display_start(idx)
        candidate = start + 2 if self._has_spread_pair() else start + 1
        if 0 <= candidate < total:
            return candidate
        return None

    def _prev_spread_index(self):
        """前の見開き（または単ページ）の先頭インデックス"""
        if not self.file_handler or not self.file_handler.current_files:
            return None
        idx = self.file_handler.current_index
        if self._is_spread_selected_as_axis():
            if idx <= 0:
                return None
            target = idx - 2
            if target < 0:
                return 0
            return target
        start = self._spread_display_start(idx)
        if start <= 0:
            return None
        return self._spread_display_start(start - 1)

    def _apply_spread_axis_flags(self, going_next: bool, old_index: int, target: int):
        """選択軸モードの単ページ固定フラグを更新"""
        if not self._is_spread_selected_as_axis():
            self._spread_force_single = False
            return
        if going_next:
            self._spread_force_single = False
        else:
            # 2-3 から戻ったときだけ 1 ページ目を単ページ
            self._spread_force_single = (old_index == 1 and target == 0)

    def _is_loaded_file_currently_displayed(self, file) -> bool:
        """読み込み完了したファイルが現在表示対象か"""
        if not self.file_handler or not self.file_handler.current_files:
            return False
        files = self.file_handler.current_files
        idx = self.file_handler.current_index
        if idx < 0 or idx >= len(files):
            return False
        start = self._spread_display_start(idx)
        file_str = str(file)
        if file_str == str(files[start]):
            return True
        if self._has_spread_pair() and start + 1 < len(files) and file_str == str(files[start + 1]):
            return True
        return False

    def _get_display_image(self):
        """現在の表示モードに応じた画像を取得"""
        if not self.file_handler:
            return None
        if self._has_spread_pair():
            start = self._spread_display_start(self.file_handler.current_index)
            first_image = self._piped_image_at(start)
            second_image = self._piped_image_at(start + 1)
            if first_image and second_image:
                page_mode = self.config.viewer.get("page_mode", "spread_right")
                if page_mode == "spread_right":
                    # 右に小さいページ、左に次ページ
                    return self.image_view.combine_spread_images(second_image, first_image)
                return self.image_view.combine_spread_images(first_image, second_image)
            return first_image or second_image
        current = self.file_handler.get_current_image()
        index = self.file_handler.current_index if self.file_handler else -1
        return self._apply_display_pipe(current, index)

    def _piped_image_at(self, index: int):
        if not self.file_handler:
            return None
        return self._apply_display_pipe(self.file_handler.get_image_at(index), index)

    def _apply_display_pipe(self, image, page_index: int):
        if image is None:
            return None
        path = ""
        files = self.file_handler.current_files if self.file_handler else []
        if 0 <= page_index < len(files):
            path = str(files[page_index])
        filters = self.config.filters if self.config else {}
        return apply_pipe(
            image,
            filters.get("pipe") or [],
            path=path,
            page=page_index + 1,
            builtin_settings=(filters.get("settings") or {}).get(BUILTIN_FILTER_ID),
        )

    def _setup_filter_menu(self, menubar):
        """フィルターメニューを台帳から組み立てる。"""
        register_builtin()
        menu = menubar.addMenu(get_text("ui.filter_menu"))
        pipe = [str(item) for item in (self.config.filters.get("pipe") or [])]
        from ez_co.plugins.manager import get_plugin_manager
        host = get_plugin_manager().host
        for record in get_filter_registry().iter():
            title = get_text("ui.filter_basic") if record.public_id == BUILTIN_FILTER_ID else record.title
            submenu = menu.addMenu(title or record.public_id)
            enable = QAction(get_text("ui.filter_enable"), self)
            enable.setCheckable(True)
            enable.setChecked(record.public_id in pipe)
            enable.triggered.connect(
                lambda checked, public_id=record.public_id: self._set_filter_enabled(public_id, checked)
            )
            submenu.addAction(enable)
            has_settings = record.has_settings
            if record.plugin_id:
                has_settings = bool(host.configs_for(record.plugin_id))
            if has_settings:
                settings_action = QAction(get_text("ui.filter_settings"), self)
                settings_action.triggered.connect(
                    lambda _checked=False, rec=record: self._open_filter_settings(rec)
                )
                submenu.addAction(settings_action)

    def _set_filter_enabled(self, public_id: str, enabled: bool) -> None:
        public_id = str(public_id or "").strip()
        if not public_id or not self.config:
            return
        pipe = [str(item) for item in (self.config.filters.get("pipe") or [])]
        if enabled:
            if public_id not in pipe:
                pipe.append(public_id)
        else:
            pipe = [item for item in pipe if item != public_id]
        self.config.filters["pipe"] = pipe
        self.save_config()
        self.update_image()

    def _open_filter_settings(self, record) -> None:
        if not record.plugin_id or record.public_id == BUILTIN_FILTER_ID:
            from ez_co.ui.dialogs.filter_dialog import FilterDialog
            FilterDialog(self, self).exec()
            return
        from ez_co.plugins.manager import get_plugin_manager
        from ez_co.ui.plugins.plugin_config_dialog import PluginConfigDialog
        manager = get_plugin_manager()
        plugin = manager.get_plugin(record.plugin_id)
        name = plugin.name if plugin is not None else record.plugin_id
        PluginConfigDialog(manager.host, record.plugin_id, name, self).exec()

    def _on_plugin_filter_config_changed(self, plugin_id: str) -> None:
        prefix = f"plugin:{plugin_id}:"
        pipe = [str(item) for item in (self.config.filters.get("pipe") or [])]
        if any(item.startswith(prefix) for item in pipe):
            self.update_image()

    def next_comic(self):
        """次のコミック（ファイル）"""
        if not self.file_handler:
            logger.warning(get_log_text("main_window_no_file_handler"))
            return

        # 現在開いているコミック単位のパスを決定
        current_path = self._get_current_comic_path()
        if current_path is None:
            logger.warning(get_log_text("main_window_could_not_determine_current_comic_path"))
            return

        logger.info(get_log_text("debug_next_comic_current_comic_path", current_path=current_path))

        # FileHandlerの新しいメソッドを使用して次のコミックファイルを取得
        next_file = self.file_handler.get_next_comic_file(current_path)
        
        if next_file is None:
            logger.info(get_log_text("main_window_no_next_comic_found"))
            return

        # 同じファイルの場合は何もしない
        if next_file == current_path:
            logger.info(get_log_text("main_window_next_file_same_as_current"))
            return

        logger.info(get_log_text("debug_next_comic_next_file", next_file=next_file))

        # 現在のファイルの履歴を保存
        self.save_current_file_history()

        # 次のコミックに移動する時は回転状態をリセット
        self.current_rotation_angle = 0

        # アーカイブの状態をクリア（新しいファイルを開く際に再設定される）
        self.file_handler.current_archive = None
        self.file_handler.current_archive_path = None

        # 新しいコミックは1ページ目から開始するためインデックスをリセット
        self.file_handler.current_index = 0

        # 新しいファイルを開く
        self.open_files([str(next_file)])
    def prev_comic(self):
        """前のコミック（ファイル）"""
        if not self.file_handler:
            logger.warning(get_log_text("main_window_no_file_handler"))
            return

        # 現在開いているコミック単位のパスを決定
        current_path = self._get_current_comic_path()
        if current_path is None:
            logger.warning(get_log_text("main_window_could_not_determine_current_comic_path"))
            return

        logger.info(get_log_text("debug_prev_comic_current_comic_path", current_path=current_path))

        # FileHandlerの新しいメソッドを使用して前のコミックファイルを取得
        prev_file = self.file_handler.get_prev_comic_file(current_path)
        
        if prev_file is None:
            logger.info(get_log_text("main_window_no_prev_comic_found"))
            return

        # 同じファイルの場合は何もしない
        if prev_file == current_path:
            logger.info(get_log_text("main_window_prev_file_same_as_current"))
            return

        logger.info(get_log_text("debug_prev_comic_prev_file", prev_file=prev_file))

        # 現在のファイルの履歴を保存
        self.save_current_file_history()

        # 前のコミックに移動する時は回転状態をリセット
        self.current_rotation_angle = 0

        # アーカイブの状態をクリア（新しいファイルを開く際に再設定される）
        self.file_handler.current_archive = None
        self.file_handler.current_archive_path = None

        # 新しいコミックは1ページ目から開始するためインデックスをリセット
        self.file_handler.current_index = 0

        # 新しいファイルを開く
        self.open_files([str(prev_file)])

    def _get_current_comic_path(self) -> Optional[Path]:
        """現在開いているコミック単位（ファイル、フォルダ、アーカイブ）のパスを取得"""
        if not self.file_handler or not self.file_handler.current_files:
            return None

        # アーカイブ内の画像ファイルの場合は、アーカイブファイル自体を基準にする
        archive_path = self.file_handler.get_current_archive_path()
        if archive_path:
            return archive_path

        # フォルダから開いた場合は、フォルダ自体を基準にする
        if self.base_dir_path:
            return Path(self.base_dir_path)

        # 単独のファイルの場合は、そのファイル自体を基準にする
        current_file = self.file_handler.current_files[self.file_handler.current_index]
        if isinstance(current_file, str):
            return Path(current_file)
        else:
            return current_file

    def close_application(self):
        """アプリケーションを閉じる"""
        self.save_config()
        self.close()
    def new_window(self):
        """新規ウィンドウを開く"""
        try:
            # 同じプロセス内で新しいウィンドウを作成
            from ez_co.main import create_new_window
            create_new_window(self.config, self)
            logger.info(get_log_text("main_window_new_window_opened"))
        except Exception as e:
            logger.error(get_log_text("main_window_new_window_failed", error=e))
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.new_window_launch_failed").format(error=str(e)))
    def show_shortcut_dialog(self):
        """ショートカット設定ダイアログを表示"""
        dialog = ShortcutDialog(self.config, self)
        if dialog.exec():
            # 設定を更新
            self.config.shortcuts = dialog.get_shortcuts()
            self.save_config()
            # ショートカットを再設定
            self.setup_shortcuts()
            self.rebuild_menu()
    def _store_dock_state(self):
        if not hasattr(self, "bookmark_dock"):
            return
        state = self.saveState()
        self.config.window["dock_state"] = bytes(state.toBase64()).decode("ascii")

    def _restore_dock_state(self):
        if not hasattr(self, "bookmark_dock"):
            return
        raw = self.config.window.get("dock_state") or ""
        if raw:
            try:
                data = QByteArray.fromBase64(str(raw).encode("ascii"))
                if not data.isEmpty():
                    self.restoreState(data)
            except Exception as e:
                logger.debug(get_log_text("main_window_dock_state_restore_failed", error=e))
        if hasattr(self, "bookmark_action"):
            self.bookmark_action.setChecked(self.bookmark_dock.isVisible())
            self.history_action.setChecked(self.history_dock.isVisible())
            self.tab_list_action.setChecked(self.tab_list_dock.isVisible())
            self.image_slide_action.setChecked(self.image_slide_dock.isVisible())
            self._readd_plugin_sidebar_actions()
        if hasattr(self, "page_slider_dock"):
            self.page_slider.set_compact(not self.page_slider_dock.isFloating())
            if hasattr(self, "page_slider_action"):
                self.page_slider_action.setChecked(self.page_slider_dock.isVisible())
            if self.page_slider_dock.isVisible():
                self._update_page_slider()
        self._apply_sidebar_dock_corners()
        if self.image_slide_dock.isVisible():
            self._update_image_slide_sidebar_on_show()
        self._notify_plugin_current_changed()

    def save_config(self):
        """現在のプロファイルの設定をDBに保存"""
        self._store_dock_state()
        if self.db_manager:
            self.db_manager.save_profile_config(
                self.db_manager.current_profile,
                self.config.to_dict(),
            )
        
        # マウスジェスチャーの設定を更新
        if hasattr(self, 'mouse_gesture') and self.mouse_gesture:
            new_threshold = self.config.viewer.get("gesture_threshold", 50)
            logger.info(get_log_text("mouse_gesture_current_settings", current_threshold=self.mouse_gesture.threshold, config_threshold=new_threshold))
            if self.mouse_gesture.threshold != new_threshold:
                self.mouse_gesture.set_threshold(new_threshold)
                logger.info(get_log_text("mouse_gesture_threshold_updated", old_threshold=self.mouse_gesture.threshold, new_threshold=new_threshold))
    def show_display_settings(self):
        """表示設定ダイアログを表示"""
        dialog = QDialog(self)
        dialog.setWindowTitle(get_text("ui.display_settings"))
        layout = QFormLayout(dialog)
        # 背景色
        bg_color = QAction(get_text("ui.background_color"), self)
        bg_color.triggered.connect(self.select_background_color)
        layout.addRow(bg_color)
        # 最小スケール
        min_scale = QSpinBox()
        min_scale.setRange(1, 100)
        min_scale.setValue(int(self.config.display.min_scale * 100))
        min_scale.valueChanged.connect(lambda v: self.set_min_scale(v / 100))
        layout.addRow(get_text("ui.min_scale_percent"), min_scale)
        # ボタン
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, dialog
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        dialog.exec()
    def select_background_color(self):
        """背景色を選択"""
        color = QColorDialog.getColor(QColor(self.config.display.background_color), self)
        if color.isValid():
            self.config.display.background_color = color.name()
            self.image_view.update()
    def set_min_scale(self, scale: float):
        """最小スケールを設定"""
        self.config.display.min_scale = scale
        self.image_view.set_min_scale(scale)
    def zoom_reset(self):
        """ズームをリセット"""
        self.image_view.zoom_factor = 1.0
        self.image_view.update_image_display()
    def rotate_reset(self):
        """回転をリセット"""
        self.current_rotation_angle = 0
        self.image_view.set_rotation(0)
        logger.info(get_log_text("main_window_rotation_reset"))
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグ開始イベント"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    def dropEvent(self, event: QDropEvent):
        """ドロップイベントの処理"""
        mime_data = event.mimeData()
        if mime_data.hasUrls():
            files = [url.toLocalFile() for url in mime_data.urls()]
            logger.info(get_log_text("main_window_files_dropped", file_list=files))
            self.open_paths(files, new_tab=self.config.viewer.get("drop_opens_new_tab", False))
            event.acceptProposedAction()

    def _add_tab(self, switch: bool = True) -> ViewerPane:
        pane = ViewerPane(self.config, self)
        pane.image_view.next_page_requested.connect(self.next_page)
        pane.image_view.prev_page_requested.connect(self.prev_page)
        pane.image_view.zoom_changed.connect(self.update_zoom_display)
        index = self.tab_widget.addTab(pane, "")
        self._apply_tab_title(index)
        if switch:
            self.tab_widget.setCurrentIndex(index)
        self._sync_tab_bar()
        return pane

    def _sync_tab_bar(self):
        if not hasattr(self, "tab_widget"):
            return
        show = self.tab_widget.count() > 1
        if self.is_fullscreen and not self.config.viewer.get("show_tabs_in_fullscreen", False):
            show = False
        self.tab_widget.tabBar().setVisible(show)
        self._refresh_tab_list()
        self._update_reopen_tab_action()

    def _refresh_tab_list(self):
        if not hasattr(self, "tab_list_toolbar"):
            return
        titles = []
        for index in range(self.tab_widget.count()):
            pane = self.tab_widget.widget(index)
            if isinstance(pane, ViewerPane):
                titles.append(pane.tab_title())
            else:
                titles.append(self.tab_widget.tabText(index))
        self.tab_list_toolbar.refresh_tabs(titles, self.tab_widget.currentIndex())
        self._update_save_session_action()

    def _update_reopen_tab_action(self):
        if hasattr(self, "reopen_tab_action"):
            self.reopen_tab_action.setEnabled(bool(self._closed_tabs))

    def _has_savable_tabs(self) -> bool:
        if not hasattr(self, "tab_widget"):
            return False
        for index in range(self.tab_widget.count()):
            pane = self.tab_widget.widget(index)
            if isinstance(pane, ViewerPane) and (pane.current_file_path or pane.base_dir_path):
                return True
        return False

    def _update_save_session_action(self):
        if hasattr(self, "save_session_action"):
            self.save_session_action.setEnabled(self._has_savable_tabs())

    def toggle_show_tabs_in_fullscreen(self):
        enabled = self.show_tabs_in_fullscreen_action.isChecked()
        self.config.viewer["show_tabs_in_fullscreen"] = enabled
        self._sync_tab_bar()
        self.save_config()

    def toggle_show_page_slider_in_fullscreen(self):
        enabled = self.show_page_slider_in_fullscreen_action.isChecked()
        self.config.viewer["show_page_slider_in_fullscreen"] = enabled
        if self.is_fullscreen and hasattr(self, "page_slider_dock"):
            if enabled:
                self.page_slider_dock.show()
                self.page_slider_action.setChecked(True)
                self._update_page_slider()
            else:
                self.page_slider_dock.hide()
                self.page_slider_action.setChecked(False)
        self.save_config()

    def _apply_tab_title(self, index: int):
        pane = self.tab_widget.widget(index)
        if not isinstance(pane, ViewerPane):
            return
        title = pane.tab_title()
        self.tab_widget.setTabText(index, title)
        self.tab_widget.setTabToolTip(index, title)
        self._refresh_tab_list()
        self._update_save_session_action()

    def _sync_current_tab_title(self):
        index = self.tab_widget.currentIndex()
        if index >= 0:
            self._apply_tab_title(index)

    def _ensure_tab_for_new_open(self):
        pane = self.current_pane
        if pane is None or not pane.is_empty():
            self._add_tab(switch=True)

    def _on_tab_changed(self, index: int):
        if index < 0 or self.current_pane is None:
            return
        if hasattr(self, "_zoom_overlay_label"):
            self._zoom_overlay_label.hide()
        if self.file_handler and self.file_handler.current_files:
            self.update_image()
            self._update_image_list_dialog()
            self._update_image_slide_sidebar()
            self._notify_plugin_current_changed()
            comic = self._get_current_comic_path()
            if comic is not None and hasattr(self, "bookmark_toolbar"):
                self.set_current_file(str(comic), self.current_page)
            self.update_extensions_menu_actions()
        self._update_page_slider()
        self.update_title()
        self._refresh_tab_list()

    def _push_closed_tab(self, pane: ViewerPane):
        state = pane.closed_state()
        if state.get("file_path"):
            self._closed_tabs.append(state)

    def new_tab(self):
        self._add_tab(switch=True)
        self.update_title()
        self._refresh_tab_list()

    def close_current_tab(self):
        self._close_tab_at(self.tab_widget.currentIndex())

    def _close_tab_at(self, index: int):
        if index < 0 or index >= self.tab_widget.count():
            return
        if self.tab_widget.count() <= 1:
            self.close_application()
            return
        pane = self.tab_widget.widget(index)
        self.tab_widget.setCurrentIndex(index)
        self.save_current_file_history()
        if isinstance(pane, ViewerPane):
            self._push_closed_tab(pane)
        self.tab_widget.removeTab(index)
        if isinstance(pane, ViewerPane):
            pane.deleteLater()
        self._sync_tab_bar()

    def reopen_closed_tab(self):
        if not self._closed_tabs:
            return
        state = self._closed_tabs.pop()
        self._ensure_tab_for_new_open()
        path = state.get("file_path")
        page = state.get("page") or 1
        if path:
            self.open_history(path, page, new_tab=False)
        self._update_reopen_tab_action()

    def goto_tab(self, index: int):
        if 0 <= index < self.tab_widget.count():
            self.tab_widget.setCurrentIndex(index)

    def next_tab(self):
        count = self.tab_widget.count()
        if count > 1:
            self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() + 1) % count)

    def prev_tab(self):
        count = self.tab_widget.count()
        if count > 1:
            self.tab_widget.setCurrentIndex((self.tab_widget.currentIndex() - 1) % count)

    def first_tab(self):
        if self.tab_widget.count() > 0:
            self.tab_widget.setCurrentIndex(0)

    def last_tab(self):
        count = self.tab_widget.count()
        if count > 0:
            self.tab_widget.setCurrentIndex(count - 1)

    def _path_open_kind(self, path: str) -> str:
        if is_session_file(path):
            return "session"
        file_path = Path(path)
        if file_path.is_dir():
            return "folder"
        from ez_co.plugins.manager import get_plugin_manager
        decision = get_plugin_manager().resolve(path, self.config)
        if decision.is_skipped:
            return "skip"
        if decision.is_image:
            return "image"
        if decision.is_archive:
            return "archive"
        return "other"

    def _grouped_open_items(self, paths: List[str]) -> list[tuple[str, list[str]]]:
        archive_own = bool(self.config.viewer.get("open_archives_in_own_tab", True))
        folder_own = bool(self.config.viewer.get("open_folders_in_own_tab", False))
        items: list[tuple[str, list[str]]] = []
        bundle: list[str] = []
        bundle_inserted = False
        for path in paths:
            kind = self._path_open_kind(path)
            if kind == "skip":
                continue
            own_tab = (
                (kind == "archive" and archive_own)
                or (kind == "folder" and folder_own)
                or kind not in ("image", "folder", "archive")
            )
            if own_tab:
                items.append(("single", [path]))
            else:
                bundle.append(path)
                if not bundle_inserted:
                    items.append(("bundle", bundle))
                    bundle_inserted = True
        return items

    def _open_path_groups(self, paths: List[str], *, new_tab: bool = False):
        groups = self._grouped_open_items(paths)
        if not groups:
            if new_tab:
                self._ensure_tab_for_new_open()
            self.show_unsupported_file_message()
            return
        for index, (kind, group_paths) in enumerate(groups):
            if index == 0:
                if new_tab:
                    self._ensure_tab_for_new_open()
            else:
                self._add_tab(switch=True)
            if kind == "bundle" and len(group_paths) > 1:
                self.open_files(group_paths)
                self._sync_current_tab_title()
            else:
                self._open_single_path(group_paths[0])

    def open_paths(self, file_paths: List[str], *, new_tab: bool = False):
        paths = [path for path in file_paths if path]
        if not paths:
            return
        sessions = [path for path in paths if is_session_file(path)]
        others = [path for path in paths if not is_session_file(path)]
        if sessions:
            target = self.restore_session(sessions[0])
            if target is None:
                return
            if others:
                target._open_path_groups(others, new_tab=True)
            return
        self._open_path_groups(paths, new_tab=new_tab)

    def _open_single_path(self, file_path: str, page_number: int = 1):
        if is_session_file(file_path):
            self.restore_session(file_path)
            return
        if Path(file_path).is_dir():
            self.open_files([file_path])
            if page_number > 1 and self.file_handler and self.file_handler.current_files:
                target_index = page_number - 1
                if 0 <= target_index < len(self.file_handler.current_files):
                    self.file_handler.current_index = target_index
                    self.current_page = page_number
                    self.load_current_page()
                    self._update_page_slider()
        else:
            self.load_file(file_path, page_number)
        self._sync_current_tab_title()

    def run_window_action(self, action_name: str) -> bool:
        session = getattr(self, "plugin_session", None)
        if session is not None and session.invoke_registered(action_name):
            return True
        handlers = {
            Actions.NEW_TAB.value: self.new_tab,
            Actions.CLOSE_TAB.value: self.close_current_tab,
            Actions.REOPEN_CLOSED_TAB.value: self.reopen_closed_tab,
            Actions.NEXT_TAB.value: self.next_tab,
            Actions.PREV_TAB.value: self.prev_tab,
            Actions.FIRST_TAB.value: self.first_tab,
            Actions.LAST_TAB.value: self.last_tab,
            Actions.OPEN_FILE_IN_NEW_TAB.value: self.open_file_in_new_tab,
            Actions.OPEN_FOLDER.value: self.open_folder,
            Actions.SAVE_SESSION.value: self.save_session_as,
            Actions.SHOW_TAB_1.value: lambda: self.goto_tab(0),
            Actions.SHOW_TAB_2.value: lambda: self.goto_tab(1),
            Actions.SHOW_TAB_3.value: lambda: self.goto_tab(2),
            Actions.SHOW_TAB_4.value: lambda: self.goto_tab(3),
            Actions.SHOW_TAB_5.value: lambda: self.goto_tab(4),
            Actions.SHOW_TAB_6.value: lambda: self.goto_tab(5),
            Actions.SHOW_TAB_7.value: lambda: self.goto_tab(6),
            Actions.SHOW_TAB_8.value: lambda: self.goto_tab(7),
            Actions.SHOW_TAB_9.value: lambda: self.goto_tab(8),
            Actions.TOGGLE_TAB_LIST_DOCK.value: self.toggle_tab_list_dock,
        }
        handler = handlers.get(action_name)
        if handler is None:
            return False
        handler()
        return True

    def open_file(self):
        """ファイルを開く"""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, get_text("ui.open_file"), "",
            self._open_file_filter_string()
        )
        if file_paths:
            self.open_paths(file_paths, new_tab=False)

    def open_file_in_new_tab(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self, get_text("ui.open_file_in_new_tab"), "",
            self._open_file_filter_string()
        )
        if file_paths:
            self.open_paths(file_paths, new_tab=True)

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(self, get_text("ui.open_folder"), "")
        if folder:
            self.open_paths([folder], new_tab=False)

    def _glob_exts(self, extensions) -> str:
        parts = []
        seen = set()
        for ext in extensions:
            text = str(ext or "").strip().lower()
            if not text:
                continue
            if not text.startswith("."):
                text = "." + text
            if text in seen:
                continue
            seen.add(text)
            parts.append(f"*{text}")
        return " ".join(parts)

    def _open_file_filter_string(self) -> str:
        from ez_co.plugins.manager import get_plugin_manager
        image_exts = sorted(ImageInfo.get_all_extensions())
        archive_exts = []
        for archive_type in ArchiveInfo.get_all_archive_types():
            archive_exts.extend(ArchiveInfo.EXTENSIONS[archive_type])
        plugin_exts = sorted(get_plugin_manager().plugin_extensions(self.config))
        all_exts = [*image_exts, *archive_exts, *plugin_exts, SESSION_SUFFIX]
        parts = [
            f"{get_text('ui.all_supported_files')} ({self._glob_exts(all_exts)})",
            ImageInfo.get_file_filter_string(),
            f"{get_text('ui.archive_files')} ({self._glob_exts(archive_exts)})",
        ]
        if plugin_exts:
            parts.append(f"{get_text('ui.plugin_files')} ({self._glob_exts(plugin_exts)})")
        parts.append(self._session_file_filter())
        parts.append(f"{get_text('ui.all_files')} (*)")
        return ";;".join(parts)

    def _session_file_filter(self) -> str:
        return f"{get_text('ui.session_files')} (*{SESSION_SUFFIX})"

    def save_session_as(self):
        tabs = []
        current_saved = 0
        current_index = self.tab_widget.currentIndex() if hasattr(self, "tab_widget") else 0
        for index in range(self.tab_widget.count() if hasattr(self, "tab_widget") else 0):
            pane = self.tab_widget.widget(index)
            if not isinstance(pane, ViewerPane):
                continue
            path = pane.current_file_path or pane.base_dir_path
            if not path:
                continue
            if index == current_index:
                current_saved = len(tabs)
            tabs.append({"path": str(path), "page": int(pane.current_page or 1)})
        if not tabs:
            QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.no_tabs_to_save"))
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            get_text("ui.save_session"),
            "",
            self._session_file_filter(),
        )
        if not file_path:
            return
        if not file_path.lower().endswith(SESSION_SUFFIX):
            file_path += SESSION_SUFFIX
        try:
            save_session(file_path, tabs, current_saved)
            logger.info(get_log_text("session_saved", path=file_path))
        except Exception as exc:
            logger.error(get_log_text("session_save_failed_log", error=exc))
            QMessageBox.warning(
                self,
                get_text("dialogs.error"),
                get_text("ui.session_save_failed").format(error=str(exc)),
            )

    def _ask_session_restore_mode(self) -> str | None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(get_text("ui.session_restore_title"))
        box.setText(get_text("ui.session_restore_confirm"))
        replace_btn = box.addButton(
            get_text("ui.session_restore_replace"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        append_btn = box.addButton(
            get_text("ui.session_restore_append"),
            QMessageBox.ButtonRole.ActionRole,
        )
        new_window_btn = box.addButton(
            get_text("ui.session_restore_new_window"),
            QMessageBox.ButtonRole.ActionRole,
        )
        cancel_btn = box.addButton(get_text("ui.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(replace_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is replace_btn:
            return "replace"
        if clicked is append_btn:
            return "append"
        if clicked is new_window_btn:
            return "new_window"
        return None

    def _apply_session_tabs(self, tabs: list, current: int, *, replace: bool):
        first_new = 0
        if replace:
            self.tab_widget.blockSignals(True)
            while self.tab_widget.count() > 0:
                pane = self.tab_widget.widget(0)
                self.tab_widget.removeTab(0)
                if isinstance(pane, ViewerPane):
                    pane.deleteLater()
            self.tab_widget.blockSignals(False)
        else:
            first_new = self.tab_widget.count()
        for tab in tabs:
            self.tab_widget.blockSignals(True)
            self._add_tab(switch=True)
            self.tab_widget.blockSignals(False)
            path = tab.get("path")
            page = tab.get("page") or 1
            if path:
                self._open_single_path(path, page)
        if self.tab_widget.count() == 0:
            self._add_tab(switch=True)
        offset = min(max(int(current or 0), 0), max(len(tabs) - 1, 0))
        target = min(first_new + offset, self.tab_widget.count() - 1)
        if target >= 0:
            self.tab_widget.setCurrentIndex(target)
        self._sync_tab_bar()
        self.update_title()

    def restore_session(self, session_path: str):
        try:
            data = load_session(session_path)
        except Exception as exc:
            logger.error(get_log_text("session_restore_failed_log", error=exc))
            QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.session_invalid"))
            return None
        tabs = data.get("tabs") or []
        if not tabs:
            QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.session_empty"))
            return None
        mode = "replace"
        if self._has_savable_tabs():
            mode = self._ask_session_restore_mode()
            if mode is None:
                return None
            if mode == "new_window":
                try:
                    from ez_co.main import create_new_window
                    new_window = create_new_window(self.config, self)
                except Exception as exc:
                    logger.error(get_log_text("main_window_new_window_failed", error=exc))
                    QMessageBox.critical(
                        self,
                        get_text("dialogs.error"),
                        get_text("ui.new_window_launch_failed").format(error=str(exc)),
                    )
                    return None
                if new_window is None:
                    return None
                return new_window.restore_session(session_path)
        self._apply_session_tabs(tabs, data.get("current") or 0, replace=(mode == "replace"))
        logger.info(get_log_text("session_restored", path=session_path))
        return self

    def open_last_file(self):
        """最後に開いたファイルを開く"""
        try:
            latest_history = self.db_manager.get_latest_history()
            if latest_history:
                self.open_history(latest_history['file_path'], latest_history['page_number'])
            else:
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.no_history"))
        except Exception as e:
            logger.error(get_log_text("main_window_failed_reopen_last_file", error=e))
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.last_file_open_error").format(error=str(e)))
    def _ensure_file_handler(self):
        if self.file_handler is None:
            from ez_co.plugins.manager import get_plugin_manager
            self.file_handler = FileHandler(self.config, plugin_manager=get_plugin_manager())
            self.file_handler.set_on_image_loaded(self.on_image_loaded)
            self.file_handler.set_on_error_occurred(self.on_file_error_occurred)
        self.file_handler.set_archive_password_provider(self._provide_archive_password)

    def _provide_archive_password(self, file_path: str) -> bool:
        from ez_co.handlers.archive_password import (
            get_session_password,
            is_encrypted,
            set_session_password,
            try_unlock,
        )

        if not is_encrypted(file_path):
            set_session_password(file_path, "")
            return True
        if try_unlock(file_path, ""):
            set_session_password(file_path, "")
            return True

        cached = get_session_password(file_path)
        if cached is not None and try_unlock(file_path, cached):
            return True

        stored = self.db_manager.get_stored_archive_password(file_path) if self.db_manager else None
        mismatch = False
        if stored is not None:
            if try_unlock(file_path, stored):
                set_session_password(file_path, stored)
                return True
            mismatch = True

        while True:
            dialog = ArchivePasswordDialog(self, mismatch=mismatch)
            result = dialog.exec()
            if result == CLOSE_APP_RESULT:
                QApplication.instance().quit()
                return False
            if result != QDialog.DialogCode.Accepted:
                return False
            password = dialog.password()
            if try_unlock(file_path, password):
                set_session_password(file_path, password)
                return True
            mismatch = True

    def _provide_pdf_password(self, pdf_path: str) -> bool:
        return self._provide_archive_password(pdf_path)

    def open_files(self, file_paths: List[str]):
        """複数のファイルを開く"""
        try:
            # メッセージを非表示
            self.hide_center_message()
            self._clear_spread_force_single()
            
            # file_handlerが初期化されていない場合は初期化
            self._ensure_file_handler()
            
            # 現在のファイルの履歴を保存
            self.save_current_file_history()
            
            # 新しいファイルセットが開かれる時は回転状態をリセット
            self.current_rotation_angle = 0
            
            # アーカイブの状態をクリア（新しいファイルを開く際に再設定される）
            if self.file_handler:
                self.file_handler.current_archive = None
                self.file_handler.current_archive_path = None
            
            # フォルダが開かれた場合は、base_dir_pathを設定
            if len(file_paths) == 1 and Path(file_paths[0]).is_dir():
                self.base_dir_path = file_paths[0]
                # 履歴からページを復元
                restored_page = self._restore_page_from_history(file_paths[0])
            else:
                self.base_dir_path = None
                restored_page = 1
            
            # ファイルを開く
            success = self.file_handler.open_files(file_paths)
            
            if not success:
                # ファイルが開けなかった場合のメッセージ表示
                self.show_unsupported_file_message()
            elif len(self.file_handler.current_files) == 0:
                # 表示できるファイルがなかった場合のメッセージ表示
                # アーカイブ設定が無効になっている可能性をチェック
                if self.config and not self.config.archive.get("enabled", True):
                    self.show_archive_disabled_message()
                else:
                    self.show_no_displayable_files_message()
            else:
                # 履歴からページを復元（フォルダの場合）
                if self.base_dir_path and restored_page > 1:
                    target_index = restored_page - 1
                    if 0 <= target_index < len(self.file_handler.current_files):
                        self.file_handler.current_index = target_index
                        self.current_page = restored_page
                    else:
                        # インデックスが範囲外の場合は1ページ目に設定
                        self.file_handler.current_index = 0
                        self.current_page = 1
                else:
                    # 復元されたページがない場合は1ページ目に設定
                    self.current_page = 1
                
                # ファイルが正常に開かれた場合、UIを更新
                logger.info(get_log_text("debug_files_opened_successfully"))
                self._update_ui_after_file_open()
                self.save_current_file_history()
                
                # ページスライダーダイアログの更新
                self._update_page_slider()
                
                # 画像一覧ダイアログの更新
                self._update_image_list_dialog()
                
                # 画像スライドサイドバーの更新
                self._update_image_slide_sidebar()
        except Exception as e:
            logger.error(get_log_text("main_window_error_opening_files", error=e))
            self.show_unsupported_file_message()
    def _update_ui_after_file_open(self):
        """ファイルが開かれた後のUI更新"""
        try:
            if self.file_handler and self.file_handler.current_files:
                # 現在のファイルパスを設定
                current_file = self.file_handler.current_files[self.file_handler.current_index]
                if hasattr(current_file, 'name'):
                    self.current_file_path = str(current_file)
                else:
                    self.current_file_path = str(current_file)
                # ページ数を取得
                total_pages = self.file_handler.get_total_pages()
                self.total_pages = total_pages
                
                # current_pageが設定されていない場合は現在のインデックスから設定
                if not hasattr(self, 'current_page') or self.current_page is None:
                    self.current_page = self.file_handler.current_index + 1
                
                # UIを更新
                self.update_title()
                self.update_page_display()
                # 現在のページを読み込み
                self.load_current_page()
                # ツールバーを更新
                if hasattr(self, 'bookmark_toolbar'):
                    self.bookmark_toolbar.refresh_bookmarks()
                if hasattr(self, 'history_toolbar'):
                    self.history_toolbar.refresh_history()
                
                # 拡張メニューの状態を更新
                self.update_extensions_menu_actions()
                
                self._notify_plugin_current_changed()
                
                self._sync_current_tab_title()
                
                logger.info(get_log_text("debug_ui_updated", file=self.current_file_path, page=self.current_page, total_pages=self.total_pages))
        except Exception as e:
            logger.error(get_log_text("main_window_error_updating_ui", error=e))
    def show_unsupported_file_message(self):
        """サポートされていないファイルのメッセージを表示"""
        message = get_text("ui.unsupported_file_format")
        self.show_center_message(message)
    def show_no_displayable_files_message(self):
        """表示できるファイルがない場合のメッセージを表示"""
        message = get_text("ui.no_displayable_files")
        self.show_center_message(message)
    def show_archive_disabled_message(self):
        """アーカイブが無効になっている場合のメッセージを表示"""
        message = get_text("ui.archive_disabled_message")
        self.show_center_message(message)
    def on_file_error_occurred(self, error_type: str, error_message: str, archive_path: str):
        """ファイルエラー発生時の処理"""
        try:
            logger.error(get_log_text("main_window_file_error_occurred", error_type=error_type, error_message=error_message, archive_path=archive_path))
            
            # エラータイプに応じたユーザーフレンドリーなメッセージを生成
            if error_type == "file_not_found":
                user_message = get_text("ui.archive_file_not_found").format(path=Path(archive_path).name)
            elif error_type == "file_moved":
                user_message = get_text("ui.archive_file_moved").format(path=Path(archive_path).name)
            elif error_type == "permission_denied":
                user_message = get_text("ui.archive_permission_denied").format(path=Path(archive_path).name)
            elif error_type == "file_not_in_archive":
                user_message = get_text("ui.file_not_in_archive").format(archive=Path(archive_path).name)
            elif error_type == "unknown_format":
                user_message = get_text("ui.unknown_archive_format").format(path=Path(archive_path).name)
            elif error_type == "unsupported_format":
                user_message = get_text("ui.unsupported_archive_format").format(path=Path(archive_path).name)
            elif error_type == "processing_failed":
                user_message = get_text("ui.archive_processing_failed").format(path=Path(archive_path).name)
            elif error_type == "folder_access_failed":
                folder_name = Path(archive_path).name if archive_path else "Unknown"
                user_message = get_text("ui.folder_access_failed").format(folder_name=folder_name)
            elif error_type == "file_no_longer_accessible":
                file_path = Path(archive_path).name if archive_path else "Unknown"
                user_message = get_text("ui.file_no_longer_accessible").format(path=file_path)
            elif error_type == "archive_no_longer_accessible":
                archive_name = Path(archive_path).name if archive_path else "Unknown"
                user_message = get_text("ui.archive_no_longer_accessible").format(archive_name=archive_name)
            else:
                user_message = get_text("ui.file_loading_error").format(error=error_message)
            
            # センターメッセージでエラーを表示
            self.show_center_message(user_message)
            
        except Exception as e:
            logger.error(get_log_text("main_window_error_in_error_handler", error=e))
            # フォールバック：汎用エラーメッセージ
            self.show_center_message(get_text("ui.unexpected_error"))

    def on_image_loaded(self, file, image):
        """画像が読み込まれた時の処理"""
        try:
            if not image:
                return
            # プリフェッチ完了分で表示中ページを上書きしない
            if not self._is_loaded_file_currently_displayed(file):
                return
            # 両開きは合成済みの表示を単ページで置き換えない
            if self._has_spread_pair():
                QTimer.singleShot(0, self._update_ui_after_image_load)
                return
            logger.info(get_log_text("main_window_updating_image", image_size=image.size, image_mode=image.mode))
            # 画像の設定
            self.image_view.set_image(image)
            # 現在の回転状態を適用
            if self.current_rotation_angle != 0:
                logger.info(get_log_text("main_window_applying_rotation", rotation=self.current_rotation_angle))
                self.image_view.set_rotation(self.current_rotation_angle)
            # UIの更新を非同期で実行
            QTimer.singleShot(0, self._update_ui_after_image_load)
        except Exception as e:
            logger.error(get_log_text("main_window_error_in_image_loaded", error=e))
    def _update_ui_after_image_load(self):
        """画像読み込み後のUI更新処理"""
        try:
            # 画像表示の更新
            self.image_view.update_image_display()
            # ウィンドウタイトルを更新
            title = self.get_current_title()
            self.setWindowTitle(title)
            # 現在のファイル情報をブックマークツールバーに設定
            if self.file_handler and self.file_handler.current_files:
                current_page = self.file_handler.current_index + 1
                current_file = self.file_handler.current_files[self.file_handler.current_index]
                self.set_current_file(str(current_file), current_page)
            # 商品情報ツールバーを更新
            self._notify_plugin_current_changed()
            # 拡張メニューの状態を更新
            self.update_extensions_menu_actions()
        except Exception as e:
            logger.error(get_log_text("main_window_error_in_ui_update", error=e))
    def update_image(self):
        """現在の画像を表示"""
        logger.info(get_log_text("debug_update_image_called", current_index=self.file_handler.current_index if self.file_handler else -1))
        if not self.file_handler:
            logger.warning(get_log_text("main_window_no_file_handler_warning"))
            return
        if not self.file_handler.current_files:
            logger.warning(get_log_text("main_window_no_files_loaded"))
            return
        self._align_current_spread_index()
        logger.info(get_log_text("debug_update_image_calling_get_current_image", current_index=self.file_handler.current_index))
        current_image = self._get_display_image()
        logger.info(get_log_text("debug_update_image_get_current_image_result", has_image=current_image is not None, image_size=current_image.size if current_image else "N/A"))
        # 背景色を常に反映
        self.image_view.set_background_color(self.config.viewer["background_color"])
        if current_image:
            logger.info(get_log_text("main_window_updating_image_display", image_size=current_image.size, image_mode=current_image.mode))
            title = self.get_current_title()
            self.setWindowTitle(title)
            if self.config.window["auto_resize"]:
                img_width, img_height = current_image.size
                window_width = self.width()
                window_height = self.height()
                width_ratio = img_width / window_width
                height_ratio = img_height / window_height
                if width_ratio > height_ratio:
                    new_width = min(img_width, self.screen().size().width() * 0.8)
                    new_height = int(new_width * (img_height / img_width))
                else:
                    new_height = min(img_height, self.screen().size().height() * 0.8)
                    new_width = int(new_height * (img_width / img_height))
                new_width = max(new_width, self.config.window["min_width"])
                new_height = max(new_height, self.config.window["min_height"])
                logger.info(get_log_text("main_window_resizing_window", new_width=new_width, new_height=new_height))
                self.resize(new_width, new_height)
            # 画像を設定（キャッシュをクリアして新しい画像を表示）
            self.image_view.set_image(current_image)
            # 現在の回転状態を適用
            if self.current_rotation_angle != 0:
                self.image_view.set_rotation(self.current_rotation_angle)
            # 表示を更新
            self.image_view.update_image_display()
            # ブックマークツールバーを更新
            if hasattr(self, 'bookmark_toolbar'):
                current_file = self.file_handler.current_files[self.file_handler.current_index]
                file_path = str(current_file)
                page_number = self.file_handler.current_index + 1
                self.bookmark_toolbar.set_current_file(file_path, page_number)
        else:
            logger.warning(get_log_text("main_window_no_image_to_display"))
            self.setWindowTitle(get_text('app_name'))
            self.image_view.set_image(None)
    def get_current_title(self):
        """ウィンドウタイトルを生成"""
        if not self.file_handler or not self.file_handler.current_files:
            return get_text('app_name')
        file = self.file_handler.current_files[self.file_handler.current_index]
        total = len(self.file_handler.current_files)
        current = self.file_handler.current_index + 1
        # str型にも対応
        filename = os.path.basename(file) if isinstance(file, str) else file.name
        # タイトルバー表示用に仮想パスの区切り文字を「 | 」に変換（見やすくするため）
        if "|" in filename:
            filename = filename.replace("|", " | ")
        if self._has_spread_pair():
            start = self._spread_display_start(self.file_handler.current_index)
            return f"{get_text('app_name')} - {filename} {start + 1}-{start + 2}/{total}"
        return f"{get_text('app_name')} - {filename} {current}/{total}"
    def next_page(self):
        """次のページへ"""
        logger.info(get_log_text("debug_next_page_called", current_index=self.file_handler.current_index if self.file_handler else -1, total_files=len(self.file_handler.current_files) if self.file_handler else 0))
        if not self.file_handler:
            logger.warning(get_log_text("main_window_no_file_handler_warning"))
            return
        self._align_current_spread_index()
        logger.info(get_log_text("debug_next_page_calling_next_file", current_index=self.file_handler.current_index, total_files=len(self.file_handler.current_files)))
        moved = False
        if self._is_spread_mode():
            target = self._next_spread_index()
            if target is not None:
                self._apply_spread_axis_flags(going_next=True, old_index=self.file_handler.current_index, target=target)
            moved = target is not None and self.file_handler.go_to_page(target)
        else:
            moved = self.file_handler.next_file()
        if moved:
            logger.info(get_log_text("main_window_moving_to_next_page"))
            logger.info(get_log_text("debug_next_page_success", new_index=self.file_handler.current_index))
            self.current_page = self.file_handler.current_index + 1
            logger.info(get_log_text("debug_next_page_calling_update_image", current_index=self.file_handler.current_index))
            self.update_image()
            logger.info(get_log_text("debug_next_page_update_image_completed"))
            self._update_page_slider()
            self._update_image_list_dialog()
            self._update_image_slide_sidebar()
            self._notify_plugin_current_changed()
        else:
            logger.info(get_log_text("main_window_already_at_last_page"))
            logger.info(get_log_text("debug_next_page_failed", current_index=self.file_handler.current_index, total_files=len(self.file_handler.current_files)))
            # 改ページが失敗した場合は読み込みフラグをリセット
            self.image_view._is_loading = False
    def prev_page(self):
        """前のページへ"""
        if not self.file_handler:
            logger.warning(get_log_text("main_window_no_file_handler_warning"))
            return
        self._align_current_spread_index()
        moved = False
        if self._is_spread_mode():
            target = self._prev_spread_index()
            if target is not None:
                self._apply_spread_axis_flags(going_next=False, old_index=self.file_handler.current_index, target=target)
            moved = target is not None and self.file_handler.go_to_page(target)
        else:
            moved = self.file_handler.prev_file()
        if moved:
            logger.info(get_log_text("main_window_moving_to_prev_page"))
            self.current_page = self.file_handler.current_index + 1
            self.update_image()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._update_image_slide_sidebar()
            self._notify_plugin_current_changed()
        else:
            logger.info(get_log_text("main_window_already_at_first_page"))
            # 改ページが失敗した場合は読み込みフラグをリセット
            self.image_view._is_loading = False
    def zoom_in(self):
        """Zoom in"""
        self.image_view.zoom_in()
    def zoom_out(self):
        """Zoom out"""
        self.image_view.zoom_out()
    def rotate_right(self):
        """右回転（90度）"""
        self.current_rotation_angle = (self.current_rotation_angle + 90) % 360
        self.image_view.set_rotation(self.current_rotation_angle)
        logger.info(get_log_text("main_window_rotate_right", new_angle=self.current_rotation_angle))
    def rotate_left(self):
        """左回転（90度）"""
        self.current_rotation_angle = (self.current_rotation_angle - 90) % 360
        self.image_view.set_rotation(self.current_rotation_angle)
        logger.info(get_log_text("main_window_rotate_left", new_angle=self.current_rotation_angle))
    def next_file(self):
        """次のファイル"""
        if not self.file_handler:
            return
        self._align_current_spread_index()
        moved = False
        if self._is_spread_mode():
            target = self._next_spread_index()
            if target is not None:
                self._apply_spread_axis_flags(going_next=True, old_index=self.file_handler.current_index, target=target)
            moved = target is not None and self.file_handler.go_to_page(target)
        else:
            moved = self.file_handler.next_file()
        if moved:
            self.current_page = self.file_handler.current_index + 1
            self.update_image()
    def prev_file(self):
        """前のファイル"""
        if not self.file_handler:
            return
        self._align_current_spread_index()
        moved = False
        if self._is_spread_mode():
            target = self._prev_spread_index()
            if target is not None:
                self._apply_spread_axis_flags(going_next=False, old_index=self.file_handler.current_index, target=target)
            moved = target is not None and self.file_handler.go_to_page(target)
        else:
            moved = self.file_handler.prev_file()
        if moved:
            self.current_page = self.file_handler.current_index + 1
            self.update_image()

    def first_page(self):
        """最初のページに戻る"""
        if not self.file_handler or not self.file_handler.current_files:
            logger.warning(get_log_text("main_window_no_file_handler_warning"))
            return
        if len(self.file_handler.current_files) > 0:
            self._clear_spread_force_single()
            self.file_handler.current_index = 0
            self.current_page = 1
            self.update_image()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._notify_plugin_current_changed()
            logger.info(get_log_text("main_window_moved_to_first_page"))

    def last_page(self):
        """最後のページに移動"""
        if not self.file_handler or not self.file_handler.current_files:
            logger.warning(get_log_text("main_window_no_file_handler_warning"))
            return
        if len(self.file_handler.current_files) > 0:
            last_index = len(self.file_handler.current_files) - 1
            self._clear_spread_force_single()
            self.file_handler.current_index = last_index
            self.current_page = last_index + 1
            self.update_image()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._notify_plugin_current_changed()
            logger.info(get_log_text("main_window_moved_to_last_page"))

    def toggle_page_slider_dock(self):
        """ページスライダードックの表示/非表示を切り替え"""
        if not hasattr(self, "page_slider_dock"):
            return
        if self.page_slider_dock.isVisible():
            self.page_slider_dock.hide()
            self.page_slider_action.setChecked(False)
        else:
            self.page_slider_dock.show()
            self.page_slider_action.setChecked(True)
            self._update_page_slider()

    def _on_page_slider_dock_visibility_changed(self, visible):
        if hasattr(self, "page_slider_action"):
            self.page_slider_action.setChecked(visible)
        if visible:
            self._update_page_slider()

    def _on_page_slider_floating(self, floating):
        if not hasattr(self, "page_slider"):
            return
        self.page_slider.set_compact(not floating)
        if floating:
            self.page_slider_dock.resize(300, 140)

    def _apply_sidebar_dock_corners(self):
        """左右サイドバーを優先し、上下スライダーは残り幅だけにする。"""
        self.setCorner(Qt.Corner.TopLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.TopRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)
        self.setCorner(Qt.Corner.BottomLeftCorner, Qt.DockWidgetArea.LeftDockWidgetArea)
        self.setCorner(Qt.Corner.BottomRightCorner, Qt.DockWidgetArea.RightDockWidgetArea)

    def _update_page_slider(self):
        """ページスライダーを現在タブの handler で更新"""
        if hasattr(self, "page_slider_dock") and self.page_slider_dock.isVisible():
            self.page_slider.file_handler = self.file_handler
            self.page_slider.refresh()

    def _update_image_list_dialog(self):
        """画像一覧ダイアログを更新"""
        if self.image_list_dialog and not self.image_list_dialog.isHidden():
            if self.file_handler and self.file_handler.current_files:
                new_image_paths = [str(f) for f in self.file_handler.current_files]
                self.image_list_dialog.refresh_file_list(new_image_paths, self.file_handler)
            else:
                # ファイルがない場合はダイアログを閉じる
                self.image_list_dialog.close()
    
    def _update_image_slide_sidebar(self):
        """画像スライドサイドバーを更新"""
        if hasattr(self, 'image_slide_sidebar') and self.image_slide_sidebar:
            # サイドバーが表示されていない場合は処理をスキップ
            if not self.image_slide_dock.isVisible():
                logger.info(get_log_text("main_window_image_slide_sidebar_update_skipped_not_visible"))
                return
                
            if self.file_handler and self.file_handler.current_files:
                self.image_slide_sidebar.update_file_list(self.file_handler)
                self.image_slide_sidebar.set_current_page(self.file_handler.current_index)
            else:
                self.image_slide_sidebar.update_file_list(None)
    
    def _update_image_slide_sidebar_on_show(self):
        """画像スライドサイドバーが表示された時の更新処理"""
        if hasattr(self, 'image_slide_sidebar') and self.image_slide_sidebar:
            if self.file_handler and self.file_handler.current_files:
                # サイドバーが表示された時に最新のファイル情報で更新
                self.image_slide_sidebar.update_file_list(self.file_handler)
                self.image_slide_sidebar.set_current_page(self.file_handler.current_index)
    
    def set_page_number(self, page_number: int):
        """指定されたページ番号に移動"""
        if not self.file_handler or not self.file_handler.current_files:
            return
        # ページ番号を0ベースのインデックスに変換
        target_index = page_number - 1
        # インデックスの範囲チェック
        if 0 <= target_index < len(self.file_handler.current_files):
            self._clear_spread_force_single()
            self.file_handler.current_index = target_index
            self.current_page = page_number
            self.update_image()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._notify_plugin_current_changed()
            logger.info(get_log_text("main_window_page_set_to", page_number=page_number, target_index=target_index))
        else:
            # 指定されたページが存在しない場合は1ページ目に移動
            if len(self.file_handler.current_files) > 0:
                self.file_handler.current_index = 0
                self.current_page = 1
                self.update_image()
                self._update_page_slider()
                self._update_image_list_dialog()
                self._notify_plugin_current_changed()
                logger.info(get_log_text("main_window_page_not_found_moved_to_1", page_number=page_number))
            else:
                QMessageBox.warning(self, get_text("dialogs.error"), get_text("ui.page_not_exists").format(page_number=page_number))
    def setup_window_mode(self):
        """ウィンドウモードの設定"""
        # フルスクリーンモードの設定
        if self.config.window.get("mode") == "fullscreen":
            self.showFullScreen()
            self.is_fullscreen = True
        else:
            self.showNormal()
            self.is_fullscreen = False
    def toggle_fullscreen(self):
        """フルスクリーンの切り替え"""
        if self.is_fullscreen:
            restore = getattr(self, "_fullscreen_restore", None) or {}
            if restore.get("maximized"):
                self.showMaximized()
            else:
                self.showNormal()
            self.is_fullscreen = False
            # メニューバーを表示
            self.menuBar().show()
            # フルスクリーン終了時はマウスロックを無効にする
            if self.mouse_locked:
                self.disable_mouse_lock()
                self.mouse_lock_action.setChecked(False)
            self._restore_after_fullscreen()
        else:
            self._snapshot_pre_fullscreen()
            self.showFullScreen()
            self.is_fullscreen = True
            # メニューバーを非表示
            self.menuBar().hide()
            # フルスクリーン時はマウスロックを自動的に有効にする
            if not self.mouse_locked:
                self.enable_mouse_lock()
                self.mouse_lock_action.setChecked(True)
            
            # フルスクリーン時はダイアログを閉じる
            self._close_dialogs_on_fullscreen()
        self._sync_tab_bar()

    def _builtin_docks(self):
        return (
            ("bookmark_dock", "bookmark_action"),
            ("history_dock", "history_action"),
            ("tab_list_dock", "tab_list_action"),
            ("image_slide_dock", "image_slide_action"),
            ("page_slider_dock", "page_slider_action"),
        )

    def _snapshot_pre_fullscreen(self):
        docks = []
        for name, _action in self._builtin_docks():
            dock = getattr(self, name, None)
            if dock is not None and dock.isVisible():
                docks.append(name)
        self._fullscreen_restore = {
            "maximized": bool(
                self.isMaximized()
                or (self.windowState() & Qt.WindowState.WindowMaximized)
            ),
            "docks": docks,
            "plugin_sidebars": [],
        }

    def _restore_after_fullscreen(self):
        state = getattr(self, "_fullscreen_restore", None)
        if not state:
            return
        mapping = dict(self._builtin_docks())
        for name in state.get("docks") or []:
            dock = getattr(self, name, None)
            action = getattr(self, mapping.get(name, ""), None)
            if dock is None:
                continue
            dock.show()
            if action is not None:
                action.setChecked(True)
        session = getattr(self, "plugin_session", None)
        if session is not None:
            session.restore_sidebars(state.get("plugin_sidebars"))
        if hasattr(self, "image_slide_dock") and self.image_slide_dock.isVisible():
            self._update_image_slide_sidebar_on_show()
        if hasattr(self, "page_slider_dock") and self.page_slider_dock.isVisible():
            self._update_page_slider()
        self._fullscreen_restore = None

    def _close_dialogs_on_fullscreen(self):
        """フルスクリーン時にダイアログとドックを閉じる"""
        # 画像一覧ダイアログを閉じる
        if self.image_list_dialog and not self.image_list_dialog.isHidden():
            self.image_list_dialog.close()
        
        # その他の開いているダイアログを閉じる
        for child in self.findChildren(QDialog):
            if child.isVisible() and child is not self.image_list_dialog:
                child.close()
        
        # 履歴、ブックマーク、画像スライド、商品情報のドックを閉じる
        if hasattr(self, 'bookmark_dock') and self.bookmark_dock.isVisible():
            self.bookmark_dock.hide()
            self.bookmark_action.setChecked(False)
        
        if hasattr(self, 'history_dock') and self.history_dock.isVisible():
            self.history_dock.hide()
            self.history_action.setChecked(False)

        if hasattr(self, 'tab_list_dock') and self.tab_list_dock.isVisible():
            self.tab_list_dock.hide()
            self.tab_list_action.setChecked(False)
        
        if hasattr(self, 'image_slide_dock') and self.image_slide_dock.isVisible():
            self.image_slide_dock.hide()
            self.image_slide_action.setChecked(False)

        if hasattr(self, "page_slider_dock") and self.page_slider_dock.isVisible():
            if not self.config.viewer.get("show_page_slider_in_fullscreen", False):
                self.page_slider_dock.hide()
                self.page_slider_action.setChecked(False)
        
        session = getattr(self, "plugin_session", None)
        if session is not None:
            hidden = session.hide_visible_sidebars()
            if getattr(self, "_fullscreen_restore", None) is not None:
                self._fullscreen_restore["plugin_sidebars"] = hidden

    def mousePressEvent(self, event):
        shortcuts = self.config.shortcuts
        if not shortcuts:
            super().mousePressEvent(event)
            return
        mouse_text = self.mouse_to_string(event)
        for action_name, shortcuts_list in shortcuts.items():
            if mouse_text in shortcuts_list:
                if self.run_window_action(action_name):
                    event.accept()
                    return
                if action_name == Actions.TOGGLE_BOOKMARK.value:
                    self.toggle_bookmark()
                elif action_name == Actions.REOPEN_LAST_FILE.value:
                    self.reopen_last_file()
                elif action_name == Actions.NEXT_PAGE.value:
                    self.next_page()
                elif action_name == Actions.PREV_PAGE.value:
                    self.prev_page()
                elif action_name == Actions.NEXT_FILE.value:
                    self.next_file()
                elif action_name == Actions.PREV_FILE.value:
                    self.prev_file()
                elif action_name == Actions.ZOOM_IN.value:
                    self.zoom_in()
                elif action_name == Actions.ZOOM_OUT.value:
                    self.zoom_out()
                elif action_name == Actions.RESET_ZOOM.value:
                    self.zoom_reset()
                elif action_name == Actions.ROTATE_RIGHT.value:
                    self.rotate_right()
                elif action_name == Actions.ROTATE_LEFT.value:
                    self.rotate_left()
                elif action_name == Actions.FULLSCREEN.value:
                    self.toggle_fullscreen()
                elif action_name == Actions.CLOSE_APP.value:
                    self.close_application()
                elif action_name == Actions.MIN_SCALE_TOGGLE.value:
                    self.toggle_min_scale()
                elif action_name == Actions.NEXT_COMIC.value:
                    self.next_comic()
                elif action_name == Actions.PREV_COMIC.value:
                    self.prev_comic()
                elif action_name == Actions.FIRST_PAGE.value:
                    self.first_page()
                elif action_name == Actions.LAST_PAGE.value:
                    self.last_page()
                elif action_name == Actions.PAGE_SLIDER_DIALOG.value:
                    self.toggle_page_slider_dock()
                elif action_name == Actions.IMAGE_SLIDE_SIDEBAR.value:
                    self.toggle_image_slide_dock()
                elif self._is_page_mode_action(action_name):
                    self.handle_page_mode_action(action_name)

                event.accept()
                return
        super().mousePressEvent(event)
    def mouse_to_string(self, event):
        """マウスイベントを文字列に変換"""
        if event.button() == Qt.LeftButton:
            return MouseButtons.LEFT.value
        elif event.button() == Qt.RightButton:
            return MouseButtons.RIGHT.value
        elif event.button() == Qt.MiddleButton:
            return MouseButtons.MIDDLE.value
        elif event.button() == Qt.XButton1:
            return MouseButtons.X1.value
        elif event.button() == Qt.XButton2:
            return MouseButtons.X2.value
        return ""
    def mouseMoveEvent(self, event):
        """マウス移動時の処理"""
        if self.mouse_locked and self.mouse_lock_center:
            # ジェスチャーがアクティブな場合はマウスロックを一時的にバイパス
            if self.gesture_active:
                logger.info(get_log_text("main_window_mouse_lock_gesture_bypass"))
                logger.info(get_log_text("main_window_mouse_lock_move_allowed"))
                super().mouseMoveEvent(event)
            else:
                # マウスを中心位置に戻す（より強制的に）
                global_pos = self.mapToGlobal(self.mouse_lock_center)
                QCursor.setPos(global_pos)
                logger.info(get_log_text("main_window_mouse_lock_move_suppressed"))
                # イベントを消費して、他の処理を防ぐ
                event.accept()
        else:
            super().mouseMoveEvent(event)
    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event)
    def wheelEvent(self, event):
        """ホイールイベントをショートカットとして処理"""
        shortcuts = self.config.shortcuts
        if not shortcuts:
            super().wheelEvent(event)
            return
        if event.angleDelta().y() > 0:
            wheel_text = MouseButtons.WHEEL_UP.value
        else:
            wheel_text = MouseButtons.WHEEL_DOWN.value
        for action_name, shortcuts_list in shortcuts.items():
            if wheel_text in shortcuts_list:
                if action_name == Actions.NEXT_PAGE.value:
                    self.next_page()
                elif action_name == Actions.PREV_PAGE.value:
                    self.prev_page()
                elif action_name == Actions.ZOOM_IN.value:
                    self.zoom_in()
                elif action_name == Actions.ZOOM_OUT.value:
                    self.zoom_out()
                event.accept()
                return
        super().wheelEvent(event)
    def setup_shortcuts(self):
        """ショートカットキーの設定"""
        # 既存のアクションをクリア
        for action in self.actions():
            self.removeAction(action)
        # QActionへのショートカット割り当ては廃止
        # すべてkeyPressEventで判定
        # 既存のkeyPressEventで全てのショートカットを判定するのでOK
    def get_action_name(self, action_name):
        """アクション名を取得"""
        return get_action_display_name(action_name)
    def keyPressEvent(self, event):
        shortcuts = self.config.shortcuts
        if not shortcuts:
            super().keyPressEvent(event)
            return
        key_text = key_to_string(event)
        # フルスクリーンのReturnはここで直接判定
        if Actions.FULLSCREEN.value in shortcuts and key_text.lower() in [sc.lower() for sc in shortcuts[Actions.FULLSCREEN.value] if sc.lower() in ["return", "enter"]]:
            self.toggle_fullscreen()
            event.accept()
            return
        # image_listアクションも判定
        if Actions.IMAGE_LIST.value in shortcuts and key_text in shortcuts[Actions.IMAGE_LIST.value]:
            self.show_image_list_dialog()
            event.accept()
            return
        # reopen_last_fileアクションも判定
        if Actions.REOPEN_LAST_FILE.value in shortcuts and key_text in shortcuts[Actions.REOPEN_LAST_FILE.value]:
            self.reopen_last_file()
            event.accept()
            return
        # toggle_bookmarkアクションも判定
        if Actions.TOGGLE_BOOKMARK.value in shortcuts and key_text in shortcuts[Actions.TOGGLE_BOOKMARK.value]:
            self.toggle_bookmark()
            event.accept()
            return
        # toggle_bookmark_dockアクションも判定
        if Actions.TOGGLE_BOOKMARK_DOCK.value in shortcuts and key_text in shortcuts[Actions.TOGGLE_BOOKMARK_DOCK.value]:
            self.toggle_bookmark_dock()
            event.accept()
            return
        # toggle_history_dockアクションも判定
        if Actions.TOGGLE_HISTORY_DOCK.value in shortcuts and key_text in shortcuts[Actions.TOGGLE_HISTORY_DOCK.value]:
            self.toggle_history_dock()
            event.accept()
            return
        # toggle_image_slide_sidebarアクションも判定
        if Actions.IMAGE_SLIDE_SIDEBAR.value in shortcuts and key_text in shortcuts[Actions.IMAGE_SLIDE_SIDEBAR.value]:
            self.toggle_image_slide_dock()
            event.accept()
            return

        # new_windowアクションも判定
        if Actions.NEW_WINDOW.value in shortcuts and key_text in shortcuts[Actions.NEW_WINDOW.value]:
            self.new_window()
            event.accept()
            return
        # toggle_mouse_lockアクションも判定
        if Actions.TOGGLE_MOUSE_LOCK.value in shortcuts and key_text in shortcuts[Actions.TOGGLE_MOUSE_LOCK.value]:
            self.toggle_mouse_lock()
            event.accept()
            return
        # ショートカットを検索
        matched_actions = [
            action_name
            for action_name, shortcuts_list in shortcuts.items()
            if key_text in (shortcuts_list or [])
        ]
        for action_name in matched_actions:
            if self.run_window_action(action_name):
                event.accept()
                return
        for action_name in matched_actions:
            if action_name == Actions.NEXT_PAGE.value:
                self.next_page()
            elif action_name == Actions.PREV_PAGE.value:
                self.prev_page()
            elif action_name == Actions.NEXT_FILE.value:
                self.next_file()
            elif action_name == Actions.PREV_FILE.value:
                self.prev_file()
            elif action_name == Actions.ZOOM_IN.value:
                self.zoom_in()
            elif action_name == Actions.ZOOM_OUT.value:
                self.zoom_out()
            elif action_name == Actions.RESET_ZOOM.value:
                self.zoom_reset()
            elif action_name == Actions.ROTATE_RIGHT.value:
                self.rotate_right()
            elif action_name == Actions.ROTATE_LEFT.value:
                self.rotate_left()
            elif action_name == Actions.FULLSCREEN.value:
                self.toggle_fullscreen()
            elif action_name == Actions.CLOSE_APP.value:
                self.close_application()
            elif action_name == Actions.MIN_SCALE_TOGGLE.value:
                self.toggle_min_scale()
            elif action_name == Actions.NEXT_COMIC.value:
                self.next_comic()
            elif action_name == Actions.PREV_COMIC.value:
                self.prev_comic()
            elif action_name == Actions.ALWAYS_ON_TOP.value:
                self.toggle_always_on_top()
            elif action_name == Actions.REOPEN_LAST_FILE.value:
                self.reopen_last_file()
            elif action_name == Actions.TOGGLE_BOOKMARK.value:
                self.toggle_bookmark()
            elif action_name == Actions.TOGGLE_BOOKMARK_DOCK.value:
                self.toggle_bookmark_dock()
            elif action_name == Actions.TOGGLE_HISTORY_DOCK.value:
                self.toggle_history_dock()
            elif action_name == Actions.TOGGLE_TAB_LIST_DOCK.value:
                self.toggle_tab_list_dock()
            elif action_name == Actions.NEW_WINDOW.value:
                self.new_window()
            elif action_name == Actions.TOGGLE_MOUSE_LOCK.value:
                self.toggle_mouse_lock()
            elif action_name == Actions.FIRST_PAGE.value:
                self.first_page()
            elif action_name == Actions.LAST_PAGE.value:
                self.last_page()
            elif action_name == Actions.PAGE_SLIDER_DIALOG.value:
                self.toggle_page_slider_dock()
            elif action_name == Actions.IMAGE_SLIDE_SIDEBAR.value:
                self.toggle_image_slide_dock()
            elif self._is_page_mode_action(action_name):
                self.handle_page_mode_action(action_name)
            else:
                continue
            event.accept()
            return
        super().keyPressEvent(event)

    def show_settings_dialog(self):
        """設定ダイアログを表示"""
        dialog = SettingsDialog(self.config, self)
        if dialog.exec():
            self.save_config()
            self.apply_loaded_profile_config()
    # def resizeEvent(self, event):
    #     super().resizeEvent(event)
    #     # ウィンドウサイズをconfigに保存
    #     self.config.window["width"] = self.width()
    #     self.config.window["height"] = self.height()
    #     # config.yamlに即時保存
    #     config_path = get_project_root() / "config.yaml"
    #     with open(config_path, "w", encoding="utf-8") as f:
    #         yaml.dump(self.config.to_dict(), f, allow_unicode=True) 
    def toggle_always_on_top(self):
        is_checked = self.always_on_top_action.isChecked()
        self.setWindowFlag(Qt.WindowStaysOnTopHint, is_checked)
        self.show()  # フラグ変更後はshow()で反映
        self.config.window["always_on_top"] = is_checked
        self.save_config() 
    def show_image_list_dialog(self):
        if not self.file_handler or not self.file_handler.current_files:
            return
        
        # 既にダイアログが開いている場合は前面に出す
        if self.image_list_dialog and not self.image_list_dialog.isHidden():
            self.image_list_dialog.raise_()
            self.image_list_dialog.activateWindow()
            return
        
        def on_select(idx):
            self._clear_spread_force_single()
            self.file_handler.current_index = idx
            self.current_page = idx + 1
            self.update_image()
            self._update_page_slider()
        
        self.image_list_dialog = ImageListDialog([str(f) for f in self.file_handler.current_files], self, on_select=on_select, file_handler=self.file_handler, config=self.config)
        
        # ダイアログが閉じられた時に参照をクリア
        self.image_list_dialog.finished.connect(lambda: setattr(self, 'image_list_dialog', None))
        
        self.image_list_dialog.show()  # モードレスダイアログとして表示
    def show_gesture_dialog(self):
        """ジェスチャー設定ダイアログを表示"""
        dialog = GestureDialog(self.config, self)
        if dialog.exec() == QDialog.Accepted:
            self.config.gesture_map = dialog.get_gesture_map()
            self.save_config()
    
    def open_manual(self):
        """マニュアルをデフォルトブラウザで開く"""
        try:
            # 現在の言語設定を取得
            from ez_co.utils.language_manager import language_manager
            import locale
            
            current_lang = language_manager.get_current_language()
            
            # 言語に応じてファイル名を決定
            if current_lang == "ja":
                manual_file = "Manual(JP).html"
            elif current_lang == "system":
                # システムのデフォルト言語を確認
                try:
                    system_lang = locale.getdefaultlocale()[0]
                    if system_lang and system_lang.startswith('ja'):
                        manual_file = "Manual(JP).html"
                    else:
                        manual_file = "Manual(EN).html"
                except Exception:
                    manual_file = "Manual(JP).html"  # デフォルトは日本語
            else:
                manual_file = "Manual(EN).html"
            
            # マニュアルファイルのパスを構築
            project_root = get_project_root()
            
            # 実行環境に応じてパスを選択
            if is_nuitka():
                # 実行版: UserManual/Manual(JP).html
                manual_path = project_root / "UserManual" / manual_file
            else:
                # 開発版: resources/UserManual/Manual(JP).html  
                manual_path = project_root / "resources" / "UserManual" / manual_file
            
            if manual_path.exists():
                # file://スキームでURLを構築
                manual_url = f"file:///{manual_path.as_posix()}"
                webbrowser.open(manual_url)
                logger.info(get_log_text("main_window_manual_opened", path=manual_path))
            else:
                # ファイルが見つからない場合はエラーメッセージを表示
                QMessageBox.warning(
                    self,
                    get_text("ui.error"),
                    get_text("ui.manual_not_found", file=manual_file)
                )
                logger.warning(get_log_text("main_window_manual_not_found", path=manual_path))
                
        except Exception as e:
            logger.error(get_log_text("main_window_manual_open_failed", error=str(e)))
            QMessageBox.critical(
                self,
                get_text("ui.error"),
                get_text("ui.manual_open_error", error=str(e))
            )

    def show_about_dialog(self):
        """ヘルプのバージョン表示。"""
        AboutDialog(self).exec()
    
    def show_plugin_dialog(self):
        """プラグイン設定ダイアログを開き、適用後にセッションへ載せ替えを任せる。"""
        dialog = PluginDialog(self.config, self)
        dialog.applied.connect(self._on_plugin_dialog_applied)
        result = dialog.exec()
        changed = False
        reload_sources = False
        if result == QDialog.Accepted:
            reload_sources = dialog.has_source_choice_changes()
            changed = dialog.has_changes() if hasattr(dialog, "has_changes") else dialog.has_handler_changes()
            dialog.apply_to_config()
        self.save_config()
        if result == QDialog.Accepted and changed:
            self._reload_after_plugin_config(reload_sources=reload_sources)

    def _on_plugin_dialog_applied(self):
        """適用ボタンからの変更を保存し、プラグインを載せ替える。"""
        dialog = self.sender()
        reload_sources = bool(getattr(dialog, "last_applied_source_changes", False))
        self.save_config()
        self._reload_after_plugin_config(reload_sources=reload_sources)

    def _reload_after_plugin_config(self, reload_sources=False):
        """プラグイン設定変更後の再読込をセッションに渡す。"""
        session = getattr(self, "plugin_session", None)
        if session is not None:
            session.after_config_change(reload_sources=reload_sources)

    def _reload_open_files_after_plugin_change(self):
        """プラグイン優先度の変更後、開いているタブを再読み込みする。"""
        current = self.tab_widget.currentIndex() if hasattr(self, "tab_widget") else 0
        if hasattr(self, "tab_widget"):
            for index in range(self.tab_widget.count()):
                self.tab_widget.blockSignals(True)
                self.tab_widget.setCurrentIndex(index)
                self.tab_widget.blockSignals(False)
                self._reload_current_pane_files()
            if 0 <= current < self.tab_widget.count():
                self.tab_widget.setCurrentIndex(current)
        else:
            self._reload_current_pane_files()

    def _reload_current_pane_files(self, page=None):
        """現在のタブのファイルを再読み込みする。"""
        if not self.file_handler or not self.file_handler.current_files:
            return False
        comic = self._get_current_comic_path()
        if comic is None:
            return False
        if page is not None:
            try:
                page = int(page)
            except (TypeError, ValueError):
                page = self.file_handler.current_index + 1
        else:
            page = self.file_handler.current_index + 1
        path = str(comic)
        if not self._check_file_exists(path):
            return False
        # load_file は同一パスだとページ移動だけするので、強制的に開き直す
        self.current_file_path = None
        if comic.is_dir():
            self.open_files([path])
            if not self.file_handler or not self.file_handler.current_files:
                return False
            target = min(max(page - 1, 0), len(self.file_handler.current_files) - 1)
            self.file_handler.current_index = target
            self.current_page = target + 1
            self.load_current_page()
            self._update_page_slider()
            self._update_image_list_dialog()
            self._update_image_slide_sidebar()
            self._sync_current_tab_title()
            self._notify_plugin_current_changed()
            return True
        self.load_file(path, page, restore_history=False)
        self._update_image_list_dialog()
        self._update_image_slide_sidebar()
        self._sync_current_tab_title()
        return True
    def _resizeEvent_with_overlay(self, event):
        if hasattr(super(), 'resizeEvent'):
            super().resizeEvent(event)
        self.gesture_overlay.setGeometry(self.rect())
        self.gesture_overlay.raise_()
        # 中央メッセージの位置を更新
        self._update_center_message_position()
    def show_overlay_message(self, message, rect=None):
        """オーバーレイメッセージを表示"""
        self.gesture_overlay.show_message(message, rect)
    def hide_overlay_message(self):
        """オーバーレイメッセージを非表示"""
        self.gesture_overlay.hide_message()
    def _update_center_message_position(self):
        pane = self.current_pane
        if pane is not None:
            pane._update_center_message_position()

    def show_center_message(self, message):
        """現在のタブ中央にメッセージを表示（背景なし）"""
        if hasattr(self, 'image_view') and self.image_view:
            self.image_view.set_image(None)
        self.setWindowTitle(get_text('app_name'))
        self.current_file_path = None
        if hasattr(self, 'file_handler') and self.file_handler:
            self.file_handler.current_files = []
            self.file_handler.current_index = 0
        pane = self.current_pane
        if pane is not None:
            pane.show_center_message(message)
        self._update_page_slider()
        self._update_save_session_action()

    def hide_center_message(self):
        """現在のタブの中央メッセージを非表示"""
        pane = self.current_pane
        if pane is not None:
            pane.hide_center_message()
    def _clamp_window_geometry(self, x: int, y: int, width: int, height: int):
        min_width = int(self.config.window.get("min_width", 400))
        min_height = int(self.config.window.get("min_height", 300))
        width = max(width, min_width)
        height = max(height, min_height)
        screen = QApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            width = min(width, avail.width())
            height = min(height, avail.height())
            x = min(max(x, avail.x()), avail.x() + avail.width() - width)
            y = min(max(y, avail.y()), avail.y() + avail.height() - height)
        return x, y, width, height

    def _apply_window_geometry(self):
        self.setMinimumSize(
            self.config.window["min_width"],
            self.config.window["min_height"],
        )
        x, y, width, height = self._clamp_window_geometry(
            int(self.config.window.get("x", 100)),
            int(self.config.window.get("y", 100)),
            int(self.config.window.get("width", 800)),
            int(self.config.window.get("height", 600)),
        )
        self.resize(width, height)
        self.move(x, y)
        restore_maximized = bool(
            self.config.window.get("maximize_on_startup", False)
            or self.config.window.get("maximized", False)
        )
        self._pending_maximize = restore_maximized
        self._window_was_maximized = restore_maximized or self._window_was_maximized

    def showEvent(self, event):
        super().showEvent(event)
        if self._pending_maximize:
            self._pending_maximize = False
            QTimer.singleShot(0, self.showMaximized)

    def _is_window_maximized(self) -> bool:
        return bool(
            self.isMaximized()
            or self._window_was_maximized
            or (self.windowState() & Qt.WindowState.WindowMaximized)
        )

    def _confirm_unmaximize(self):
        if self._closing or self.is_fullscreen or not self.isVisible():
            return
        if not self.isMaximized() and not (self.windowState() & Qt.WindowState.WindowMaximized):
            self._window_was_maximized = False
            self.config.window["maximized"] = False

    def _store_window_geometry(self):
        if self.is_fullscreen:
            return
        maximized = self._is_window_maximized()
        geo = self.normalGeometry() if maximized else self.geometry()
        self.config.window["maximized"] = maximized
        self.config.window["x"] = geo.x()
        self.config.window["y"] = geo.y()
        self.config.window["width"] = geo.width()
        self.config.window["height"] = geo.height()

    def closeEvent(self, event):
        self._closing = True
        self._store_window_geometry()
        # 現在のファイルの履歴を保存
        self.save_current_file_history()
        # マウスロックが有効な場合は無効にして、設定もFalseで保存
        if self.mouse_locked:
            self.disable_mouse_lock()
            self.config.viewer["mouse_lock"] = False
            self.mouse_lock_action.setChecked(False)
            logger.info(get_log_text("main_window_mouse_lock_disabled_on_close"))
        self.save_config()
        super().closeEvent(event)
    def toggle_bookmark_dock(self):
        """ブックマークドックの表示/非表示を切り替え"""
        if self.bookmark_dock.isVisible():
            self.bookmark_dock.hide()
            self.bookmark_action.setChecked(False)
        else:
            self.bookmark_dock.show()
            self.bookmark_action.setChecked(True)
    def toggle_history_dock(self):
        """履歴ドックの表示/非表示を切り替え"""
        if self.history_dock.isVisible():
            self.history_dock.hide()
            self.history_action.setChecked(False)
        else:
            self.history_dock.show()
            self.history_action.setChecked(True)

    def toggle_tab_list_dock(self):
        if self.tab_list_dock.isVisible():
            self.tab_list_dock.hide()
            self.tab_list_action.setChecked(False)
        else:
            self.tab_list_dock.show()
            self.tab_list_action.setChecked(True)
            self._refresh_tab_list()
    
    def toggle_image_slide_dock(self):
        """画像スライドドックの表示/非表示を切り替え"""
        if self.image_slide_dock.isVisible():
            self.image_slide_dock.hide()
            self.image_slide_action.setChecked(False)
        else:
            self.image_slide_dock.show()
            self.image_slide_action.setChecked(True)
            # サイドバーが表示された時に初期ロードを実行
            self._update_image_slide_sidebar_on_show()
    
    def on_image_slide_page_selected(self, page_index):
        """画像スライドサイドバーでページが選択された時の処理"""
        if self.file_handler and 0 <= page_index < len(self.file_handler.current_files):
            self._clear_spread_force_single()
            self.file_handler.current_index = page_index
            self.current_page = page_index + 1
            self.update_image()
            self._update_page_slider()
            logger.info(get_log_text("main_window_page_selected_from_slide", page=self.current_page))
    
    def on_image_slide_dock_visibility_changed(self, visible):
        """画像スライドドックの可視性変更時の処理"""
        # メニューアクションの同期
        self.image_slide_action.setChecked(visible)
        
        # サイドバーが表示された時にサムネイルロードを開始
        if visible:
            self._update_image_slide_sidebar_on_show()
    def open_bookmark(self, file_path: str, page_number: int, new_tab: bool = False):
        """ブックマークを開く"""
        try:
            if new_tab:
                self._ensure_tab_for_new_open()
            # ファイルの存在確認（アーカイブファイルやフォルダも含む）
            if not self._check_file_exists(file_path):
                QMessageBox.warning(self, get_text("dialogs.error"), get_text("dialogs.file_not_found") + "\n" + file_path)
                return
            # フォルダの場合はopen_filesメソッドを使用、ファイルの場合はload_fileメソッドを使用
            if Path(file_path).is_dir():
                self.open_files([file_path])
                # フォルダが開かれた後、ブックマークのページ番号を設定
                if self.file_handler and self.file_handler.current_files:
                    # ページ番号を調整（1ベースから0ベースに変換）
                    target_index = page_number - 1
                    if 0 <= target_index < len(self.file_handler.current_files):
                        self.file_handler.current_index = target_index
                        self.current_page = page_number
                        self.load_current_page()
                        self._update_page_slider()
            else:
                self.load_file(file_path, page_number)
                self._update_page_slider()
            logger.info(get_log_text("main_window_bookmark_opened", file_path=file_path, page_number=page_number))
            # 履歴ツールバーを更新
            if hasattr(self, 'history_toolbar'):
                self.history_toolbar.refresh_history()
            # メインウィンドウにフォーカスを戻す（ショートカットが効くように）
            self._sync_current_tab_title()
            self.setFocus()
            self.activateWindow()
        except Exception as e:
            logger.error(get_log_text("main_window_failed_open_bookmark", error=e))
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_open_error").format(error=str(e)))
    def open_history(self, file_path: str, page_number: int, new_tab: bool = False):
        """履歴を開く"""
        try:
            if new_tab:
                self._ensure_tab_for_new_open()
            logger.info(get_log_text("main_window_opening_history", file_path=file_path, page_number=page_number))
            # ファイルの存在確認（アーカイブファイルやフォルダも含む）
            if not self._check_file_exists(file_path):
                logger.warning(get_log_text("main_window_file_not_found", file_path=file_path))
                QMessageBox.warning(self, get_text("dialogs.error"), get_text("dialogs.file_not_found") + "\n" + file_path)
                return
            logger.info(get_log_text("main_window_file_exists_loading", file_path=file_path))
            # フォルダの場合はopen_filesメソッドを使用、ファイルの場合はload_fileメソッドを使用
            if Path(file_path).is_dir():
                self.open_files([file_path])
                # フォルダが開かれた後、履歴のページ番号を設定
                if self.file_handler and self.file_handler.current_files:
                    # ページ番号を調整（1ベースから0ベースに変換）
                    target_index = page_number - 1
                    if 0 <= target_index < len(self.file_handler.current_files):
                        self.file_handler.current_index = target_index
                        self.current_page = page_number
                        self.load_current_page()
                        self._update_page_slider()
            else:
                self.load_file(file_path, page_number)
                self._update_page_slider()
            logger.info(get_log_text("main_window_history_opened", file_path=file_path, page_number=page_number))
            self._sync_current_tab_title()
            # 履歴ツールバーを更新
            if hasattr(self, 'history_toolbar'):
                self.history_toolbar.refresh_history()
            # メインウィンドウにフォーカスを戻す（ショートカットが効くように）
            self.setFocus()
            self.activateWindow()
        except Exception as e:
            logger.error(get_log_text("main_window_failed_open_history", error=e))
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.history_open_error").format(error=str(e)))
    def reopen_last_file(self):
        """最後に開いたファイルを開く"""
        try:
            latest_history = self.db_manager.get_latest_history()
            if latest_history:
                self.open_history(latest_history['file_path'], latest_history['page_number'])
            else:
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.no_history"))
        except Exception as e:
            logger.error(get_log_text("main_window_failed_reopen_last_file", error=e))
            QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.last_file_open_error").format(error=str(e)))
    def set_current_file(self, file_path: str, page_number: int):
        """現在のファイルとページを設定（ブックマークツールバー用）"""
        self.bookmark_toolbar.current_file = file_path
        self.bookmark_toolbar.current_page = page_number
    def _check_file_exists(self, file_path: str) -> bool:
        from ez_co.handlers.virtual_path_handler import VirtualPathHandler
        logger.info(get_log_text("main_window_exist_check_called", file_path=file_path))
        if VirtualPathHandler.is_virtual_path(file_path):
            logger.info(get_log_text("main_window_detected_archive_path", file_path=file_path))
            result = VirtualPathHandler.parse_virtual_path(file_path)
            logger.info(get_log_text("main_window_virtual_path_parse_result", result=result))
            if result:
                archive_path, _ = result
                logger.info(get_log_text("main_window_archive_path_extracted", archive_path=archive_path))
                exists = archive_path.exists()
                logger.info(get_log_text("main_window_archive_file_exists", archive_path=archive_path, exists=exists))
                return exists
            else:
                logger.warning(get_log_text("main_window_invalid_virtual_archive_path", file_path=file_path))
                return False
        path = Path(file_path)
        logger.info(get_log_text("main_window_path_exists", path_exists=path.exists()))
        logger.info(get_log_text("main_window_path_suffix", path_suffix=path.suffix.lower()))
        if path.exists():
            logger.info(get_log_text("main_window_file_dir_exists", file_path=file_path))
            return True
        if ArchiveInfo.is_archive_file(file_path):
            exists = path.exists()
            logger.info(get_log_text("main_window_archive_file_exists_by_ext", file_path=file_path, exists=exists))
            return exists
        logger.warning(get_log_text("main_window_file_not_found_final", file_path=file_path))
        return False
    def load_file(self, file_path: str, page_number: int = 1, restore_history: bool = True):
        """ファイルを読み込み"""
        if is_session_file(file_path):
            self.restore_session(file_path)
            return
        try:
            # メッセージを非表示
            self.hide_center_message()
            
            # file_handlerが初期化されていない場合は初期化
            self._ensure_file_handler()
            
            # 同じファイルが既に開いている場合は、ページ番号のみ更新
            if (hasattr(self, 'current_file_path') and 
                self.current_file_path and 
                self.current_file_path == file_path):
                logger.info(get_log_text("main_window_file_already_open", file_path=file_path))
                self.current_page = page_number
                self.load_current_page()
                return
            
            # 新しいファイルを読み込む前に、現在のファイルの履歴を保存
            self.save_current_file_history()
            
            # 履歴からページを復元（page_numberが1の場合のみ）
            if restore_history and page_number == 1:
                page_number = self._restore_page_from_history(file_path)
            
            # 新しいファイルを読み込み
            self.current_file_path = file_path
            self.current_page = page_number
            
            # 新しいファイルが開かれる時は回転状態をリセット
            self.current_rotation_angle = 0
            
            # アーカイブの状態をクリア（新しいファイルを開く際に再設定される）
            if self.file_handler:
                self.file_handler.current_archive = None
                self.file_handler.current_archive_path = None
            
            # ファイルが開かれた場合はbase_dir_pathをクリア
            self.base_dir_path = None
            
            # ファイルハンドラーでファイルを開く
            success = self.file_handler.open_file(file_path)
            
            if success:
                # ページ数を取得
                total_pages = self.file_handler.get_total_pages()
                
                # ページ番号を調整
                if page_number > total_pages:
                    page_number = total_pages
                elif page_number < 1:
                    page_number = 1
                    
                self.current_page = page_number
                self.total_pages = total_pages
                
                # UIを更新
                self.update_title()
                self._sync_current_tab_title()
                self.update_page_display()
                self.load_current_page()
                
                # ファイルが正常に読み込まれた後に履歴を保存
                self.save_current_file_history()
                
                # ツールバーを更新
                if hasattr(self, 'bookmark_toolbar'):
                    self.bookmark_toolbar.refresh_bookmarks()
                if hasattr(self, 'history_toolbar'):
                    self.history_toolbar.refresh_history()
                
                # メインウィンドウにフォーカスを戻す（ショートカットが効くように）
                self.setFocus()
                self.activateWindow()
                
                # ページスライダーダイアログの更新
                self._update_page_slider()
                
                logger.info(get_log_text("main_window_file_loaded_successfully", file_path=file_path, page_number=page_number))
            else:
                logger.error(get_log_text("main_window_failed_to_load_file", file_path=file_path))
                # ファイルが開けなかった場合のメッセージ表示
                self.show_unsupported_file_message()
        except Exception as e:
            logger.error(get_log_text("main_window_error_loading_file", error=e))
            self.show_unsupported_file_message()
    def update_title(self):
        """ウィンドウタイトルを更新"""
        if hasattr(self, 'current_file_path') and self.current_file_path:
            file_name = Path(self.current_file_path).name
            page_info = f" - {get_text('ui.page')} {self.current_page}/{self.total_pages}" if hasattr(self, 'total_pages') else ""
            self.setWindowTitle(f"{get_text('app_name')} - {file_name}{page_info}")
        else:
            self.setWindowTitle(get_text('app_name'))
    def update_page_display(self):
        """ページ表示を更新"""
        if hasattr(self, 'current_page') and hasattr(self, 'total_pages'):
            # ページ表示ラベルがあれば更新
            if hasattr(self, 'page_label'):
                if self._has_spread_pair():
                    start = self._spread_display_start(self.file_handler.current_index)
                    self.page_label.setText(f"{start + 1}-{start + 2} / {self.total_pages}")
                else:
                    self.page_label.setText(f"{self.current_page} / {self.total_pages}")
    def load_current_page(self):
        """現在のページを読み込み"""
        if (hasattr(self, 'file_handler') and self.file_handler and 
            hasattr(self, 'current_page') and self.current_page):
            target_index = self.current_page - 1
            self._clear_spread_force_single()
            # ファイルハンドラーでページを読み込み
            success = self.file_handler.go_to_page(target_index)  # 0ベースのインデックス
            if success:
                self.update_image()
            else:
                QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.page_not_exists").format(page_number=self.current_page)) 
    def save_current_file_history(self):
        """現在のファイルの履歴を保存"""
        if (hasattr(self, 'current_file_path') and self.current_file_path and 
            hasattr(self, 'file_handler') and self.file_handler and 
            hasattr(self.file_handler, 'current_index') and 
            self.file_handler.current_files):  # ファイルが実際に読み込まれているかチェック
            # 表示可能なファイルが0件の場合は履歴に保存しない
            if len(self.file_handler.current_files) == 0:
                return
            archive_path = self.file_handler.get_current_archive_path()
            if archive_path:
                file_path = str(archive_path)
            elif self.file_handler.current_archive:
                return
            elif hasattr(self, 'base_dir_path') and self.base_dir_path:
                file_path = self.base_dir_path
            else:
                file_path = self.current_file_path
            # file_handlerの現在のインデックスからページ番号を取得
            page_number = self.file_handler.current_index + 1
            # フォルダかどうかを判定してentry_typeを設定
            entry_type = EntryType.FOLDER.value if Path(file_path).is_dir() else EntryType.FILE.value
            self.add_to_history(file_path, page_number, entry_type=entry_type)
    def _encrypted_password_for_history(self, file_path: str):
        from ez_co.handlers.archive_password import get_session_password
        from ez_co.handlers.virtual_path_handler import VirtualPathHandler
        from ez_co.utils.password_protect import encrypt_secret

        candidates = [file_path]
        archive_path = self.file_handler.get_current_archive_path() if self.file_handler else None
        if archive_path:
            candidates.append(str(archive_path))
        if VirtualPathHandler.is_virtual_path(file_path):
            parsed = VirtualPathHandler.parse_virtual_path(file_path)
            if parsed:
                candidates.append(str(parsed[0]))
        for candidate in candidates:
            password = get_session_password(candidate)
            if password:
                try:
                    return encrypt_secret(password)
                except Exception as exc:
                    logger.error(get_log_text("main_window_archive_password_encrypt_failed", error=exc))
                    return None
        return None

    def add_to_history(self, file_path: str, page_number: int, title: str = None, entry_type: str = EntryType.FILE.value):
        """履歴に追加"""
        try:
            if not title:
                # virtual pathの場合（archive:〜形式）はアーカイブファイル名を使用
                from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                if VirtualPathHandler.is_virtual_path(file_path):
                    result = VirtualPathHandler.parse_virtual_path(file_path)
                    if result:
                        archive_path, _ = result
                        title = archive_path.name
                    else:
                        title = Path(file_path).name
                # アーカイブファイルの場合は適切なタイトルを設定
                elif self.file_handler and self.file_handler.current_archive:
                    # アーカイブ内の画像を表示している場合、アーカイブファイル名を使用
                    archive_path = self.file_handler.get_current_archive_path()
                    if archive_path:
                        title = archive_path.name
                    else:
                        title = Path(file_path).name
                else:
                    title = Path(file_path).name
            # 同じファイル/フォルダの既存の履歴を削除
            self.db_manager.delete_history_by_file_path(file_path, entry_type)
            # 新しい履歴を追加
            encrypted_password = self._encrypted_password_for_history(file_path)
            success = self.db_manager.add_history(
                file_path, page_number, title, entry_type, encrypted_password=encrypted_password
            )
            if success:
                # 履歴の最大数を制限
                max_count = self.config.history.get("max_count", 20)
                self.db_manager.cleanup_old_history(max_count)
                # 履歴ツールバーを更新
                if hasattr(self, 'history_toolbar'):
                    self.history_toolbar.refresh_history()
                logger.info(get_log_text("main_window_history_added", file_path=file_path, page_number=page_number, entry_type=entry_type))
            else:
                logger.error(get_log_text("main_window_failed_add_history", file_path=file_path, page_number=page_number))
        except Exception as e:
            logger.error(get_log_text("main_window_error_adding_history", error=e))
    def toggle_bookmark(self):
        """ブックマークの追加/削除を切り替え"""
        if not self.file_handler or not hasattr(self, 'current_file_path') or not self.current_file_path:
            QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.no_file_opened"))
            return
        # フォルダが開かれている場合はbase_dir_pathを使用、そうでなければcurrent_file_pathを使用
        if hasattr(self, 'base_dir_path') and self.base_dir_path:
            file_path = self.base_dir_path
        else:
            file_path = self.current_file_path
        page_number = self.file_handler.current_index + 1
        # 現在のフォルダIDを取得（最後に使用されたフォルダ）
        current_folder_id = self.db_manager.get_last_used_folder()
        # ブックマークが既に存在するかチェック
        existing_bookmark = self.db_manager.get_bookmark(file_path, page_number)
        if existing_bookmark:
            # ブックマークが存在する場合は削除
            success = self.db_manager.remove_bookmark(file_path, page_number)
            if success:
                self.bookmark_toolbar.refresh_bookmarks()
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.bookmark_delete_success"))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_delete_failed"))
        else:
            # ブックマークが存在しない場合は追加
            # virtual pathの場合（archive:〜形式）はアーカイブファイル名を使用
            if file_path.startswith("archive:"):
                try:
                    from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                    archive_path, internal_path = VirtualPathHandler.parse_virtual_path(file_path)
                    title = archive_path.name
                except Exception as e:
                    logger.error(f"virtual pathの解析に失敗: {file_path}, エラー: {e}")
                    title = Path(file_path).name
            else:
                title = Path(file_path).name
            
            # フォルダかどうかを判定してentry_typeを設定
            entry_type = EntryType.FOLDER.value if Path(file_path).is_dir() else EntryType.FILE.value
            success = self.db_manager.add_bookmark(file_path, page_number, title, current_folder_id, entry_type)
            if success:
                self.bookmark_toolbar.refresh_bookmarks()
                QMessageBox.information(self, get_text("dialogs.information"), get_text("ui.bookmark_add_success"))
            else:
                QMessageBox.critical(self, get_text("dialogs.error"), get_text("ui.bookmark_add_failed"))
    def set_page_mode(self, mode: str):
        """ページモード設定"""
        self.config.display.page_mode = mode
        self.image_view.set_page_mode(mode) 
    def toggle_mouse_lock(self):
        """マウスロックの切り替え"""
        is_checked = self.mouse_lock_action.isChecked()
        self.config.viewer["mouse_lock"] = is_checked
        if is_checked:
            self.enable_mouse_lock()
        else:
            self.disable_mouse_lock()
        self.save_config()
    def enable_mouse_lock(self):
        """マウスロックを有効にする"""
        if self.mouse_locked:
            return
        # フルスクリーン時は自動的に有効にする
        if self.is_fullscreen:
            self.mouse_lock_action.setChecked(True)
            self.config.viewer["mouse_lock"] = True
        # ウィンドウが非アクティブの場合は有効にしない
        if not self.isActiveWindow():
            return
        self.mouse_locked = True
        # 現在のカーソル位置を保存
        cursor_pos = QCursor.pos()
        self.mouse_lock_center = self.mapFromGlobal(cursor_pos)
        # 元のカーソルを保存
        self.original_cursor = self.cursor()
        # カーソルを非表示にする（設定が有効な場合）
        if self.config.viewer.get("mouse_lock_hide_cursor", True):
            self.setCursor(Qt.BlankCursor)
        # マウスを中央に固定
        QCursor.setPos(self.mapToGlobal(self.mouse_lock_center))
        # アプリケーションレベルでのイベントフィルタをインストール
        QApplication.instance().installEventFilter(self)
        logger.info(get_log_text("main_window_mouse_lock_enabled"))
    def disable_mouse_lock(self):
        """マウスロックを無効にする"""
        if not self.mouse_locked:
            return
        self.mouse_locked = False
        # カーソルを元に戻す
        if self.original_cursor:
            self.setCursor(self.original_cursor)
            self.original_cursor = None
        self.mouse_lock_center = None
        # アプリケーションレベルでのイベントフィルタを削除
        QApplication.instance().removeEventFilter(self)
        logger.info(get_log_text("main_window_mouse_lock_disabled"))
    def eventFilter(self, obj, event):
        """アプリケーションレベルでのイベントフィルタ"""
        if self.mouse_locked and self.mouse_lock_center:
            if event.type() == QEvent.Type.MouseMove:
                # ジェスチャーがアクティブな場合はマウスロックを一時的にバイパス
                if self.gesture_active:
                    logger.info(get_log_text("main_window_mouse_lock_gesture_active", gesture_active=self.gesture_active))
                    return False  # イベントを通す
                else:
                    # マウス移動量を計算して画像表示位置に反映
                    current_global_pos = QCursor.pos()
                    center_global_pos = self.mapToGlobal(self.mouse_lock_center)
                    mouse_delta = current_global_pos - center_global_pos
                    
                    # 移動量が十分大きい場合のみ処理（微細な振動を防ぐ）
                    if abs(mouse_delta.x()) > 1 or abs(mouse_delta.y()) > 1:
                        # ImageViewがあり、拡大表示中の場合は画像移動を処理
                        if (hasattr(self, 'image_view') and self.image_view and 
                            hasattr(self.image_view, 'zoom_factor') and 
                            self.image_view.zoom_factor > 1.0 and 
                            hasattr(self.image_view, 'current_qimage') and 
                            self.image_view.current_qimage):
                            
                            # 移動感度を適用
                            sensitivity = self.config.viewer.get("image_move_sensitivity", 2.0) if self.config else 2.0
                            adjusted_delta = mouse_delta * sensitivity
                            
                            # 画像のオフセットを更新（マウス移動と逆方向）
                            self.image_view.image_offset -= adjusted_delta
                            
                            # 画像表示を更新
                            self.image_view.update_image_display()
                            
                            logger.info(get_log_text("main_window_mouse_lock_image_moved", 
                                                   mouse_delta=mouse_delta, 
                                                   adjusted_delta=adjusted_delta,
                                                   new_offset=self.image_view.image_offset))
                    
                    # マウスを中心位置に戻す
                    QCursor.setPos(center_global_pos)
                    return True  # イベントを消費
        return super().eventFilter(obj, event)
    def changeEvent(self, event):
        """ウィンドウ状態変更時の処理"""
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange:
            if not self.is_fullscreen and not self._closing:
                if self.isMaximized() or (self.windowState() & Qt.WindowState.WindowMaximized):
                    self._window_was_maximized = True
                    self.config.window["maximized"] = True
                else:
                    QTimer.singleShot(50, self._confirm_unmaximize)
            # ウィンドウが非アクティブになった場合、マウスロックを無効にする
            if not self.isActiveWindow() and self.mouse_locked:
                self.disable_mouse_lock()
                # メニューのチェック状態も更新
                self.mouse_lock_action.setChecked(False)
    def focusOutEvent(self, event):
        """フォーカスが外れた時の処理"""
        super().focusOutEvent(event)
        # ウィンドウが非アクティブになった場合、マウスロックを無効にする
        if self.mouse_locked:
            self.disable_mouse_lock()
            # メニューのチェック状態も更新
            self.mouse_lock_action.setChecked(False)
    
    def set_gesture_active(self, active: bool):
        """ジェスチャーのアクティブ状態を設定"""
        self.gesture_active = active
        logger.info(get_log_text("main_window_mouse_lock_gesture_active", gesture_active=active))
    
    def is_gesture_active(self) -> bool:
        """ジェスチャーがアクティブかどうかを返す"""
        return self.gesture_active
    def rebuild_menu(self):
        """メニューを再構築（言語変更時など）"""
        menubar = self.menuBar()
        menubar.clear()
        self.setup_menu()

    def _restore_page_from_history(self, file_path: str) -> int:
        """履歴からページ番号を復元"""
        if not self.config.history.get("restore_page_on_reopen", False):
            return 1
        
        # フォルダかファイルかを判定
        entry_type = EntryType.FOLDER.value if Path(file_path).is_dir() else EntryType.FILE.value
        
        # 履歴からページ番号を取得
        history_entry = self.db_manager.get_history_by_file_path(file_path, entry_type)
        if history_entry:
            page_number = history_entry['page_number']
            logger.info(get_log_text("main_window_restored_page_from_history", file_path=file_path, page_number=page_number))
            return page_number
        
        # 履歴がない場合は1ページ目から
        return 1
    
    def get_current_folder_path(self) -> Optional[str]:
        """現在開いているフォルダのパスを取得"""
        try:
            if not self.file_handler or not self.file_handler.current_files:
                return None
            
            # アーカイブ内の場合
            if self.file_handler.current_archive:
                archive_path = self.file_handler.get_current_archive_path()
                if archive_path:
                    return str(archive_path.parent)
            
            # フォルダから開いた場合
            if self.base_dir_path:
                return self.base_dir_path
            
            # 単独ファイルの場合
            current_file = self.file_handler.current_files[self.file_handler.current_index]
            
            # virtual pathの場合（archive://path|filename形式）
            if isinstance(current_file, (str, Path)) and str(current_file).startswith("archive://"):
                from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                result = VirtualPathHandler.parse_virtual_path(str(current_file))
                if result:
                    archive_path, _ = result
                    return str(archive_path.parent)
            
            if isinstance(current_file, str):
                return str(Path(current_file).parent)
            else:
                return str(current_file.parent)
        except Exception as e:
            logger.error(get_log_text("folder_path_get_error", error=e))
            return None
    
    def has_info_json(self) -> bool:
        """現在のフォルダにinfo.jsonがあるかチェック"""
        paths_to_check = self._get_info_file_check_paths()
        
        for folder_path in paths_to_check:
            info_json_path = folder_path / "info.json"
            if info_json_path.exists():
                return True
        
        return False
    
    def has_info_url_or_json(self) -> bool:
        """現在のフォルダにinfo.urlまたはinfo.jsonがあるかチェック"""
        paths_to_check = self._get_info_file_check_paths()
        
        for folder_path in paths_to_check:
            info_json_path = folder_path / "info.json"
            info_url_path = folder_path / "info.url"
            if info_json_path.exists() or info_url_path.exists():
                return True
        
        return False
    
    def _get_info_file_check_paths(self) -> list:
        """info.jsonをチェックするパスのリストを取得"""
        paths_to_check = []
        
        try:
            if not self.file_handler or not self.file_handler.current_files:
                logger.info(get_log_text("info_json_check_no_file_handler"))
                return paths_to_check
            
            current_file = self.file_handler.current_files[self.file_handler.current_index]
            logger.info(get_log_text("info_json_check_current_file", current_file=current_file))
            
            # virtual pathの場合（archive:\path|filename形式）
            if isinstance(current_file, (str, Path)) and str(current_file).startswith("archive:"):
                logger.info(get_log_text("info_json_check_virtual_path_detected", current_file=current_file))
                from ez_co.handlers.virtual_path_handler import VirtualPathHandler
                result = VirtualPathHandler.parse_virtual_path(str(current_file))
                if result:
                    archive_path, internal_path = result
                    logger.info(get_log_text("info_json_check_archive_path_parsed", 
                                          archive_path=archive_path, internal_path=internal_path))
                    # アーカイブファイルと同じフォルダをチェック
                    paths_to_check.append(archive_path.parent)
                    logger.info(get_log_text("info_json_check_archive_folder_added", 
                                          folder_path=archive_path.parent))
                else:
                    logger.warning(get_log_text("info_json_check_virtual_path_parse_failed", 
                                             current_file=current_file))
            
            # アーカイブ内の場合（従来の方法）
            elif self.file_handler.current_archive:
                logger.info(get_log_text("info_json_check_using_current_archive", 
                                      current_archive=self.file_handler.current_archive))
                archive_path = self.file_handler.get_current_archive_path()
                if archive_path:
                    # アーカイブファイルと同じフォルダをチェック
                    paths_to_check.append(archive_path.parent)
                    logger.info(get_log_text("info_json_check_archive_folder_added", 
                                          folder_path=archive_path.parent))
            
            # フォルダから開いた場合
            elif self.base_dir_path:
                logger.info(get_log_text("info_json_check_using_base_dir_path", 
                                      base_dir_path=self.base_dir_path))
                folder_path = Path(self.base_dir_path)
                # フォルダ内部をチェック
                paths_to_check.append(folder_path)
                logger.info(get_log_text("info_json_check_folder_internal_added", 
                                      folder_path=folder_path))
                # フォルダと同じ階層（親フォルダ）もチェック
                if folder_path.parent != folder_path:  # ルートディレクトリでない場合
                    paths_to_check.append(folder_path.parent)
                    logger.info(get_log_text("info_json_check_parent_folder_added", 
                                          folder_path=folder_path.parent))
            
            # 単独ファイルの場合
            else:
                logger.info(get_log_text("info_json_check_single_file_processing", 
                                      current_file=current_file))
                # 通常のファイルの場合、ファイルと同じフォルダをチェック
                if isinstance(current_file, str):
                    file_path = Path(current_file)
                else:
                    file_path = current_file
                paths_to_check.append(file_path.parent)
                logger.info(get_log_text("info_json_check_file_folder_added", 
                                      folder_path=file_path.parent))
            
            logger.info(get_log_text("info_json_check_paths_list", paths_to_check=paths_to_check))
        except Exception as e:
            logger.error(get_log_text("info_json_check_path_get_error", error=e))
            import traceback
            traceback.print_exc()
        
        return paths_to_check
    
    def update_extensions_menu_actions(self):
        """拡張メニューのアクション有効状態を更新"""
        # RJ拡張機能は削除されたため、この処理は不要
        pass
    

