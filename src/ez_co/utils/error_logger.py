"""エラーをファイルへ残し、有効なときはダイアログを出す。"""

import sys
import threading
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable
class ErrorLogger:
    """エラーログを管理するクラス"""
    def __init__(self, log_dir: Optional[Path] = None):
        """
        エラーロガーを初期化

        Args:
            log_dir: ログファイルの保存ディレクトリ（Noneの場合は実行ファイルと同じディレクトリ）
        """
        if log_dir is None:
            from ez_co.utils.data_location import get_data_root
            log_dir = get_data_root()
        self.log_dir = Path(log_dir) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        # ログファイル名を設定（日付付き）
        self.log_file = self.log_dir / f"error_log_{datetime.now().strftime('%Y%m%d')}.txt"
        # ログフォーマッターを設定
        self.formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # ファイルハンドラーを設定
        self.file_handler = logging.FileHandler(
            self.log_file,
            encoding='utf-8',
            mode='a'  # 追記モード
        )
        self.file_handler.setFormatter(self.formatter)
        # ロガーを設定
        self.logger = logging.getLogger('EzCo_Error')
        self.logger.setLevel(logging.ERROR)
        self.logger.addHandler(self.file_handler)
        # 既存のハンドラーをクリア（重複を避けるため）
        self.logger.propagate = False

    def log_error(self, message: str, exc_info: Optional[Exception] = None):
        """
        エラーメッセージをログに記録

        Args:
            message: エラーメッセージ
            exc_info: 例外情報（オプション）
        """
        try:
            if exc_info:
                self.logger.error(f"{message}", exc_info=True)
            else:
                self.logger.error(message)
        except Exception as e:
            # ログ記録中にエラーが発生した場合のフォールバック
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ERROR - "
                           f"Failed to log error: {e}\n")
            except:
                # ファイルへも書けなければ捨てる
                pass
# グローバルなエラーロガーインスタンス
error_logger = None
_error_log_enabled: Optional[Callable[[], bool]] = None
_error_dialog_queue = None
_dialog_open = False


def set_error_log_enabled(getter: Optional[Callable[[], bool]]) -> None:
    """エラーダイアログを出すかどうかの判定を登録する。

    Args:
        getter: 有効なら True を返す関数。None なら出さない
    """
    global _error_log_enabled
    _error_log_enabled = getter


def _is_error_log_enabled() -> bool:
    """登録された判定でダイアログを出すかを返す。

    Returns:
        判定が True のときだけ True
    """
    if _error_log_enabled is None:
        return False
    try:
        return bool(_error_log_enabled())
    except Exception:
        # 判定に失敗したらダイアログは出さない
        return False


def _should_ignore(exc_type) -> bool:
    """記録しない例外かを返す。

    Args:
        exc_type: 例外の型

    Returns:
        割り込み、システム終了、ジェネレータ終了なら True
    """
    return exc_type is not None and issubclass(exc_type, (KeyboardInterrupt, SystemExit, GeneratorExit))


def _format_error_text(exc=None, exc_info=None) -> str:
    """例外をトレースバックの文字列にする。

    Args:
        exc: 例外インスタンス
        exc_info: 型、値、トレースバックの組

    Returns:
        整形した文字列。材料が無ければ空
    """
    if exc_info is not None:
        return "".join(traceback.format_exception(*exc_info))
    if exc is not None:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    return ""


def _ensure_dialog_queue():
    """ダイアログ表示を GUI スレッドへ渡す発信器を用意する。

    Returns:
        発信器。Qt が無い、またはアプリケーションが無ければ None
    """
    global _error_dialog_queue
    if _error_dialog_queue is not None:
        return _error_dialog_queue
    try:
        from PySide6.QtCore import QObject, Qt, Signal
        from PySide6.QtWidgets import QApplication
    except ImportError:
        # Qt を読み込めなければダイアログは出さない
        return None
    app = QApplication.instance()
    if app is None:
        return None

    class _Emitter(QObject):
        """エラーダイアログの表示をキューする。"""
        requested = Signal(str, str)

        def __init__(self):
            """シグナルをキュー接続で自分の表示へつなぐ。"""
            super().__init__()
            self.requested.connect(self._show, Qt.QueuedConnection)

        def _show(self, where, text):
            """キューからエラーダイアログを開く。

            Args:
                where: 発生箇所
                text: 表示する本文
            """
            _open_error_dialog(where, text)

    emitter = _Emitter()
    emitter.moveToThread(app.thread())
    _error_dialog_queue = emitter
    return _error_dialog_queue


