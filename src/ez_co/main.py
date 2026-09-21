import sys
import os
import yaml
import importlib.resources
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QFont
from ez_co.ui.main_window import MainWindow
from ez_co.ui.plugins.plugin_session import PluginSession
from ez_co.config import Config
from ez_co.handlers.file_handler import FileHandler
from ez_co.utils.path_utils import get_project_root
from ez_co.utils.image_loading_recommendation import apply_recommendation
from ez_co.utils.data_location import (
    LOCATION_EXE,
    LOCATION_USER,
    apply_data_location,
    default_location_settings,
    exe_config_db_path,
    get_data_root,
    has_location_file,
    load_location_settings,
    set_data_root,
)
from ez_co.utils.language_manager import (
    language_manager,
    set_language,
    get_log_text,
    get_text,
    reload_external_languages,
)
from ez_co.utils.error_logger import (
    initialize_error_logger,
    setup_exception_handler,
    setup_qt_exception_handler,
    get_error_logger,
    set_error_log_enabled,
    create_application,
)
from ez_co.utils.database import DatabaseManager

# ロギングの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_config_args(args: List[str]) -> Dict[str, Any]:
    """コマンドライン引数から設定オーバーライドを解析する
    
    Args:
        args: コマンドライン引数のリスト
        
    Returns:
        パースされた設定のオーバーライド辞書
    """
    config_overrides = {}
    
    for arg in args:
        if arg.startswith('--conf:'):
            try:
                # --conf:section.key=value の形式を解析
                config_part = arg[7:]  # '--conf:' を除去
                if '=' in config_part:
                    key_path, value_str = config_part.split('=', 1)
                    
                    # 値の型を推定して変換
                    value = parse_config_value(value_str)
                    config_overrides[key_path] = value
                    
                    logger.info(f"設定オーバーライド: {key_path} = {value}")
                else:
                    logger.warning(f"無効な設定オーバーライド形式: {arg}")
            except Exception as e:
                logger.warning(f"設定オーバーライド解析エラー {arg}: {str(e)}")
    
    return config_overrides

def parse_profile_args(args: List[str]) -> Optional[str]:
    """コマンドライン引数からプロファイル指定を解析する
    
    対応形式: --profile=名前 / --profile 名前 / -p=名前 / -p 名前
    """
    for i, arg in enumerate(args):
        profile_name = None
        if arg.startswith('--profile='):
            profile_name = arg[10:]
        elif arg.startswith('-p='):
            profile_name = arg[3:]
        elif arg in ('--profile', '-p') and i + 1 < len(args):
            next_arg = args[i + 1]
            if not next_arg.startswith('-'):
                profile_name = next_arg
        if profile_name:
            profile_name = profile_name.strip()
            if profile_name:
                logger.info(f"プロファイル指定: {profile_name}")
                return profile_name
    return None

def parse_config_value(value_str: str) -> Any:
    """設定値文字列を適切な型に変換する
    
    Args:
        value_str: 設定値の文字列
        
    Returns:
        変換された値
    """
    # 大文字小文字を無視してブール値をチェック
    lower_value = value_str.lower()
    if lower_value in ('true', 'yes', 'on', '1'):
        return True
    elif lower_value in ('false', 'no', 'off', '0'):
        return False
    
    # 数値の変換を試行
    try:
        # まず整数として解析を試行
        if '.' not in value_str:
            return int(value_str)
        else:
            return float(value_str)
    except ValueError:
        pass
    
    # 文字列として返す
    return value_str

def ensure_data_location() -> bool:
    """場所の設定が無ければ初回ダイアログを出す。キャンセル／閉じるは起動しない。"""
    if has_location_file():
        settings = load_location_settings() or default_location_settings()
        set_data_root(apply_data_location(settings))
        return True
    from ez_co.ui.dialogs.data_location_dialog import DataLocationDialog

    dialog = DataLocationDialog(exe_config_db_path().is_file())
    if dialog.exec() != QDialog.Accepted:
        return False
    choice = dialog.choice()
    if choice == DataLocationDialog.CHOICE_EXE:
        apply_data_location({"data_location": LOCATION_EXE, "custom_path": ""})
    elif choice == DataLocationDialog.CHOICE_USER_COPY:
        apply_data_location(
            {"data_location": LOCATION_USER, "custom_path": ""},
            copy_from_exe=True,
        )
    else:
        apply_data_location({"data_location": LOCATION_USER, "custom_path": ""})
    return True


