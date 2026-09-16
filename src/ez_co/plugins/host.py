"""プラグインからホストのダイアログ／アクションを呼ぶ口。

プラグインは ez_co を import せず、注入された入口を使う。
各プラグインには plugin_id 固定の ScopedPluginHost が渡る。
"""
from __future__ import annotations

import copy
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Optional

from ez_co.plugins.api import FileKind, FormatSpec, normalize_formats, parse_file_kind
from ez_co.plugins.manifest import parse_permissions
from ez_co.utils.language_manager import get_log_text, get_text

logger = logging.getLogger(__name__)

_APP_CONFIG_ALLOW = ("language", "viewer", "cache", "ui_font")
_CONFIG_TYPES = ("bool", "string", "int", "float", "color", "date", "datetime", "choice", "font")
_COLOR_FALLBACK = "#000000"


def make_plugin_action_id(plugin_id: str, action_id: str) -> str:
    return f"plugin:{plugin_id}:{action_id}"


def make_sidebar_action_id(plugin_id: str, sidebar_id: str) -> str:
    return f"plugin:{plugin_id}:sidebar:{sidebar_id}"


def normalize_action_aliases(aliases) -> tuple[str, ...]:
    if aliases is None:
        return ()
    if isinstance(aliases, str):
        aliases = (aliases,)
    seen = []
    for item in aliases:
        name = str(item or "").strip()
        if not name or name in seen:
            continue
        seen.append(name)
    return tuple(seen)


_SIDEBAR_TITLE_SUFFIXES = (
    "サイドバー表示/非表示",
    "サイドバーの開閉",
    "サイドバー",
    " show/hide sidebar",
    " sidebar",
)


def sidebar_title_stem(title: str) -> str:
    name = str(title or "").strip()
    lowered = name.casefold()
    for suffix in _SIDEBAR_TITLE_SUFFIXES:
        if lowered.endswith(suffix.casefold()):
            name = name[: len(name) - len(suffix)].strip()
            lowered = name.casefold()
    return name


def sidebar_toggle_label(title: str) -> str:
    stem = sidebar_title_stem(title) or str(title or "").strip() or "sidebar"
    return get_text("ui.plugin_sidebar_toggle", title=stem)


def normalize_local_action_id(action_id) -> str:
    name = str(action_id or "").strip()
    if not name or name == "sidebar" or ":" in name:
        return ""
    return name


@dataclass(frozen=True)
class PluginAction:
    plugin_id: str
    local_id: str
    public_id: str
    label: str
    callback: Callable
    kind: str = "custom"
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ConfigField:
    key: str
    value_type: str
    default: Any = None
    label: str = ""
    description: str = ""
    choices: tuple[tuple[str, str], ...] = ()


def normalize_config_type(value_type) -> str:
    name = str(value_type or "string").strip().lower()
    if name in ("bool", "boolean"):
        return "bool"
    if name in ("int", "integer"):
        return "int"
    if name in ("float", "double", "number"):
        return "float"
    if name in ("color", "colour"):
        return "color"
    if name == "date":
        return "date"
    if name in ("datetime", "timestamp"):
        return "datetime"
    if name in ("choice", "enum", "select"):
        return "choice"
    if name in ("font", "font_family"):
        return "font"
    return "string"


def normalize_config_choices(choices) -> tuple[tuple[str, str], ...]:
    if not choices:
        return ()
    rows = []
    seen = set()
    for item in choices:
        if isinstance(item, (list, tuple)) and item:
            value = str(item[0])
            label = str(item[1]) if len(item) > 1 else value
        else:
            value = str(item)
            label = value
        if value in seen:
            continue
        seen.add(value)
        rows.append((value, label))
    return tuple(rows)


def _parse_hex_color(value) -> str:
    text = str(value or "").strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) == 3 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return "#" + "".join(ch.lower() * 2 for ch in text)
    if len(text) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in text):
        return "#" + text.lower()
    return ""


def _unix_seconds(value) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, datetime):
        moment = value
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        return int(moment.timestamp())
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        pass
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        if "T" in text or " " in text:
            moment = datetime.fromisoformat(text.replace(" ", "T", 1))
        else:
            moment = datetime.fromisoformat(text)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        return int(moment.timestamp())
    except ValueError:
        return None


def _date_seconds(value) -> Optional[int]:
    parsed = _unix_seconds(value)
    if parsed is None:
        return None
    moment = datetime.fromtimestamp(parsed, tz=timezone.utc)
    midnight = datetime(moment.year, moment.month, moment.day, tzinfo=timezone.utc)
    return int(midnight.timestamp())


