import sys
import os
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
class ErrorLogger:
    """エラーログを管理するクラス"""
    def __init__(self, log_dir: Optional[Path] = None):
        """
        エラーロガーを初期化
        Args:
            log_dir: ログファイルの保存ディレクトリ（Noneの場合は実行ファイルと同じディレクトリ）
        """
        if log_dir is None:
            # 実行ファイルと同じディレクトリにログファイルを作成
            if getattr(sys, 'frozen', False):
                # PyInstallerでビルドされた場合
                self.log_dir = Path(sys.executable).parent
            else:
                # 開発環境の場合
                self.log_dir = Path(__file__).parent.parent.parent.parent
        self.log_dir = Path(log_dir) if log_dir else self.log_dir
        self.log_dir = self.log_dir / "logs"
        self.log_dir.mkdir(exist_ok=True)
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
    def log_exception(self, exc_type, exc_value, exc_traceback):
        """
        例外をログに記録
        Args:
            exc_type: 例外の型
            exc_value: 例外の値
            exc_traceback: トレースバック
        """
        try:
            # 例外情報をログに記録
            self.logger.error(
                f"Unhandled exception occurred:\n"
                f"Type: {exc_type.__name__}\n"
                f"Value: {exc_value}\n"
                f"Traceback:\n{''.join(traceback.format_tb(exc_traceback))}"
            )
        except Exception as e:
            # ログ記録中にエラーが発生した場合のフォールバック
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - ERROR - "
                           f"Failed to log exception: {e}\n")
            except:
                pass  # 最後の手段として何もしない
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
                pass
    def cleanup(self):
        """リソースをクリーンアップ"""
        try:
            self.file_handler.close()
            self.logger.removeHandler(self.file_handler)
        except:
            pass
# グローバルなエラーロガーインスタンス
error_logger = None
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
        """未処理例外をハンドリング"""
        logger = get_error_logger()
        logger.log_exception(exc_type, exc_value, exc_traceback)
        # 元のsys.excepthookを呼び出して標準的な処理も行う
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    # 未処理例外のハンドラーを設定
    sys.excepthook = handle_exception
def setup_qt_exception_handler(app):
    """
    Qtアプリケーションのイベントループ内での例外をキャッチするハンドラーを設定
    Args:
        app: QApplicationインスタンス
    """
    def qt_exception_handler(exc_type, exc_value, exc_traceback):
        """Qtイベントループ内での例外をハンドリング"""
        logger = get_error_logger()
        logger.log_exception(exc_type, exc_value, exc_traceback)
        # 元のsys.excepthookを呼び出して標準的な処理も行う
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    # Qtアプリケーションのイベントループ内での例外をキャッチ
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        def check_exceptions():
            """定期的に例外をチェック"""
            if hasattr(sys, 'last_type') and sys.last_type is not None:
                qt_exception_handler(sys.last_type, sys.last_value, sys.last_traceback)
                # クリア
                sys.last_type = None
                sys.last_value = None
                sys.last_traceback = None
        # タイマーを設定して定期的に例外をチェック
        timer = QTimer()
        timer.timeout.connect(check_exceptions)
        timer.start(1000)  # 1秒ごとにチェック
    except ImportError:
        # PySide6が利用できない場合
        pass 