def maybe_import_legacy_yaml(db_manager: DatabaseManager):
    """残っている config.yaml があれば取り込み確認を出す"""
    config_path = None
    for candidate in (get_data_root() / "config.yaml", get_project_root() / "config.yaml"):
        if candidate.exists():
            config_path = candidate
            break
    if config_path is None:
        return
    try:
        from ez_co.ui.dialogs.yaml_import_dialog import YamlImportDialog
        dialog = YamlImportDialog(db_manager.get_profiles())
        if dialog.exec() != QDialog.Accepted:
            return
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data = Config.strip_profile_section(data)
        merged = Config.merge_with_defaults(data)
        profile_name = dialog.selected_profile()
        if dialog.is_new_profile():
            if not db_manager.create_profile(profile_name, merged):
                QMessageBox.critical(None, get_text("dialogs.error"), get_text("ui.profile_create_failed_msg"))
                return
        else:
            db_manager.save_profile_config(profile_name, merged)
        db_manager.set_current_profile_persistent(profile_name)
        QMessageBox.information(
            None,
            get_text("dialogs.information"),
            get_text("ui.yaml_import_success").format(profile_name=profile_name),
        )
        reply = QMessageBox.question(
            None,
            get_text("ui.confirmation"),
            get_text("ui.yaml_delete_confirm"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            config_path.unlink()
            logger.info(get_log_text("config_yaml_deleted"))
    except Exception as e:
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_config_load_error", error=e), e)
        QMessageBox.warning(None, get_text("dialogs.error"), get_text("ui.yaml_import_failed").format(error=e))

def load_config_from_db(db_manager: DatabaseManager) -> Config:
    """現在のプロファイルの設定をDBから読み込む"""
    try:
        profile_name = db_manager.current_profile
        data = db_manager.load_profile_config(profile_name)
        if not data:
            # 新規設定だけhardwareからの推奨値を初期値にする。既存設定は再計算しない
            config = Config()
            recommendation = apply_recommendation(config)
            db_manager.save_profile_config(profile_name, config.to_dict())
            logger.info(get_log_text("config_created"))
            logger.info(
                get_log_text(
                    "image_loading_recommendation_applied",
                    memory_limit=recommendation.memory_limit,
                    prefetch_pages=recommendation.prefetch_pages,
                    workers=recommendation.image_loader_workers,
                )
            )
            return config
        logger.info(get_log_text("config_loaded"))
        return Config.from_dict(data)
    except Exception as e:
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_config_load_error", error=e), e)
        return Config()

def initialize_language(config: Config):
    """言語を初期化"""
    try:
        # 設定から言語を読み込み
        language_code = config.language.get("code", "system")
        set_language(language_code)
        logger.info(get_log_text("language_initialized", language=language_code))
    except Exception as e:
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_language_init_error", error=e), e)

def initialize_debug_logging(config: Config):
    """デバッグログ機能を初期化"""
    try:
        if config.debug.get("enabled", False):
            # logsフォルダを作成
            logs_dir = get_data_root() / "logs"
            logs_dir.mkdir(exist_ok=True)
            # タイムスタンプ付きのログファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"debug_{timestamp}.log"
            log_file_path = logs_dir / log_filename
            # ファイルハンドラーを作成
            file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            # フォーマッターを設定
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            # ルートロガーにファイルハンドラーを追加
            root_logger = logging.getLogger()
            root_logger.addHandler(file_handler)
            root_logger.setLevel(logging.DEBUG)
            logger.info(get_log_text("main_debug_log_file_created", log_file_path=log_file_path))
            logger.info(get_log_text("application_started"))
    except Exception as e:
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_debug_log_init_error", error=e), e)

def initialize_profile(db_manager: DatabaseManager, config: Config, profile_name: Optional[str] = None):
    """プロファイルを初期化。引数指定が無い、または存在しない場合は前回のプロファイルを使う。"""
    try:
        previous_profile = db_manager.current_profile
        if profile_name:
            if db_manager.profile_exists(profile_name):
                db_manager.set_current_profile(profile_name)
                data = db_manager.load_profile_config(profile_name)
                if data:
                    config.apply_dict(data)
                config.set_runtime_override("profile.current_profile", profile_name)
                logger.info(get_log_text("profile_initialized", profile_name=profile_name))
                return profile_name

            logger.warning(get_log_text(
                "profile_not_found_use_previous",
                profile_name=profile_name,
                previous_profile=previous_profile,
            ))

        logger.info(get_log_text("profile_initialized", profile_name=previous_profile))
        return previous_profile
    except Exception as e:
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_profile_init_error", error=e), e)
        from ez_co.utils.database import get_default_profile_name
        return get_default_profile_name()


def connect_plugin_session(window, *, bootstrap=True) -> PluginSession:
    """プラグイン起動とウィンドウ結線。bootstrap は初回ウィンドウだけ。"""
    session = getattr(window, "plugin_session", None) or PluginSession()
    window.plugin_session = session
    if bootstrap:
        session.bootstrap(
            parent=window,
            config=window.config,
            rebuild_menu=window.rebuild_menu,
            save_profile=window.save_plugin_profile_config,
        )
    session.attach(
        window,
        config=window.config,
        db_manager=window.db_manager,
        current=window.plugin_current,
        reload_current=window.reload_current_for_plugin,
        run_action=lambda action_id, kwargs: window.run_window_action(action_id),
        app_config=window.plugin_app_config,
        restore_docks=window._restore_dock_state,
        first_shortcut=window._first_keyboard_shortcut,
        sidebar_menu=lambda: getattr(window, "sidebar_submenu", None),
        setup_shortcuts=window.setup_shortcuts,
        reload_open_files=window._reload_open_files_after_plugin_change,
        rebuild_menu=window.rebuild_menu,
        save_profile=window.save_plugin_profile_config,
        refresh_display=window.update_image,
        after_plugin_config=window._on_plugin_filter_config_changed,
    )
    return session


def create_new_window(config: Config, parent_window=None):
    """新規ウィンドウを作成"""
    try:
        from ez_co.ui.main_window import MainWindow
        # 新しいウィンドウを作成
        db_manager = getattr(parent_window, "db_manager", None) if parent_window is not None else None
        session = PluginSession()
        new_window = MainWindow(config, db_manager=db_manager, plugin_session=session)
        connect_plugin_session(new_window, bootstrap=False)
        # 新規ウィンドウにもフォント設定を適用
        try:
            ui_font = config.ui_font
            font_family = ui_font.get("font_family")
            font_size = ui_font.get("font_size")
            if font_family and font_size:
                window_font = QFont(font_family, font_size)
                new_window.setFont(window_font)
        except Exception as e:
            error_logger = get_error_logger()
            error_logger.log_error(get_log_text("main_new_window_font_error", error=e), e)
        # 親ウィンドウがある場合は位置をずらして表示
        if parent_window:
            # 親ウィンドウの位置を取得
            parent_x = parent_window.x()
            parent_y = parent_window.y()
            parent_width = parent_window.width()
            parent_height = parent_window.height()
            # 新しいウィンドウの位置を計算（親ウィンドウから30ピクセルずらす）
            offset = 30
            new_x = parent_x + offset
            new_y = parent_y + offset
            # 画面の範囲内に収める
            screen = QApplication.primaryScreen().geometry()
            if new_x + parent_width > screen.width():
                new_x = max(0, screen.width() - parent_width)
            if new_y + parent_height > screen.height():
                new_y = max(0, screen.height() - parent_height)
            # 新しいウィンドウの位置を設定
            new_window.move(new_x, new_y)
        new_window.show()
        return new_window
    except Exception as e:
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_new_window_create_error", error=e), e)
        return None

def main():
    try:
        # エラーログ機能を初期化
        initialize_error_logger()
        setup_exception_handler()
        app = create_application(sys.argv)
        app.setApplicationName(get_text("app_name"))
        # Qtアプリケーションの例外ハンドラーを設定
        setup_qt_exception_handler(app)
        # アイコンの設定
        try:
            with importlib.resources.path("ez_co.resources", "icon.ico") as icon_path:
                app.setWindowIcon(QIcon(str(icon_path)))
        except Exception as e:
            error_logger = get_error_logger()
            error_logger.log_error(get_log_text("main_icon_set_error", error=e), e)
        # 言語の初期化（DB読み込み前はシステム既定）
        initialize_language(Config())
        if not ensure_data_location():
            return 0
        initialize_error_logger(get_data_root())
        reload_external_languages()

        db_manager = DatabaseManager()
        maybe_import_legacy_yaml(db_manager)
        config = load_config_from_db(db_manager)
        db_manager.config = config
        
        # コマンドライン引数から設定オーバーライドを解析
        config_overrides = parse_config_args(sys.argv[1:])
        if config_overrides:
            logger.info(f"適用されるランタイム設定オーバーライド: {config_overrides}")
            # オーバーライドを設定に適用
            for key_path, value in config_overrides.items():
                config.set_runtime_override(key_path, value)
        
        # コマンドライン引数からプロファイル指定を解析
        specified_profile = parse_profile_args(sys.argv[1:])
        
        # プロファイルの初期化
        current_profile = initialize_profile(db_manager, config, specified_profile)
        # プロファイル設定の言語を適用
        initialize_language(config)
        effective_workers = config.freeze_image_loader_workers()
        logger.info(
            get_log_text(
                "image_loader_workers_resolved",
                configured=config.image_loader_workers_configured_at_start,
                resolved=effective_workers,
                cpu_count=config.image_loader_logical_cpu_count,
            )
        )
        # アプリケーションフォントの設定
        try:
            ui_font = config.ui_font
            font_family = ui_font.get("font_family")
            font_size = ui_font.get("font_size")
            if font_family and font_size:
                app_font = QFont(font_family, font_size)
                app.setFont(app_font)
                logger.info(get_log_text("main_app_font_set", font_family=font_family, font_size=font_size))
        except Exception as e:
            error_logger = get_error_logger()
            error_logger.log_error(get_log_text("main_app_font_set_error", error=e), e)
        # デバッグログの初期化
        initialize_debug_logging(config)
        set_error_log_enabled(lambda: bool(config.debug.get("show_error_log", False)))
        # メインウィンドウの作成
        session = PluginSession()
        window = MainWindow(config, db_manager=db_manager, plugin_session=session)
        connect_plugin_session(window, bootstrap=True)
        
        # データベースマネージャーに現在のプロファイルを設定
        window.db_manager.set_current_profile(current_profile)
        
        window.show()
        # コマンドライン引数からファイルを開く（オプション引数を除外）
        file_arguments = [arg for arg in sys.argv[1:] if not arg.startswith('-')]
        if file_arguments:
            try:
                files = [Path(arg) for arg in file_arguments if Path(arg).exists()]
                if files:
                    logger.info(get_log_text("main_opening_files_from_command_line", file_list=files))
                    window.open_paths([str(f) for f in files], new_tab=False)
                    window.update_image()
                else:
                    # 引数は指定されたが存在しないファイルの場合、警告を表示
                    nonexistent_files = [arg for arg in file_arguments if not Path(arg).exists()]
                    if nonexistent_files:
                        logger.warning(get_log_text("main_nonexistent_files_specified", files=nonexistent_files))
            except Exception as e:
                error_logger = get_error_logger()
                error_logger.log_error(get_log_text("main_command_line_files_error", error=e), e)
        else:
            # ファイル引数がない場合、起動時最後のファイル復元オプションをチェック
            if config.history.get("open_last_file_on_startup", False):
                try:
                    logger.info(get_log_text("main_opening_last_file_on_startup"))
                    window.reopen_last_file()
                except Exception as e:
                    error_logger = get_error_logger()
                    error_logger.log_error(get_log_text("main_open_last_file_on_startup_error", error=e), e)
        return app.exec()
    except Exception as e:
        logger.exception(get_log_text("main_app_startup_fatal_error", error=e))
        error_logger = get_error_logger()
        error_logger.log_error(get_log_text("main_app_startup_fatal_error", error=e), e)
        return 1

if __name__ == "__main__":
    sys.exit(main())