def _open_error_dialog(where: str, text: str) -> None:
    """エラーダイアログを一つだけ開く。

    Args:
        where: 発生箇所
        text: 表示する本文
    """
    global _dialog_open
    if _dialog_open:
        return
    _dialog_open = True
    try:
        from PySide6.QtWidgets import QApplication
        from ez_co.ui.dialogs.error_log_dialog import ErrorLogDialog

        app = QApplication.instance()
        if app is None:
            return
        dialog = ErrorLogDialog(where, text, app.activeWindow())
        dialog.exec()
    except Exception:
        # ダイアログを出せなければ捨てる
        pass
    finally:
        _dialog_open = False


def _enqueue_error_dialog(where: str, text: str) -> None:
    """エラーダイアログの表示をキューへ載せる。

    Args:
        where: 発生箇所
        text: 表示する本文
    """
    queue = _ensure_dialog_queue()
    if queue is None:
        return
    queue.requested.emit(where, text)


def _build_id_header() -> str:
    """識別子が取れなくても、呼び出し側は traceback を残す。

    Returns:
        ビルド識別子の見出し。取れなければ空
    """
    try:
        from ez_co.utils.app_info import build_id_error_header

        return build_id_error_header()
    except Exception:
        # ビルド識別子を取れなければ空の見出しを返す
        return ""


def report_error(where, exc=None, plugin_id=None, exc_info=None) -> None:
    """例外をログへ残し、有効ならダイアログを出す。

    Args:
        where: 発生箇所
        exc: 例外インスタンス
        plugin_id: プラグインの id。あれば箇所の前に付ける
        exc_info: 型、値、トレースバックの組
    """
    if exc_info is not None and _should_ignore(exc_info[0]):
        return
    if exc is not None and _should_ignore(type(exc)):
        return
    text = _format_error_text(exc=exc, exc_info=exc_info)
    if not text and exc is not None:
        text = f"{type(exc).__name__}: {exc}"
    if not text:
        return
    header = _build_id_header()
    if header:
        text = f"{header}\n\n{text}"
    location = str(where or "error")
    if plugin_id:
        location = f"{plugin_id} / {location}"
    try:
        get_error_logger().logger.error("%s\n%s", location, text)
    except Exception:
        # 専用ロガーに書けなければ、標準のロガーへ残す
        logging.getLogger("EzCo_Error").error("%s\n%s", location, text)
    if _is_error_log_enabled():
        _enqueue_error_dialog(location, text)


def initialize_error_logger(log_dir: Optional[Path] = None) -> ErrorLogger:
    """
    エラーロガーを初期化

    Args:
        log_dir: ログファイルの保存ディレクトリ

    Returns:
        初期化されたErrorLoggerインスタンス
    """
    global error_logger
    error_logger = ErrorLogger(log_dir)
    return error_logger


def get_error_logger() -> ErrorLogger:
    """
    グローバルなエラーロガーインスタンスを取得

    Returns:
        ErrorLoggerインスタンス
    """
    global error_logger
    if error_logger is None:
        error_logger = ErrorLogger()
    return error_logger


def setup_exception_handler():
    """未処理例外のハンドラーを設定"""
    def handle_exception(exc_type, exc_value, exc_traceback):
        """無視しない未処理例外を記録し、常に既定のフックへ渡す。

        Args:
            exc_type: 例外の型
            exc_value: 例外インスタンス
            exc_traceback: トレースバック
        """
        if _should_ignore(exc_type):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        report_error("unhandled", exc_value, exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception

    def handle_thread(args):
        """無視しないスレッド例外を記録する。

        Args:
            args: 例外の型、値、トレースバックを持つ情報
        """
        if _should_ignore(args.exc_type):
            return
        report_error(
            "thread",
            args.exc_value,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    threading.excepthook = handle_thread


class ErrorReportingApplication:
    """QApplication の notify を包み、スロット例外で落とさない。"""

    def notify(self, receiver, event):
        """イベント配送中の例外を記録して False を返す。

        Args:
            receiver: イベントの受け手
            event: 配送するイベント

        Returns:
            配送結果。例外のときは False
        """
        try:
            return super().notify(receiver, event)
        except Exception as exc:
            # イベント配送の例外は記録して偽を返す
            report_error("qt", exc)
            return False


def create_application(argv):
    """例外を記録する QApplication を作る。

    Args:
        argv: 起動引数

    Returns:
        生成したアプリケーション
    """
    from PySide6.QtWidgets import QApplication

    class _App(ErrorReportingApplication, QApplication):
        """ErrorReportingApplication と QApplication を継いだアプリケーション。"""
        pass

    return _App(argv)


def setup_qt_exception_handler(app):
    """ダイアログ用キューを用意する。notify の捕捉は create_application 側。

    Args:
        app: 対象のアプリケーション。None なら何もしない
    """
    if app is None:
        return
    _ensure_dialog_queue()
