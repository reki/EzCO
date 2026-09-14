"""プラグインの同意・重複選択・ホスト結線。MainWindow は見ない。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QDockWidget, QMainWindow

from ez_co.plugins.host import make_sidebar_action_id, sidebar_title_stem
from ez_co.plugins.manager import get_plugin_manager
from ez_co.plugins.settings_key import hash_plugin_id
from ez_co.ui.plugins.plugin_conflict_dialog import PluginConflictDialog
from ez_co.ui.plugins.plugin_consent_dialog import PluginConsentDialog
from ez_co.utils.data_location import accept_plugin_consent, plugin_consent_accepted


class PluginSession:
    """起動時の同意／重複と、ウィンドウへの host.bind・ドック載せ。"""

    def __init__(self):
        self._consented = False
        self._consent_known = False
        self._manager = None
        self._host = None
        self._window = None
        self._config = None
        self._sidebars = {}
        self._current = None
        self._reload_current = None
        self._run_action = None
        self._app_config = None
        self._rebuild_menu = None
        self._save_profile = None
        self._restore_docks = None
        self._first_shortcut = None
        self._sidebar_menu = None
        self._setup_shortcuts = None
        self._reload_open_files = None

    def consent_accepted(self) -> bool:
        """導入同意済みか。起動時に一度だけ user.json を見る。"""
        self._ensure_consent_cache()
        return self._consented

    def bootstrap(self, parent, config, rebuild_menu=None, save_profile=None) -> None:
        """同意と重複選択のあと、選ばれたプラグインをロードする。"""
        self._config = config
        self._rebuild_menu = rebuild_menu
        self._save_profile = save_profile
        manager = self._manager_ref()
        just_accepted = False
        self._ensure_consent_cache()
        if manager.candidates and not self._consented:
            dialog = PluginConsentDialog(parent)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            accept_plugin_consent()
            self._consented = True
            just_accepted = True
        if not self._consented:
            return
        unresolved = manager.unresolved_groups(config)
        if unresolved:
            dialog = PluginConflictDialog(unresolved, parent)
            dialog.exec()
            manager.record_choices(dialog.choices(), config)
            if save_profile is not None:
                save_profile()
        manager.load_selected(config)
        if just_accepted and rebuild_menu is not None:
            rebuild_menu()

    def attach(
        self,
        window: QMainWindow,
        *,
        config,
        db_manager=None,
        current=None,
        reload_current=None,
        run_action=None,
        app_config=None,
        restore_docks=None,
        first_shortcut=None,
        sidebar_menu=None,
        setup_shortcuts=None,
        reload_open_files=None,
        rebuild_menu=None,
        save_profile=None,
    ) -> None:
        """ホストをこのウィンドウに結び、UI を有効化する。ロードはしない。"""
        self._window = window
        self._config = config
        self._current = current
        self._reload_current = reload_current
        self._run_action = run_action
        self._app_config = app_config
        self._restore_docks = restore_docks
        self._first_shortcut = first_shortcut
        self._sidebar_menu = sidebar_menu
        self._setup_shortcuts = setup_shortcuts
        self._reload_open_files = reload_open_files
        if rebuild_menu is not None:
            self._rebuild_menu = rebuild_menu
        if save_profile is not None:
            self._save_profile = save_profile
        self._ensure_consent_cache()
        manager = self._manager_ref()
        manager.host.bind(
            parent=window,
            db_manager=db_manager,
            run_action=run_action,
            get_current=current,
            reload_current=reload_current,
            get_app_config=app_config,
            mount_sidebar=self.mount_sidebar,
            unmount_sidebar=self.unmount_sidebar,
            toggle_sidebar=self.toggle_sidebar,
        )
        manager.activate_ui(config)
        if restore_docks is not None:
            restore_docks()
        else:
            self.notify_current_changed()

    def notify_current_changed(self) -> None:
        """開いている path / folder / page をプラグインへ知らせる。"""
        host = self._host
        if host is None:
            return
        current = self._current
        payload = {
            "path": current("path") if current is not None else None,
            "folder": current("folder") if current is not None else None,
            "page": current("page") if current is not None else None,
        }
        host.emit("current_changed", payload)

    def invoke_registered(self, action_id: str) -> bool:
        """プラグイン登録アクションを実行する。未結線なら False。"""
        host = self._host
        if host is None:
            return False
        return host.invoke_registered(action_id)

    def after_config_change(self, reload_sources=False) -> None:
        """プラグイン設定の適用後に UI と開いているファイルを載せ替える。"""
        manager = self._manager_ref()
        config = self._config
        if reload_sources:
            manager.reload_selected(config)
            if self._rebuild_menu is not None:
                self._rebuild_menu()
            if self._setup_shortcuts is not None:
                self._setup_shortcuts()
        manager.activate_ui(config)
        if self._reload_open_files is not None:
            self._reload_open_files()
        self.notify_current_changed()

    def mount_sidebar(self, plugin_id: str, sidebar_id: str, title: str, widget) -> None:
        """プラグインのサイドバーをドックとして載せる。"""
        window = self._window
        if window is None:
            return
        key = (plugin_id, sidebar_id)
        action_text = sidebar_title_stem(title) or str(title or "").strip() or sidebar_id
        existing = self._sidebars.get(key)
        if existing is not None:
            dock = existing["dock"]
            dock.setWindowTitle(title)
            existing["action"].setText(action_text)
            existing["title"] = title
            if dock.widget() is not widget:
                dock.setWidget(widget)
            return
        dock = QDockWidget(title, window)
        dock.setObjectName(self._sidebar_object_name(plugin_id, sidebar_id))
        dock.setWidget(widget)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetClosable
            | QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        window.addDockWidget(Qt.RightDockWidgetArea, dock)
        dock.hide()
        action = QAction(action_text, window)
        action.setCheckable(True)
        action.triggered.connect(lambda checked, target=dock: target.setVisible(bool(checked)))
        dock.visibilityChanged.connect(lambda visible, item=action: item.setChecked(bool(visible)))
        action_id = make_sidebar_action_id(plugin_id, sidebar_id)
        self._apply_sidebar_shortcut(action, action_id)
        menu = self._sidebar_menu() if self._sidebar_menu is not None else None
        if menu is not None:
            menu.addAction(action)
        self._sidebars[key] = {
            "dock": dock,
            "action": action,
            "title": title,
            "action_id": action_id,
        }

    def unmount_sidebar(self, plugin_id: str, sidebar_id: str) -> None:
        """載せたサイドバーを外す。"""
        record = self._sidebars.pop((plugin_id, sidebar_id), None)
        if record is None:
            return
        dock = record["dock"]
        action = record["action"]
        menu = self._sidebar_menu() if self._sidebar_menu is not None else None
        if menu is not None:
            menu.removeAction(action)
        window = self._window
        if window is not None:
            window.removeDockWidget(dock)
        dock.deleteLater()

    def toggle_sidebar(self, plugin_id: str, sidebar_id: str) -> bool:
        """サイドバーの表示を切り替える。開けたときは current_changed を出す。"""
        record = self._sidebars.get((plugin_id, sidebar_id))
        if record is None:
            return False
        dock = record["dock"]
        action = record["action"]
        visible = not dock.isVisible()
        dock.setVisible(visible)
        action.setChecked(visible)
        if visible:
            self.notify_current_changed()
        return True

    def readd_sidebar_actions(self) -> None:
        """メニュー再構築のあと、サイドバー用アクションを載せ直す。"""
        menu = self._sidebar_menu() if self._sidebar_menu is not None else None
        if menu is None:
            return
        for record in self._sidebars.values():
            action = record["action"]
            if action not in menu.actions():
                menu.addAction(action)
            action.setChecked(record["dock"].isVisible())
            action_id = record.get("action_id")
            if action_id:
                self._apply_sidebar_shortcut(action, action_id)

    def hide_visible_sidebars(self) -> None:
        """表示中のプラグインサイドバーを閉じる。"""
        for record in self._sidebars.values():
            dock = record["dock"]
            if dock.isVisible():
                dock.hide()
                record["action"].setChecked(False)

    def _manager_ref(self):
        """マネージャと host を一度だけ取る。"""
        if self._manager is None:
            self._manager = get_plugin_manager()
            self._host = self._manager.host
        return self._manager

    def _ensure_consent_cache(self) -> None:
        """同意の有無を一度だけ読む。"""
        if self._consent_known:
            return
        self._consented = plugin_consent_accepted()
        self._consent_known = True

    def _sidebar_object_name(self, plugin_id: str, sidebar_id: str) -> str:
        """ドック復元用の objectName。"""
        safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(sidebar_id or "main"))
        return f"plugin_sidebar_{hash_plugin_id(plugin_id)[:16]}_{safe_id}"

    def _apply_sidebar_shortcut(self, action: QAction, action_id: str) -> None:
        """サイドバー開閉に割り当てられたショートカットを付ける。"""
        host = self._host
        names = host.action_ids_for(action_id) if host is not None else None
        names = names or [action_id]
        for name in names:
            shortcut = self._first_shortcut(name) if self._first_shortcut is not None else None
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
                action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
                return
        action.setShortcut(QKeySequence())
