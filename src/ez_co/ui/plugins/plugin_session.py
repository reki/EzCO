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
        """同意、ホスト、サイドバーの入れ物を空で用意する。"""
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
        self._refresh_display = None

    def consent_accepted(self) -> bool:
        """導入同意済みか。起動時に一度だけ user.json を見る。

        Returns:
            同意済みのとき True。
        """
        self._ensure_consent_cache()
        return self._consented

    def bootstrap(self, parent, config, rebuild_menu=None, save_profile=None) -> None:
        """同意と重複選択のあと、選ばれたプラグインをロードする。

        Args:
            parent: 同意と重複ダイアログの親。
            config: 選択の記録に使う設定。
            rebuild_menu: 同意した直後にメニューを組み直す処理。
            save_profile: 重複の選択を保存する処理。
        """
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
        open_tabs=None,
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
        refresh_display=None,
        after_plugin_config=None,
    ) -> None:
        """ホストをこのウィンドウに結び、UI を有効化する。ロードはしない。

        Args:
            window: 結び付けるウィンドウ。
            config: 有効化に使う設定。
            db_manager: ホストへ渡すデータベース。
            current: path、folder、page を取る処理。
            open_tabs: 開いているタブの一覧を返す処理。
            reload_current: 現在の表示を読み直す処理。
            run_action: アクションを実行する処理。
            app_config: アプリ設定を読む処理。
            restore_docks: ドック配置を戻す処理。
            first_shortcut: アクション名から最初のショートカットを取る処理。
            sidebar_menu: サイドバー用メニューを返す処理。
            setup_shortcuts: ショートカットを組み直す処理。
            reload_open_files: 開いているファイルを載せ替える処理。
            rebuild_menu: メニューを組み直す処理。
            save_profile: プロファイルを保存する処理。
            refresh_display: 表示を更新する処理。
            after_plugin_config: プラグイン設定のあとに呼ぶ処理。
        """
        self._window = window
        self._config = config
        self._current = current
        self._open_tabs = open_tabs
        self._reload_current = reload_current
        self._run_action = run_action
        self._app_config = app_config
        self._restore_docks = restore_docks
        self._first_shortcut = first_shortcut
        self._sidebar_menu = sidebar_menu
        self._setup_shortcuts = setup_shortcuts
        self._reload_open_files = reload_open_files
        self._refresh_display = refresh_display
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
            open_tabs=open_tabs,
            reload_current=reload_current,
            get_app_config=app_config,
            mount_sidebar=self.mount_sidebar,
            unmount_sidebar=self.unmount_sidebar,
            toggle_sidebar=self.toggle_sidebar,
            sidebar_visible=self.sidebar_visible,
            after_plugin_config=after_plugin_config,
        )
        manager.activate_ui(config)
        if self._rebuild_menu is not None:
            self._rebuild_menu()
        if restore_docks is not None:
            restore_docks()
        else:
            self.notify_current_changed()

    def notify_current_changed(self, plugin_id: str | None = None) -> None:
        """開いている path / folder / page をプラグインへ知らせる。

        Args:
            plugin_id: 知らせるプラグイン。無ければホストの購読範囲。
        """
        host = self._host
        if host is None:
            return
        current = self._current
        payload = {
            "path": current("path") if current is not None else None,
            "folder": current("folder") if current is not None else None,
            "page": current("page") if current is not None else None,
        }
        host.emit("current_changed", payload, plugin_id=plugin_id)

    def sidebar_visible(self, plugin_id: str) -> bool:
        """そのプラグインのドックが1つでも表示中なら True。

        Args:
            plugin_id: 調べるプラグイン。

        Returns:
            表示中のドックがあるとき True。
        """
        return any(
            record["dock"].isVisible()
            for key, record in self._sidebars.items()
            if key[0] == plugin_id
        )

    def invoke_registered(self, action_id: str) -> bool:
        """プラグイン登録アクションを実行する。未結線なら False。

        Args:
            action_id: 実行するアクション。

        Returns:
            実行できたとき True。未結線なら False。
        """
        host = self._host
        if host is None:
            return False
        return host.invoke_registered(action_id)

    def after_config_change(self, reload_sources=False) -> None:
        """プラグイン設定の適用後に UI と開いているファイルを載せ替える。

        Args:
            reload_sources: 選ばれたプラグインを読み直すとき True。
        """
        manager = self._manager_ref()
        config = self._config
        if reload_sources:
            manager.reload_selected(config)
            if self._rebuild_menu is not None:
                self._rebuild_menu()
            if self._setup_shortcuts is not None:
                self._setup_shortcuts()
        manager.activate_ui(config)
        if self._rebuild_menu is not None:
            self._rebuild_menu()
        if self._reload_open_files is not None:
            self._reload_open_files()
        elif self._refresh_display is not None:
            self._refresh_display()
        self.notify_current_changed()

    def mount_sidebar(self, plugin_id: str, sidebar_id: str, title: str, widget) -> None:
        """プラグインのサイドバーをドックとして載せる。

        Args:
            plugin_id: プラグイン。
            sidebar_id: サイドバー。
            title: ドックのタイトル。
            widget: ドックに載せるウィジェット。
        """
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
        dock.visibilityChanged.connect(
            lambda visible, pid=plugin_id, item=action: self._on_sidebar_visibility(pid, item, visible)
        )
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
        """載せたサイドバーを外す。

        Args:
            plugin_id: プラグイン。
            sidebar_id: 外すサイドバー。
        """
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
        """サイドバーの表示を切り替える。開けたときの current_changed は visibilityChanged。

        Args:
            plugin_id: プラグイン。
            sidebar_id: 切り替えるサイドバー。

        Returns:
            ドックが無いとき False。切り替えたとき True。
        """
        record = self._sidebars.get((plugin_id, sidebar_id))
        if record is None:
            return False
        dock = record["dock"]
        action = record["action"]
        visible = not dock.isVisible()
        dock.setVisible(visible)
        action.setChecked(visible)
        return True

    def _on_sidebar_visibility(self, plugin_id: str, action, visible) -> None:
        """表示になったプラグインへだけ current_changed を出す。

        Args:
            plugin_id: 表示が変わったプラグイン。
            action: チェックを合わせるメニュー項目。
            visible: 表示中のとき True。
        """
        action.setChecked(bool(visible))
        if visible:
            self.notify_current_changed(plugin_id=plugin_id)

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

    def hide_visible_sidebars(self) -> list:
        """表示中のプラグインサイドバーを閉じ、隠したレコードを返す。

        Returns:
            隠したサイドバーのレコード。
        """
        hidden = []
        for record in self._sidebars.values():
            dock = record["dock"]
            if dock.isVisible():
                dock.hide()
                record["action"].setChecked(False)
                hidden.append(record)
        return hidden

    def restore_sidebars(self, records) -> None:
        """hide_visible_sidebars が返したサイドバーを戻す。

        Args:
            records: 戻すレコード。無ければ何もしない。
        """
        for record in records or []:
            record["dock"].show()
            record["action"].setChecked(True)

    def _manager_ref(self):
        """マネージャと host を一度だけ取る。

        Returns:
            プラグインマネージャ。
        """
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
        """ドック復元用の objectName。

        Args:
            plugin_id: プラグイン。
            sidebar_id: サイドバー。空なら main。

        Returns:
            ドックの objectName。
        """
        safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in str(sidebar_id or "main"))
        return f"plugin_sidebar_{hash_plugin_id(plugin_id)[:16]}_{safe_id}"

    def _apply_sidebar_shortcut(self, action: QAction, action_id: str) -> None:
        """サイドバー開閉に割り当てられたショートカットを付ける。

        Args:
            action: ショートカットを付ける項目。
            action_id: ショートカットを探すアクション ID。
        """
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
