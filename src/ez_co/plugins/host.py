"""プラグインからホストのダイアログ／アクションを呼ぶ口。

プラグインは ez_co を import せず、注入された入口を使う。
各プラグインには plugin_id 固定の ScopedPluginHost が渡る。
"""
from __future__ import annotations

import copy
import logging
import threading
from types import MappingProxyType
from typing import Any, Callable, Optional

from ez_co.plugins.api import FileKind, FormatSpec, normalize_formats, parse_file_kind
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)

_APP_CONFIG_ALLOW = ("language", "viewer", "cache", "ui_font")


class _UiBridge:
    """ワーカーから UI スレッドへ処理を渡す。"""

    def __init__(self):
        from PySide6.QtCore import QObject, Qt, Signal

        class _Emitter(QObject):
            requested = Signal(object)

            def __init__(self):
                super().__init__()
                self.requested.connect(self._dispatch, Qt.QueuedConnection)

            def _dispatch(self, payload):
                func, box, done = payload
                try:
                    box.append(func())
                except Exception as exc:
                    box.append(exc)
                finally:
                    done.set()

        self._emitter = _Emitter()

    def invoke(self, func):
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or QThread.currentThread() == app.thread():
            return func()
        box = []
        done = threading.Event()
        self._emitter.requested.emit((func, box, done))
        done.wait()
        if box and isinstance(box[0], Exception):
            raise box[0]
        return box[0] if box else None


class SidebarRegistration:
    def __init__(self, plugin_id: str, sidebar_id: str, title: str, widget):
        self.plugin_id = plugin_id
        self.sidebar_id = sidebar_id
        self.title = title
        self.widget = widget