def coerce_config_value(value_type: str, value, default=None, choices=None):
    kind = normalize_config_type(value_type)
    options = normalize_config_choices(choices)
    if kind == "bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("true", "yes", "on", "1"):
                return True
            if lowered in ("false", "no", "off", "0"):
                return False
        return bool(default) if default is not None else False
    if kind == "int":
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(default)
            except (TypeError, ValueError):
                return 0
    if kind == "float":
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return float(default)
            except (TypeError, ValueError):
                return 0.0
    if kind == "color":
        return _parse_hex_color(value) or _parse_hex_color(default) or _COLOR_FALLBACK
    if kind == "date":
        parsed = _date_seconds(value)
        if parsed is not None:
            return parsed
        parsed = _date_seconds(default)
        return 0 if parsed is None else parsed
    if kind == "datetime":
        parsed = _unix_seconds(value)
        if parsed is not None:
            return parsed
        parsed = _unix_seconds(default)
        return 0 if parsed is None else parsed
    if kind == "choice" and options:
        text = "" if value is None else str(value)
        allowed = {item[0] for item in options}
        if text in allowed:
            return text
        fallback = "" if default is None else str(default)
        if fallback in allowed:
            return fallback
        return options[0][0]
    if kind == "font":
        if value is None:
            return "" if default is None else str(default)
        return str(value)
    if value is None:
        return "" if default is None else str(default)
    return str(value)


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
        self._reload_current = None
        self._get_app_config = None
        self._mount_sidebar = None
        self._unmount_sidebar = None
        self._toggle_sidebar = None
        self._sidebar_visible = None
        self._formats: dict[str, list[FormatSpec]] = {}
        self._sidebars: dict[tuple[str, str], SidebarRegistration] = {}
        self._actions: dict[str, PluginAction] = {}
        self._listeners: dict[str, list[tuple[str, Callable]]] = {}
        self._scoped: dict[str, "ScopedPluginHost"] = {}
        self._config_fields: dict[str, list[ConfigField]] = {}
        self._permissions: dict[str, MappingProxyType] = {}

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
        reload_current: Optional[Callable] = None,
        get_app_config: Optional[Callable] = None,
        mount_sidebar: Optional[Callable] = None,
        unmount_sidebar: Optional[Callable] = None,
        toggle_sidebar: Optional[Callable] = None,
        sidebar_visible: Optional[Callable] = None,
    ) -> None:
        self._parent = parent
        self._db = db_manager
        self._run_action = run_action
        self._get_current = get_current
        self._reload_current = reload_current
        self._get_app_config = get_app_config
        self._mount_sidebar = mount_sidebar
        self._unmount_sidebar = unmount_sidebar
        self._toggle_sidebar = toggle_sidebar
        self._sidebar_visible = sidebar_visible
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

    def report_error(self, where, exc, plugin_id: Optional[str] = None) -> None:
        from ez_co.utils.error_logger import report_error
        report_error(where, exc, plugin_id=plugin_id)

    def set_manifest_permissions(self, plugin_id: str, permissions) -> None:
        """本体のロード経路だけが呼ぶ。プラグイン API には出さない。"""
        key = str(plugin_id or "")
        if not key:
            return
        if isinstance(permissions, dict):
            raw = permissions
        elif permissions is None:
            raw = {}
        else:
            try:
                raw = dict(permissions)
            except (TypeError, ValueError):
                raw = {}
        self._permissions[key] = parse_permissions(raw)

    def has_manifest_permission(self, plugin_id: str, name: str) -> bool:
        granted = self._permissions.get(str(plugin_id))
        if not granted:
            return False
        return bool(granted.get(str(name or "")))

    def _delivers_current_changed(self, plugin_id: str) -> bool:
        if not self.sidebars_for(plugin_id):
            return True
        if self.has_manifest_permission(plugin_id, "inactive_callback"):
            return True
        checker = self._sidebar_visible
        if checker is None:
            return False
        try:
            return bool(checker(plugin_id))
        except Exception:
            return False

    def emit(self, event: str, payload=None, plugin_id: Optional[str] = None) -> None:
        name = str(event or "").strip()
        if not name:
            return
        target = str(plugin_id) if plugin_id else None
        gate_inactive = name == "current_changed"
        for owner, callback in list(self._listeners.get(name, [])):
            if target is not None and owner != target:
                continue
            if gate_inactive and not self._delivers_current_changed(owner):
                continue
            try:
                callback(payload)
            except TypeError:
                try:
                    callback()
                except Exception as exc:
                    self.report_error(name, exc, plugin_id=owner)
            except Exception as exc:
                self.report_error(name, exc, plugin_id=owner)

    def configs_for(self, plugin_id: str) -> list[ConfigField]:
        return list(self._config_fields.get(plugin_id, []))

    def list_actions(self) -> list[PluginAction]:
        return list(self._actions.values())

    def resolve_action(self, action_id: str) -> Optional[PluginAction]:
        key = str(action_id or "")
        if not key:
            return None
        record = self._actions.get(key)
        if record is not None:
            return record
        for item in self._actions.values():
            if key in item.aliases:
                return item
        return None

    def action_label(self, action_id: str) -> Optional[str]:
        record = self.resolve_action(action_id)
        if record is None:
            return None
        if record.kind == "sidebar":
            return sidebar_toggle_label(record.label)
        return record.label

    def action_ids_for(self, public_id: str) -> list[str]:
        record = self.resolve_action(public_id)
        if record is None:
            return [public_id] if public_id else []
        return [record.public_id, *record.aliases]

    def invoke_registered(self, action_id: str) -> bool:
        record = self.resolve_action(action_id)
        if record is None:
            return False
        try:
            result = record.callback()
        except TypeError:
            try:
                record.callback()
                return True
            except Exception as exc:
                self.report_error(action_id, exc, plugin_id=record.plugin_id)
                return False
        except Exception as exc:
            self.report_error(action_id, exc, plugin_id=record.plugin_id)
            return False
        return True if result is None else bool(result)

    def clear_plugin(self, plugin_id: str) -> None:
        for key in [item for item in self._sidebars if item[0] == plugin_id]:
            self._unmount_sidebar_record(key)
        for public_id in [item for item, record in self._actions.items() if record.plugin_id == plugin_id]:
            self._actions.pop(public_id, None)
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

    def _register_sidebar(self, plugin_id: str, sidebar_id: str, title: str, widget_or_layout, aliases=None) -> None:
        sidebar_id = str(sidebar_id or "").strip() or "main"
        widget = self._as_widget(widget_or_layout)
        record = SidebarRegistration(plugin_id, sidebar_id, str(title or sidebar_id), widget)
        self._sidebars[(plugin_id, sidebar_id)] = record
        self._register_sidebar_action(plugin_id, sidebar_id, record.title, aliases)
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
        self._actions.pop(make_sidebar_action_id(record.plugin_id, record.sidebar_id), None)
        if self._unmount_sidebar is not None:
            try:
                self._unmount_sidebar(record.plugin_id, record.sidebar_id)
            except Exception as exc:
                logger.debug(get_log_text("plugin_sidebar_unmount_failed", error=exc))

    def _register_sidebar_action(self, plugin_id: str, sidebar_id: str, title: str, aliases=None) -> None:
        public_id = make_sidebar_action_id(plugin_id, sidebar_id)
        self._actions[public_id] = PluginAction(
            plugin_id=plugin_id,
            local_id=f"sidebar:{sidebar_id}",
            public_id=public_id,
            label=str(title or sidebar_id),
            callback=lambda pid=plugin_id, sid=sidebar_id: self._toggle_sidebar_ui(pid, sid),
            kind="sidebar",
            aliases=normalize_action_aliases(aliases),
        )

    def _toggle_sidebar_ui(self, plugin_id: str, sidebar_id: str) -> bool:
        if self._toggle_sidebar is None:
            return False
        try:
            return bool(self._toggle_sidebar(plugin_id, sidebar_id))
        except Exception as exc:
            logger.debug(get_log_text("plugin_event_failed", event=f"toggle_sidebar:{sidebar_id}", error=exc))
            return False

    def _register_action(self, plugin_id: str, action_id, label, callback, aliases=None) -> None:
        local_id = normalize_local_action_id(action_id)
        if not local_id or callback is None:
            return
        public_id = make_plugin_action_id(plugin_id, local_id)
        self._actions[public_id] = PluginAction(
            plugin_id=plugin_id,
            local_id=local_id,
            public_id=public_id,
            label=str(label or local_id),
            callback=callback,
            kind="custom",
            aliases=normalize_action_aliases(aliases),
        )

    def _unregister_action(self, plugin_id: str, action_id) -> None:
        local_id = normalize_local_action_id(action_id)
        if not local_id:
            return
        self._actions.pop(make_plugin_action_id(plugin_id, local_id), None)

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

    def _register_config(
        self,
        plugin_id: str,
        key: str,
        value_type,
        default=None,
        label=None,
        description=None,
        choices=None,
    ) -> None:
        field_key = str(key or "").strip()
        if not field_key:
            return
        field = ConfigField(
            key=field_key,
            value_type=normalize_config_type(value_type),
            default=default,
            label=str(label or ""),
            description=str(description or ""),
            choices=normalize_config_choices(choices),
        )
        rows = [item for item in self._config_fields.get(plugin_id, []) if item.key != field_key]
        rows.append(field)
        self._config_fields[plugin_id] = rows

    def _field_for(self, plugin_id: str, key: str) -> Optional[ConfigField]:
        for field in self._config_fields.get(plugin_id, []):
            if field.key == key:
                return field
        return None

    def _get_plugin_config(self, plugin_id: str, key: str, default=None):
        field = self._field_for(plugin_id, key)
        if default is None and field is not None:
            default = field.default
        if self._db is None:
            value = default
        else:
            value = self._db.get_plugin_setting(plugin_id, key, default)
        if field is not None:
            return coerce_config_value(field.value_type, value, field.default, field.choices)
        return value

    def _set_plugin_config(self, plugin_id: str, key: str, value, notify: bool = True) -> bool:
        field = self._field_for(plugin_id, key)
        stored = (
            coerce_config_value(field.value_type, value, field.default, field.choices)
            if field is not None
            else value
        )
        if self._db is None:
            ok = False
        else:
            ok = bool(self._db.set_plugin_setting(plugin_id, key, stored))
        if notify:
            self.emit("config_changed", {"key": str(key or ""), "value": stored}, plugin_id=plugin_id)
        return ok

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

    def reload_current(self, page=None) -> bool:
        target = None
        if page is not None:
            try:
                target = int(page)
            except (TypeError, ValueError):
                target = None
        return bool(self._call_on_ui(lambda: self._reload_current_ui(target)))

    def _reload_current_ui(self, page) -> bool:
        if self._reload_current is None:
            return False
        try:
            return bool(self._reload_current(page))
        except Exception as exc:
            logger.debug(get_log_text("plugin_event_failed", event="reload_current", error=exc))
            return False

    def _run_action_ui(self, action_id: str, kwargs: dict) -> bool:
        if self.invoke_registered(action_id):
            return True
        if self._run_action is None:
            logger.info(get_log_text("plugin_action_not_bound", action_id=action_id))
            return False
        return bool(self._run_action(action_id, kwargs))

    def _ask_password_ui(self, file_path: str, mismatch: bool, verify) -> Optional[str]:
        from PySide6.QtWidgets import QApplication, QDialog
        from ez_co.handlers.archive_password import get_session_password, set_session_password
        from ez_co.ui.dialogs.pdf_password_dialog import CLOSE_APP_RESULT, ArchivePasswordDialog

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

    def register_sidebar(self, sidebar_id: str, title: str, widget_or_layout, aliases=None) -> None:
        self._host._register_sidebar(self._plugin_id, sidebar_id, title, widget_or_layout, aliases)

    def unregister_sidebar(self, sidebar_id: str) -> None:
        self._host._unregister_sidebar(self._plugin_id, sidebar_id)

    def register_action(self, action_id, label, callback, aliases=None) -> None:
        self._host._register_action(self._plugin_id, action_id, label, callback, aliases)

    def unregister_action(self, action_id) -> None:
        self._host._unregister_action(self._plugin_id, action_id)

    def load_ui(self, data_or_path):
        return self._host.load_ui(data_or_path)

    def register_config(
        self,
        key: str,
        value_type,
        default=None,
        label=None,
        description=None,
        choices=None,
    ) -> None:
        self._host._register_config(
            self._plugin_id,
            key,
            value_type,
            default,
            label,
            description,
            choices,
        )

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

    def reload_current(self, page=None) -> bool:
        return bool(self._host.reload_current(page))

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

    def report_error(self, where, exc) -> None:
        self._host.report_error(where, exc, plugin_id=self._plugin_id)

    def registered_formats(self) -> list[FormatSpec]:
        return self._host.formats_for(self._plugin_id)

    def has_pending_sidebars(self) -> bool:
        return bool(self._host.sidebars_for(self._plugin_id))
