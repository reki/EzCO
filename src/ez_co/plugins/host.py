"""プラグインからホストのダイアログ／アクションを呼ぶ口。

プラグインは ez_co を import せず、注入された次の入口を使う。

- ask_password(file_path, mismatch=False, verify=None) -> str | None
- show_dialog(\"password\", file_path=..., verify=...)
- run_action(action_id, **kwargs) -> bool  # 将来用。今は未配線

ホストは FileLoader(root, get_text, host) を渡す。
ダイアログとアクションは host から呼ぶ。
"""
from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)


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


class PluginHost:
    def __init__(self):
        self._parent = None
        self._db = None
        self._run_action = None
        self._bridge = None

    def bind(self, parent, db_manager=None, run_action: Optional[Callable] = None) -> None:
        self._parent = parent
        self._db = db_manager
        self._run_action = run_action
        self._ensure_bridge()

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