class PluginHost:
    def __init__(self):
        self._parent = None
        self._db = None
        self._run_action = None
        self._bridge = None
        self._get_current = None
        self._get_app_config = None
        self._mount_sidebar = None
        self._unmount_sidebar = None
        self._formats: dict[str, list[FormatSpec]] = {}
        self._sidebars: dict[tuple[str, str], SidebarRegistration] = {}
        self._listeners: dict[str, list[tuple[str, Callable]]] = {}
        self._scoped: dict[str, "ScopedPluginHost"] = {}

    def scoped(self, plugin_id: str) -> "ScopedPluginHost":
        key = str(plugin_id or "")
        existing = self._scoped.get(key)
        if existing is None:
            existing = ScopedPluginHost(self, key)
            self._scoped[key] = existing
        return existing

    def bind(
        self,
        parent,
        db_manager=None,
        run_action: Optional[Callable] = None,
        get_current: Optional[Callable] = None,
        get_app_config: Optional[Callable] = None,
        mount_sidebar: Optional[Callable] = None,
        unmount_sidebar: Optional[Callable] = None,
    ) -> None:
        self._parent = parent
        self._db = db_manager
        self._run_action = run_action
        self._get_current = get_current
        self._get_app_config = get_app_config
        self._mount_sidebar = mount_sidebar
        self._unmount_sidebar = unmount_sidebar
        self._ensure_bridge()
        if mount_sidebar:
            for record in list(self._sidebars.values()):
                try:
                    mount_sidebar(record.plugin_id, record.sidebar_id, record.title, record.widget)
                except Exception as exc:
                    logger.warning(get_log_text("plugin_sidebar_mount_failed", error=exc))

    def formats_for(self, plugin_id: str) -> list[FormatSpec]:
        return list(self._formats.get(plugin_id, []))

    def sidebars_for(self, plugin_id: str) -> list[SidebarRegistration]:
        return [item for key, item in self._sidebars.items() if key[0] == plugin_id]

    def ask_password(self, file_path: str, mismatch: bool = False, verify=None) -> Optional[str]:
        return self._call_on_ui(lambda: self._ask_password_ui(file_path, mismatch, verify))

    def show_dialog(self, name: str, **kwargs):
        key = str(name or "").strip().lower()
        if key in ("password", "archive_password", "ask_password"):
            return self.ask_password(
                kwargs.get("file_path") or kwargs.get("path") or "",
                mismatch=bool(kwargs.get("mismatch", False)),
                verify=kwargs.get("verify"),
            )
        logger.warning(get_log_text("plugin_dialog_unsupported", name=name))
        return None

    def run_action(self, action_id: str, **kwargs) -> bool:
        return bool(self._call_on_ui(lambda: self._run_action_ui(action_id, kwargs)))

    def load_ui(self, data_or_path):
        return self._call_on_ui(lambda: self._load_ui(data_or_path))

    def emit(self, event: str, payload=None) -> None:
        name = str(event or "").strip()
        if not name:
            return
        for _plugin_id, callback in list(self._listeners.get(name, [])):
            try:
                callback(payload)
            except TypeError:
                try:
                    callback()
                except Exception as exc:
                    logger.debug(get_log_text("plugin_event_failed", event=name, error=exc))
            except Exception as exc:
                logger.debug(get_log_text("plugin_event_failed", event=name, error=exc))

    def clear_plugin(self, plugin_id: str) -> None:
        for key in [item for item in self._sidebars if item[0] == plugin_id]:
            self._unmount_sidebar_record(key)
        for event, rows in list(self._listeners.items()):
            self._listeners[event] = [item for item in rows if item[0] != plugin_id]

    def _register_format(self, plugin_id: str, extension, kind) -> None:
        specs = normalize_formats([(extension, kind if not isinstance(kind, str) else parse_file_kind(kind) or kind)])
        if not specs and isinstance(kind, FileKind):
            specs = normalize_formats([(extension, kind)])
        bucket = self._formats.setdefault(plugin_id, [])
        for spec in specs:
            if not any(item.extension == spec.extension and item.kind == spec.kind for item in bucket):
                bucket.append(spec)

    def _register_sidebar(self, plugin_id: str, sidebar_id: str, title: str, widget_or_layout) -> None:
        sidebar_id = str(sidebar_id or "").strip() or "main"
        widget = self._as_widget(widget_or_layout)
        record = SidebarRegistration(plugin_id, sidebar_id, str(title or sidebar_id), widget)
        self._sidebars[(plugin_id, sidebar_id)] = record
        if self._mount_sidebar is not None:
            try:
                self._mount_sidebar(plugin_id, sidebar_id, record.title, widget)
            except Exception as exc:
                logger.warning(get_log_text("plugin_sidebar_mount_failed", error=exc))

    def _unregister_sidebar(self, plugin_id: str, sidebar_id: str) -> None:
        self._unmount_sidebar_record((plugin_id, str(sidebar_id or "").strip() or "main"))

    def _unmount_sidebar_record(self, key: tuple[str, str]) -> None:
        record = self._sidebars.pop(key, None)
        if record is None:
            return
        if self._unmount_sidebar is not None:
            try:
                self._unmount_sidebar(record.plugin_id, record.sidebar_id)
            except Exception as exc:
                logger.debug(get_log_text("plugin_sidebar_unmount_failed", error=exc))

    def _as_widget(self, widget_or_layout):
        from PySide6.QtWidgets import QLayout, QWidget

        if isinstance(widget_or_layout, QLayout):
            widget = QWidget()
            widget.setLayout(widget_or_layout)
            return widget
        return widget_or_layout

    def _on(self, plugin_id: str, event: str, callback: Callable) -> None:
        name = str(event or "").strip()
        if not name or callback is None:
            return
        self._listeners.setdefault(name, []).append((plugin_id, callback))

    def _off(self, plugin_id: str, event: str, callback: Optional[Callable] = None) -> None:
        name = str(event or "").strip()
        rows = self._listeners.get(name) or []
        if callback is None:
            self._listeners[name] = [item for item in rows if item[0] != plugin_id]
            return
        self._listeners[name] = [item for item in rows if item != (plugin_id, callback)]

    def _load_ui(self, data_or_path):
        from PySide6.QtCore import QBuffer, QByteArray, QFile, QIODevice
        from PySide6.QtUiTools import QUiLoader

        loader = QUiLoader()
        if isinstance(data_or_path, (bytes, bytearray)):
            buffer = QBuffer()
            buffer.setData(QByteArray(bytes(data_or_path)))
            buffer.open(QIODevice.OpenModeFlag.ReadOnly)
            widget = loader.load(buffer)
            buffer.close()
            return widget
        path = str(data_or_path or "")
        handle = QFile(path)
        if not handle.open(QFile.OpenModeFlag.ReadOnly):
            raise FileNotFoundError(path)
        widget = loader.load(handle)
        handle.close()
        return widget

    def _get_plugin_config(self, plugin_id: str, key: str, default=None):
        if self._db is None:
            return default
        return self._db.get_plugin_setting(plugin_id, key, default)

    def _set_plugin_config(self, plugin_id: str, key: str, value) -> bool:
        if self._db is None:
            return False
        return bool(self._db.set_plugin_setting(plugin_id, key, value))

    def _delete_plugin_config(self, plugin_id: str, key: str) -> bool:
        if self._db is None:
            return False
        return bool(self._db.delete_plugin_setting(plugin_id, key))

    def _app_config_snapshot(self):
        raw = {}
        if self._get_app_config is not None:
            try:
                raw = self._get_app_config() or {}
            except Exception as exc:
                logger.debug(get_log_text("plugin_app_config_failed", error=exc))
                raw = {}
        allowed = {}
        for section in _APP_CONFIG_ALLOW:
            value = raw.get(section)
            if isinstance(value, dict):
                allowed[section] = copy.deepcopy(dict(value))
        return MappingProxyType({key: MappingProxyType(val) for key, val in allowed.items()})

    def _current_value(self, key: str):
        if self._get_current is None:
            return None
        try:
            return self._get_current(str(key or ""))
        except Exception as exc:
            logger.debug(get_log_text("plugin_current_failed", key=key, error=exc))
            return None

    def _run_action_ui(self, action_id: str, kwargs: dict) -> bool:
        if self._run_action is None:
            logger.info(get_log_text("plugin_action_not_bound", action_id=action_id))
            return False
        return bool(self._run_action(action_id, kwargs))

    def _ask_password_ui(self, file_path: str, mismatch: bool, verify) -> Optional[str]:
        from PySide6.QtWidgets import QApplication, QDialog
        from ez_co.handlers.archive_password import get_session_password, set_session_password
        from ez_co.ui.pdf_password_dialog import CLOSE_APP_RESULT, ArchivePasswordDialog

        cached = get_session_password(file_path)
        if cached is not None:
            if self._verify_password(cached, verify):
                return cached

        stored = None
        if self._db is not None:
            try:
                stored = self._db.get_stored_archive_password(file_path)
            except Exception as exc:
                logger.debug(get_log_text("plugin_stored_password_failed", error=exc))
        if stored is not None:
            if self._verify_password(stored, verify):
                set_session_password(file_path, stored)
                return stored
            mismatch = True

        while True:
            dialog = ArchivePasswordDialog(self._parent, mismatch=mismatch)
            result = dialog.exec()
            if result == CLOSE_APP_RESULT:
                app = QApplication.instance()
                if app is not None:
                    app.quit()
                return None
            if result != QDialog.DialogCode.Accepted:
                return None
            password = dialog.password()
            if self._verify_password(password, verify):
                set_session_password(file_path, password)
                return password
            mismatch = True

    def _verify_password(self, password: str, verify) -> bool:
        if verify is None:
            return True
        try:
            return bool(verify(password))
        except Exception:
            return False

    def _ensure_bridge(self) -> None:
        from PySide6.QtWidgets import QApplication

        if self._bridge is not None:
            return
        app = QApplication.instance()
        if app is None:
            return
        self._bridge = _UiBridge()
        self._bridge._emitter.moveToThread(app.thread())

    def _call_on_ui(self, func):
        from PySide6.QtCore import QThread
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None or QThread.currentThread() == app.thread():
            return func()
        self._ensure_bridge()
        if self._bridge is None:
            return func()
        return self._bridge.invoke(func)


class ScopedPluginHost:
    """呼び出し元 plugin_id に閉じたホスト。他プラグインの設定は触れない。"""

    def __init__(self, host: PluginHost, plugin_id: str):
        self._host = host
        self._plugin_id = plugin_id

    def register_format(self, extension, kind) -> None:
        self._host._register_format(self._plugin_id, extension, kind)

    def register_sidebar(self, sidebar_id: str, title: str, widget_or_layout) -> None:
        self._host._register_sidebar(self._plugin_id, sidebar_id, title, widget_or_layout)

    def unregister_sidebar(self, sidebar_id: str) -> None:
        self._host._unregister_sidebar(self._plugin_id, sidebar_id)

    def load_ui(self, data_or_path):
        return self._host.load_ui(data_or_path)

    def get_config(self, key: str, default: Any = None):
        return self._host._get_plugin_config(self._plugin_id, key, default)

    def set_config(self, key: str, value) -> bool:
        return self._host._set_plugin_config(self._plugin_id, key, value)

    def delete_config(self, key: str) -> bool:
        return self._host._delete_plugin_config(self._plugin_id, key)

    def get_app_config(self):
        return self._host._app_config_snapshot()

    def get_current(self, key: str):
        return self._host._current_value(key)

    def on(self, event: str, callback: Callable) -> None:
        self._host._on(self._plugin_id, event, callback)

    def off(self, event: str, callback: Optional[Callable] = None) -> None:
        self._host._off(self._plugin_id, event, callback)

    def ask_password(self, file_path: str, mismatch: bool = False, verify=None):
        return self._host.ask_password(file_path, mismatch=mismatch, verify=verify)

    def show_dialog(self, name: str, **kwargs):
        return self._host.show_dialog(name, **kwargs)

    def run_action(self, action_id: str, **kwargs) -> bool:
        return self._host.run_action(action_id, **kwargs)

    def registered_formats(self) -> list[FormatSpec]:
        return self._host.formats_for(self._plugin_id)

    def has_pending_sidebars(self) -> bool:
        return bool(self._host.sidebars_for(self._plugin_id))
