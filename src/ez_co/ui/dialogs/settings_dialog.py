from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QLineEdit,
    QSpinBox, QCheckBox, QPushButton, QDialogButtonBox, QColorDialog,
    QComboBox, QGroupBox, QSlider, QTabWidget, QWidget, QGridLayout,
    QFileDialog, QMessageBox, QScrollArea, QCompleter, QRadioButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
import html
import yaml
import logging
import humanfriendly
from ez_co.enums.fonts import FontInfo, FontFamilyManager
from ez_co.config import Config
from ez_co.utils.language_manager import get_text, get_available_languages, set_language, get_log_text
from ez_co.utils.data_location import (
    LOCATION_CUSTOM,
    LOCATION_EXE,
    LOCATION_USER,
    default_location_settings,
    is_writable_dir,
    load_location_settings,
    resolve_data_root,
    save_location_settings,
)

logger = logging.getLogger(__name__)

class SettingsDialog(QDialog):
    """設定ダイアログ"""
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self._setting_tip_widgets = {}
        self.setup_ui()
        self.apply_runtime_overrides()

    def _setting_tip_text(self, key):
        """設定項目の詳細説明を取得（tip → description の順）"""
        tip_key = f"settings.{key}_tip"
        tip = get_text(tip_key)
        if tip != tip_key:
            return tip
        desc_key = f"settings.{key}_description"
        desc = get_text(desc_key)
        if desc != desc_key:
            return desc
        return ""

    def _format_tooltip(self, text):
        if not text:
            return ""
        escaped = html.escape(text).replace("\n", "<br>")
        return f"<p style='white-space:pre-wrap; max-width:380px;'>{escaped}</p>"

    def _apply_setting_tip(self, key, *widgets, extra_text=""):
        text = self._setting_tip_text(key)
        if extra_text:
            text = f"{text}\n\n{extra_text}" if text else extra_text
        formatted = self._format_tooltip(text)
        if not formatted:
            return
        registered = self._setting_tip_widgets.setdefault(key, [])
        for widget in widgets:
            if widget is None:
                continue
            widget.setToolTip(formatted)
            widget.setToolTipDuration(15000)
            if widget not in registered:
                registered.append(widget)

    def _form_label(self, key, suffix=":"):
        label = QLabel(get_text(f"settings.{key}") + suffix)
        self._apply_setting_tip(key, label)
        return label

    def _disable_if_overridden(self, config_key, tip_key, *widgets):
        if not self.config.is_runtime_overridden(config_key):
            return
        override = get_text("settings.runtime_override_tooltip")
        all_widgets = list(widgets) + list(self._setting_tip_widgets.get(tip_key, []))
        unique = []
        seen = set()
        for widget in all_widgets:
            if widget is None or id(widget) in seen:
                continue
            seen.add(id(widget))
            unique.append(widget)
        for widget in unique:
            if not isinstance(widget, QLabel):
                widget.setEnabled(False)
        self._apply_setting_tip(tip_key, *unique, extra_text=override)

    def setup_ui(self):
        """UIの初期化"""
        self.setWindowTitle(get_text("settings.title"))
        self.setFixedSize(550, 560)
        
        layout = QVBoxLayout()
        
        # タブウィジェットを作成
        self.tab_widget = QTabWidget()
        
        # 各タブを作成
        self.create_general_tab()
        self.create_display_tab()
        self.create_behavior_tab()
        self.create_development_tab()
        
        layout.addWidget(self.tab_widget)
        
        # ボタンレイアウト
        button_layout = QHBoxLayout()
        
        # エクスポート・インポートボタン追加
        export_button = QPushButton(get_text("ui.export"))
        export_button.clicked.connect(self.export_config)
        button_layout.addWidget(export_button)
        
        import_button = QPushButton(get_text("ui.import"))
        import_button.clicked.connect(self.import_config)
        button_layout.addWidget(import_button)
        
        button_layout.addStretch()
        
        # 初期化ボタン
        reset_button = QPushButton(get_text("ui.reset"))
        reset_button.clicked.connect(self.reset_settings)
        button_layout.addWidget(reset_button)
        
        # 適用ボタン
        apply_button = QPushButton(get_text("ui.apply"))
        apply_button.clicked.connect(self.apply_settings)
        button_layout.addWidget(apply_button)
        
        # OK/Cancelボタン
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        cancel_button = QPushButton(get_text("ui.cancel"))
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def apply_runtime_overrides(self):
        """ランタイムオーバーライドが適用されている設定項目を非活性化"""
        self._disable_if_overridden("language.code", "language", self.language_combo)
        self._disable_if_overridden("window.auto_resize", "auto_resize", self.auto_resize_checkbox)
        self._disable_if_overridden("window.save_window_state", "save_window_state", self.save_window_state_checkbox)
        self._disable_if_overridden("window.maximize_on_startup", "maximize_on_startup", self.maximize_on_startup_checkbox)
        self._disable_if_overridden("viewer.background_color", "background_color", self.bg_color_button)
        self._disable_if_overridden("viewer.fit_to_window", "fit_to_window", self.fit_to_window_checkbox)
        self._disable_if_overridden("viewer.fit_to_window_minimum", "fit_to_window_minimum", self.fit_to_window_min_checkbox)
        self._disable_if_overridden("viewer.spread_selected_as_axis", "spread_selected_as_axis", self.spread_selected_as_axis_checkbox)
        self._disable_if_overridden("viewer.spread_toggle_preference", "spread_toggle_preference", self.spread_toggle_preference_combo)
        self._disable_if_overridden(
            "viewer.image_move_sensitivity", "image_move_sensitivity",
            self.sensitivity_slider, self.sensitivity_input
        )
        self._disable_if_overridden(
            "viewer.gesture_threshold", "gesture_threshold",
            self.gesture_threshold_slider, self.gesture_threshold_input
        )
        self._disable_if_overridden(
            "viewer.mouse_repeat_initial_delay", "mouse_repeat_initial_delay",
            self.mouse_repeat_initial_delay_slider, self.mouse_repeat_initial_delay_input
        )
        self._disable_if_overridden(
            "viewer.mouse_repeat_acceleration_start", "mouse_repeat_acceleration_start",
            self.mouse_repeat_acceleration_start_slider, self.mouse_repeat_acceleration_start_input
        )
        self._disable_if_overridden(
            "viewer.mouse_repeat_min_interval", "mouse_repeat_min_interval",
            self.mouse_repeat_min_interval_slider, self.mouse_repeat_min_interval_input
        )
        self._disable_if_overridden("ui_font.font_family", "font_family", self.ui_font_family)
        self._disable_if_overridden("ui_font.font_size", "font_size", self.ui_font_size)
        self._disable_if_overridden("ui_font.font_color", "font_color", self.ui_font_color_btn)
        self._disable_if_overridden("ui_font.bg_color", "background_color_popup", self.ui_bg_color_btn)
        self._disable_if_overridden("ui_font.alpha", "transparency", self.ui_alpha)
        self._disable_if_overridden("history.max_count", "max_history_count", self.history_max_count_spin)
        self._disable_if_overridden("history.restore_page_on_reopen", "restore_page_on_reopen", self.restore_page_checkbox)
        self._disable_if_overridden("history.open_last_file_on_startup", "open_last_file_on_startup", self.open_last_file_checkbox)
        self._disable_if_overridden("viewer.drop_opens_new_tab", "drop_opens_new_tab", self.drop_opens_combo)
        self._disable_if_overridden("viewer.open_archives_in_own_tab", "open_archives_in_own_tab", self.open_archives_own_tab_checkbox)
        self._disable_if_overridden("viewer.open_folders_in_own_tab", "open_folders_in_own_tab", self.open_folders_own_tab_checkbox)
        self._disable_if_overridden("cache.memory_limit", "cache_memory_limit", self.cache_memory_limit)
        self._disable_if_overridden("cache.prefetch_pages", "cache_prefetch_pages", self.cache_prefetch_pages)
        self._disable_if_overridden("cache.optimize_large_images", "optimize_large_images", self.optimize_large_images_checkbox)
        self._disable_if_overridden("cache.optimize_threshold", "optimize_threshold", self.optimize_threshold)
        self._disable_if_overridden("cache.optimize_max_resolution", "optimize_max_resolution", self.optimize_max_resolution)
        self._disable_if_overridden("debug.enabled", "debug_mode", self.debug_mode_checkbox)
        self._disable_if_overridden("debug.keep_archive_handles", "keep_archive_handles", self.keep_archive_handles_checkbox)
        self._disable_if_overridden("debug.cache_archive_metadata", "cache_archive_metadata", self.cache_archive_metadata_checkbox)
        self._disable_if_overridden("debug.show_error_log", "show_error_log", self.show_error_log_checkbox)

    def create_general_tab(self):
        """全般タブを作成"""
        general_widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(general_widget)
        
        layout = QVBoxLayout()

        location_group = QGroupBox(get_text("settings.data_location_settings"))
        location_layout = QVBoxLayout()
        current = load_location_settings() or default_location_settings()
        self._location_group = QButtonGroup(self)
        self.location_user_radio = QRadioButton(get_text("settings.data_location_user"))
        self.location_exe_radio = QRadioButton(get_text("settings.data_location_exe"))
        self.location_custom_radio = QRadioButton(get_text("settings.data_location_custom"))
        self._location_group.addButton(self.location_user_radio)
        self._location_group.addButton(self.location_exe_radio)
        self._location_group.addButton(self.location_custom_radio)
        location_layout.addWidget(self.location_user_radio)
        location_layout.addWidget(self.location_exe_radio)
        self.location_exe_warning = QLabel(get_text("settings.data_location_exe_warning"))
        self.location_exe_warning.setWordWrap(True)
        self.location_exe_warning.setStyleSheet("color: #c47d00;")
        location_layout.addWidget(self.location_exe_warning)
        location_layout.addWidget(self.location_custom_radio)
        self.location_custom_warning = QLabel(get_text("settings.data_location_custom_warning"))
        self.location_custom_warning.setWordWrap(True)
        self.location_custom_warning.setStyleSheet("color: #c47d00;")
        location_layout.addWidget(self.location_custom_warning)
        custom_row = QHBoxLayout()
        self.location_custom_edit = QLineEdit()
        self.location_custom_edit.setText(current.get("custom_path") or "")
        self.location_browse_button = QPushButton(get_text("settings.data_location_browse"))
        self.location_browse_button.clicked.connect(self._browse_data_location)
        custom_row.addWidget(self.location_custom_edit)
        custom_row.addWidget(self.location_browse_button)
        location_layout.addLayout(custom_row)
        self.location_restart_note = QLabel(get_text("settings.data_location_restart_note"))
        self.location_restart_note.setWordWrap(True)
        location_layout.addWidget(self.location_restart_note)
        location_group.setLayout(location_layout)
        layout.addWidget(location_group)
        mode = current.get("data_location", LOCATION_USER)
        self.location_user_radio.setChecked(mode == LOCATION_USER)
        self.location_exe_radio.setChecked(mode == LOCATION_EXE)
        self.location_custom_radio.setChecked(mode == LOCATION_CUSTOM)
        self.location_exe_radio.toggled.connect(self._update_location_controls)
        self.location_custom_radio.toggled.connect(self._update_location_controls)
        self._update_location_controls()
        self._apply_setting_tip("data_location", location_group)

        # 言語設定
        language_group = QGroupBox(get_text("settings.language_settings"))
        language_layout = QFormLayout()
        
        self.language_combo = QComboBox()
        self.language_combo.setMaximumWidth(200)  # 最大幅を制限
        available_languages = get_available_languages()
        current_language = self.config.language.get("code", "system")
        
        for lang_code, lang_info in available_languages.items():
            self.language_combo.addItem(lang_info["name"], lang_code)
            if lang_code == current_language:
                self.language_combo.setCurrentText(lang_info["name"])
        
        language_layout.addRow(self._form_label("language"), self.language_combo)
        self._apply_setting_tip("language", self.language_combo)
        self.language_plugin_layout_note = QLabel(get_text("settings.language_plugin_layout_note"))
        self.language_plugin_layout_note.setWordWrap(True)
        language_layout.addRow(self.language_plugin_layout_note)
        language_group.setLayout(language_layout)
        layout.addWidget(language_group)
        
        # ウィンドウ設定
        window_group = QGroupBox(get_text("settings.window_settings"))
        window_layout = QFormLayout()
        
        # ウィンドウサイズの自動調整
        self.auto_resize_checkbox = QCheckBox(get_text("settings.auto_resize"))
        self.auto_resize_checkbox.setChecked(self.config.window["auto_resize"])
        self._apply_setting_tip("auto_resize", self.auto_resize_checkbox)
        window_layout.addRow(self.auto_resize_checkbox)
        
        # ウィンドウサイズを保存
        self.save_window_state_checkbox = QCheckBox(get_text("settings.save_window_state"))
        self.save_window_state_checkbox.setChecked(self.config.window.get("save_window_state", True))
        self._apply_setting_tip("save_window_state", self.save_window_state_checkbox)
        window_layout.addRow(self.save_window_state_checkbox)
        
        # 起動時に最大化
        self.maximize_on_startup_checkbox = QCheckBox(get_text("settings.maximize_on_startup"))
        self.maximize_on_startup_checkbox.setChecked(self.config.window.get("maximize_on_startup", False))
        self._apply_setting_tip("maximize_on_startup", self.maximize_on_startup_checkbox)
        window_layout.addRow(self.maximize_on_startup_checkbox)
        
        window_group.setLayout(window_layout)
        layout.addWidget(window_group)
        
        layout.addStretch()
        general_widget.setLayout(layout)
        
        self.tab_widget.addTab(scroll_area, get_text("settings.tab_general"))

    def _update_location_controls(self):
        custom = self.location_custom_radio.isChecked()
        self.location_custom_edit.setEnabled(custom)
        self.location_browse_button.setEnabled(custom)
        self.location_custom_warning.setVisible(custom)
        self.location_exe_warning.setVisible(self.location_exe_radio.isChecked())

    def _browse_data_location(self):
        path = QFileDialog.getExistingDirectory(
            self,
            get_text("settings.data_location_browse"),
            self.location_custom_edit.text() or "",
        )
        if path:
            self.location_custom_edit.setText(path)
            self.location_custom_radio.setChecked(True)
            self._update_location_controls()

    def _current_location_settings(self) -> dict:
        if self.location_exe_radio.isChecked():
            mode = LOCATION_EXE
        elif self.location_custom_radio.isChecked():
            mode = LOCATION_CUSTOM
        else:
            mode = LOCATION_USER
        return {
            "data_location": mode,
            "custom_path": self.location_custom_edit.text().strip(),
        }

    def create_display_tab(self):
        """表示タブを作成"""
        display_widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(display_widget)
        
        layout = QVBoxLayout()
        
        # ビューア設定
        viewer_group = QGroupBox(get_text("settings.viewer_settings"))
        viewer_layout = QFormLayout()
        
        # 背景色
        self.bg_color_button = QPushButton()
        self.bg_color_button.setStyleSheet(
            f"background-color: {self.config.viewer['background_color']};"
            "min-width: 100px; max-width: 150px; min-height: 20px;"
        )
        self.bg_color_button.clicked.connect(self.select_background_color)
        viewer_layout.addRow(self._form_label("background_color"), self.bg_color_button)
        self._apply_setting_tip("background_color", self.bg_color_button)
        
        # 画像をウィンドウに合わせる
        self.fit_to_window_checkbox = QCheckBox(get_text("settings.fit_to_window"))
        self.fit_to_window_checkbox.setChecked(self.config.viewer["fit_to_window"])
        self._apply_setting_tip("fit_to_window", self.fit_to_window_checkbox)
        viewer_layout.addRow(self.fit_to_window_checkbox)
        
        # 画像の最小縮小率を全画面までに制限
        self.fit_to_window_min_checkbox = QCheckBox(get_text("settings.fit_to_window_minimum"))
        self.fit_to_window_min_checkbox.setChecked(self.config.viewer.get("fit_to_window_minimum", True))
        self._apply_setting_tip("fit_to_window_minimum", self.fit_to_window_min_checkbox)
        viewer_layout.addRow(self.fit_to_window_min_checkbox)

        # 両開きは選択ページを軸にする
        self.spread_selected_as_axis_checkbox = QCheckBox(get_text("settings.spread_selected_as_axis"))
        self.spread_selected_as_axis_checkbox.setChecked(self.config.viewer.get("spread_selected_as_axis", False))
        self._apply_setting_tip("spread_selected_as_axis", self.spread_selected_as_axis_checkbox)
        viewer_layout.addRow(self.spread_selected_as_axis_checkbox)

        # 両開き／単ページ切替時の両開き
        self.spread_toggle_preference_combo = QComboBox()
        self.spread_toggle_preference_combo.setMaximumWidth(280)
        self.spread_toggle_preference_combo.addItem(
            get_text("settings.spread_toggle_keep_previous"), "keep_previous"
        )
        self.spread_toggle_preference_combo.addItem(
            get_text("settings.spread_toggle_prefer_right"), "prefer_right"
        )
        self.spread_toggle_preference_combo.addItem(
            get_text("settings.spread_toggle_prefer_left"), "prefer_left"
        )
        current_spread_pref = self.config.viewer.get("spread_toggle_preference", "keep_previous")
        pref_index = self.spread_toggle_preference_combo.findData(current_spread_pref)
        self.spread_toggle_preference_combo.setCurrentIndex(pref_index if pref_index >= 0 else 0)
        viewer_layout.addRow(self._form_label("spread_toggle_preference"), self.spread_toggle_preference_combo)
        self._apply_setting_tip("spread_toggle_preference", self.spread_toggle_preference_combo)
        
        # 画像移動感度
        sensitivity_layout = QHBoxLayout()
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(5, 40)  # 0.5～4.0を50～400で表現
        sensitivity_value = self.config.viewer.get("image_move_sensitivity", 2.0)
        self.sensitivity_slider.setValue(int(sensitivity_value * 10))
        
        self.sensitivity_input = QLineEdit()
        self.sensitivity_input.setText(f"{sensitivity_value:.1f}")
        self.sensitivity_input.setPlaceholderText("0.5～4.0")
        self.sensitivity_input.setMaximumWidth(80)  # 最大幅を制限
        
        # スライダーとテキストボックスの連動
        self.sensitivity_slider.valueChanged.connect(self.on_sensitivity_slider_changed)
        self.sensitivity_input.textChanged.connect(self.on_sensitivity_input_changed)
        self.sensitivity_input.editingFinished.connect(self.on_sensitivity_input_finished)
        
        sensitivity_layout.addWidget(self.sensitivity_slider)
        sensitivity_layout.addWidget(self.sensitivity_input)
        viewer_layout.addRow(self._form_label("image_move_sensitivity"), sensitivity_layout)
        self._apply_setting_tip("image_move_sensitivity", self.sensitivity_slider, self.sensitivity_input)
        
        # マウスジェスチャー判定距離
        gesture_layout = QHBoxLayout()
        self.gesture_threshold_slider = QSlider(Qt.Horizontal)
        self.gesture_threshold_slider.setRange(20, 100)  # 20～100ピクセル
        gesture_threshold_value = self.config.viewer.get("gesture_threshold", 50)
        self.gesture_threshold_slider.setValue(gesture_threshold_value)
        
        self.gesture_threshold_input = QLineEdit()
        self.gesture_threshold_input.setText(str(gesture_threshold_value))
        self.gesture_threshold_input.setPlaceholderText("20～100")
        self.gesture_threshold_input.setMaximumWidth(80)  # 最大幅を制限
        
        # スライダーとテキストボックスの連動
        self.gesture_threshold_slider.valueChanged.connect(self.on_gesture_threshold_slider_changed)
        self.gesture_threshold_input.textChanged.connect(self.on_gesture_threshold_input_changed)
        self.gesture_threshold_input.editingFinished.connect(self.on_gesture_threshold_input_finished)
        
        gesture_layout.addWidget(self.gesture_threshold_slider)
        gesture_layout.addWidget(self.gesture_threshold_input)
        viewer_layout.addRow(self._form_label("gesture_threshold"), gesture_layout)
        self._apply_setting_tip("gesture_threshold", self.gesture_threshold_slider, self.gesture_threshold_input)
        
        # マウスリピート初期間隔
        mouse_repeat_initial_delay_layout = QHBoxLayout()
        self.mouse_repeat_initial_delay_slider = QSlider(Qt.Horizontal)
        self.mouse_repeat_initial_delay_slider.setRange(50, 500)  # 50～500ms
        mouse_repeat_initial_delay_value = self.config.viewer.get("mouse_repeat_initial_delay", 100)
        self.mouse_repeat_initial_delay_slider.setValue(mouse_repeat_initial_delay_value)
        
        self.mouse_repeat_initial_delay_input = QLineEdit()
        self.mouse_repeat_initial_delay_input.setText(str(mouse_repeat_initial_delay_value))
        self.mouse_repeat_initial_delay_input.setPlaceholderText("50～500")
        self.mouse_repeat_initial_delay_input.setMaximumWidth(80)
        
        self.mouse_repeat_initial_delay_slider.valueChanged.connect(self.on_mouse_repeat_initial_delay_slider_changed)
        self.mouse_repeat_initial_delay_input.textChanged.connect(self.on_mouse_repeat_initial_delay_input_changed)
        self.mouse_repeat_initial_delay_input.editingFinished.connect(self.on_mouse_repeat_initial_delay_input_finished)
        
        mouse_repeat_initial_delay_layout.addWidget(self.mouse_repeat_initial_delay_slider)
        mouse_repeat_initial_delay_layout.addWidget(self.mouse_repeat_initial_delay_input)
        viewer_layout.addRow(self._form_label("mouse_repeat_initial_delay"), mouse_repeat_initial_delay_layout)
        self._apply_setting_tip(
            "mouse_repeat_initial_delay",
            self.mouse_repeat_initial_delay_slider, self.mouse_repeat_initial_delay_input
        )
        
        # マウスリピート加速開始時刻
        mouse_repeat_acceleration_start_layout = QHBoxLayout()
        self.mouse_repeat_acceleration_start_slider = QSlider(Qt.Horizontal)
        self.mouse_repeat_acceleration_start_slider.setRange(50, 500)  # 50～500ms
        mouse_repeat_acceleration_start_value = self.config.viewer.get("mouse_repeat_acceleration_start", 100)
        self.mouse_repeat_acceleration_start_slider.setValue(mouse_repeat_acceleration_start_value)
        
        self.mouse_repeat_acceleration_start_input = QLineEdit()
        self.mouse_repeat_acceleration_start_input.setText(str(mouse_repeat_acceleration_start_value))
        self.mouse_repeat_acceleration_start_input.setPlaceholderText("50～500")
        self.mouse_repeat_acceleration_start_input.setMaximumWidth(80)
        
        self.mouse_repeat_acceleration_start_slider.valueChanged.connect(self.on_mouse_repeat_acceleration_start_slider_changed)
        self.mouse_repeat_acceleration_start_input.textChanged.connect(self.on_mouse_repeat_acceleration_start_input_changed)
        self.mouse_repeat_acceleration_start_input.editingFinished.connect(self.on_mouse_repeat_acceleration_start_input_finished)
        
        mouse_repeat_acceleration_start_layout.addWidget(self.mouse_repeat_acceleration_start_slider)
        mouse_repeat_acceleration_start_layout.addWidget(self.mouse_repeat_acceleration_start_input)
        viewer_layout.addRow(self._form_label("mouse_repeat_acceleration_start"), mouse_repeat_acceleration_start_layout)
        self._apply_setting_tip(
            "mouse_repeat_acceleration_start",
            self.mouse_repeat_acceleration_start_slider, self.mouse_repeat_acceleration_start_input
        )
        
        # マウスリピート最小間隔
        mouse_repeat_min_interval_layout = QHBoxLayout()
        self.mouse_repeat_min_interval_slider = QSlider(Qt.Horizontal)
        self.mouse_repeat_min_interval_slider.setRange(10, 100)  # 10～100ms
        mouse_repeat_min_interval_value = self.config.viewer.get("mouse_repeat_min_interval", 30)
        self.mouse_repeat_min_interval_slider.setValue(mouse_repeat_min_interval_value)
        
        self.mouse_repeat_min_interval_input = QLineEdit()
        self.mouse_repeat_min_interval_input.setText(str(mouse_repeat_min_interval_value))
        self.mouse_repeat_min_interval_input.setPlaceholderText("10～100")
        self.mouse_repeat_min_interval_input.setMaximumWidth(80)
        
        self.mouse_repeat_min_interval_slider.valueChanged.connect(self.on_mouse_repeat_min_interval_slider_changed)
        self.mouse_repeat_min_interval_input.textChanged.connect(self.on_mouse_repeat_min_interval_input_changed)
        self.mouse_repeat_min_interval_input.editingFinished.connect(self.on_mouse_repeat_min_interval_input_finished)
        
        mouse_repeat_min_interval_layout.addWidget(self.mouse_repeat_min_interval_slider)
        mouse_repeat_min_interval_layout.addWidget(self.mouse_repeat_min_interval_input)
        viewer_layout.addRow(self._form_label("mouse_repeat_min_interval"), mouse_repeat_min_interval_layout)
        self._apply_setting_tip(
            "mouse_repeat_min_interval",
            self.mouse_repeat_min_interval_slider, self.mouse_repeat_min_interval_input
        )
        
        viewer_group.setLayout(viewer_layout)
        layout.addWidget(viewer_group)
        
        # UIフォント設定
        ui_font_group = QGroupBox(get_text("settings.ui_font_settings"))
        ui_font_layout = QFormLayout()
        
        # フォントファミリー選択（フィルタリング対応）
        self.ui_font_family = QComboBox()
        self.ui_font_family.setEditable(True)
        self.ui_font_family.setMaximumWidth(200)  # 最大幅を制限
        font_families = FontFamilyManager.get_available_font_families()
        self.ui_font_family.addItems(font_families)
        
        # フォントファミリー用コンプリーター設定
        self.font_family_completer = QCompleter(font_families)
        self.font_family_completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.font_family_completer.setFilterMode(Qt.MatchContains)
        self.ui_font_family.setCompleter(self.font_family_completer)
        
        # プレースホルダーテキストを設定
        if self.ui_font_family.lineEdit():
            self.ui_font_family.lineEdit().setPlaceholderText(get_text("settings.font_family_placeholder"))
        
        # フォントバリアント選択（フィルタリング対応）
        self.ui_font_variant = QComboBox()
        self.ui_font_variant.setEditable(True)
        self.ui_font_variant.setMaximumWidth(200)  # 最大幅を制限
        
        # フォントファミリー変更時にバリアントを更新
        self.ui_font_family.currentTextChanged.connect(self.update_font_variants)
        self.ui_font_family.editTextChanged.connect(self.update_font_variants)
        
        # 現在の設定値に基づいて選択
        current_font = self.config.ui_font.get("font_family", "メイリオ")
        normalized_font = FontFamilyManager.normalize_font_name(current_font)
        
        # フォントファミリーを設定
        if normalized_font in font_families:
            self.ui_font_family.setEditText(normalized_font)
        elif current_font in font_families:
            self.ui_font_family.setEditText(current_font)
        else:
            # 見つからない場合は正規化した名前を設定
            self.ui_font_family.setEditText(normalized_font)
        
        # 初回のバリアント更新
        self.update_font_variants()
        
        # バリアントが複数ある場合は現在の設定に最も近いものを選択
        if current_font != normalized_font:
            # バリアント一覧から現在のフォントを探す
            current_variants = [self.ui_font_variant.itemText(i) for i in range(self.ui_font_variant.count())]
            if current_font in current_variants:
                self.ui_font_variant.setEditText(current_font)
        
        self.ui_font_size = QSpinBox()
        self.ui_font_size.setMaximumWidth(100)  # 最大幅を制限
        self.ui_font_size.setRange(8, 64)
        self.ui_font_size.setValue(self.config.ui_font.get("font_size", 18))
        
        # 文字色
        self.ui_font_color_btn = QPushButton()
        font_color = self.config.ui_font.get('font_color', '#0000ff')
        self.ui_font_color_btn.setStyleSheet(f"background-color: {font_color}; min-width: 100px; max-width: 150px; min-height: 20px;")
        self.ui_font_color_btn.clicked.connect(self.select_ui_font_color)
        
        # 背景色
        self.ui_bg_color_btn = QPushButton()
        bg_color = self.config.ui_font.get('bg_color', '#ffffff')
        self.ui_bg_color_btn.setStyleSheet(f"background-color: {bg_color}; min-width: 100px; max-width: 150px; min-height: 20px;")
        self.ui_bg_color_btn.clicked.connect(self.select_ui_bg_color)
        
        # 透過度
        self.ui_alpha = QSpinBox()
        self.ui_alpha.setMaximumWidth(100)  # 最大幅を制限
        self.ui_alpha.setRange(0, 255)
        self.ui_alpha.setValue(self.config.ui_font.get('alpha', 170))
        
        ui_font_layout.addRow(self._form_label("font_family", suffix=""), self.ui_font_family)
        ui_font_layout.addRow(self._form_label("font_style", suffix=""), self.ui_font_variant)
        ui_font_layout.addRow(self._form_label("font_size", suffix=""), self.ui_font_size)
        ui_font_layout.addRow(self._form_label("font_color", suffix=""), self.ui_font_color_btn)
        ui_font_layout.addRow(self._form_label("background_color_popup", suffix=""), self.ui_bg_color_btn)
        ui_font_layout.addRow(self._form_label("transparency", suffix=""), self.ui_alpha)
        self._apply_setting_tip("font_family", self.ui_font_family)
        self._apply_setting_tip("font_style", self.ui_font_variant)
        self._apply_setting_tip("font_size", self.ui_font_size)
        self._apply_setting_tip("font_color", self.ui_font_color_btn)
        self._apply_setting_tip("background_color_popup", self.ui_bg_color_btn)
        self._apply_setting_tip("transparency", self.ui_alpha)
        
        ui_font_group.setLayout(ui_font_layout)
        layout.addWidget(ui_font_group)
        
        layout.addStretch()
        display_widget.setLayout(layout)
        
        self.tab_widget.addTab(scroll_area, get_text("settings.tab_display"))

    def create_behavior_tab(self):
        """動作タブを作成"""
        behavior_widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(behavior_widget)
        
        layout = QVBoxLayout()
        
        # 履歴設定
        history_group = QGroupBox(get_text("settings.history_settings"))
        history_layout = QFormLayout()
        
        # 履歴の最大数
        self.history_max_count_spin = QSpinBox()
        self.history_max_count_spin.setMaximumWidth(100)  # 最大幅を制限
        self.history_max_count_spin.setRange(1, 99)
        self.history_max_count_spin.setValue(self.config.history.get("max_count", 20))
        history_layout.addRow(self._form_label("max_history_count"), self.history_max_count_spin)
        self._apply_setting_tip("max_history_count", self.history_max_count_spin)
        
        # 履歴ページ復元オプション
        self.restore_page_checkbox = QCheckBox(get_text("settings.restore_page_on_reopen"))
        self.restore_page_checkbox.setChecked(self.config.history.get("restore_page_on_reopen", False))
        self._apply_setting_tip("restore_page_on_reopen", self.restore_page_checkbox)
        history_layout.addRow(self.restore_page_checkbox)
        
        # 起動時最後のファイル復元オプション
        self.open_last_file_checkbox = QCheckBox(get_text("settings.open_last_file_on_startup"))
        self.open_last_file_checkbox.setChecked(self.config.history.get("open_last_file_on_startup", False))
        self._apply_setting_tip("open_last_file_on_startup", self.open_last_file_checkbox)
        history_layout.addRow(self.open_last_file_checkbox)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)

        tab_group = QGroupBox(get_text("settings.tab_settings"))
        tab_layout = QFormLayout()
        self.drop_opens_combo = QComboBox()
        self.drop_opens_combo.setMaximumWidth(280)
        self.drop_opens_combo.addItem(get_text("settings.drop_open_current"), False)
        self.drop_opens_combo.addItem(get_text("settings.drop_open_new"), True)
        drop_index = 1 if self.config.viewer.get("drop_opens_new_tab", False) else 0
        self.drop_opens_combo.setCurrentIndex(drop_index)
        tab_layout.addRow(self._form_label("drop_opens_new_tab"), self.drop_opens_combo)
        self._apply_setting_tip("drop_opens_new_tab", self.drop_opens_combo)
        self.open_archives_own_tab_checkbox = QCheckBox(get_text("settings.open_archives_in_own_tab"))
        self.open_archives_own_tab_checkbox.setChecked(self.config.viewer.get("open_archives_in_own_tab", True))
        self._apply_setting_tip("open_archives_in_own_tab", self.open_archives_own_tab_checkbox)
        tab_layout.addRow(self.open_archives_own_tab_checkbox)
        self.open_folders_own_tab_checkbox = QCheckBox(get_text("settings.open_folders_in_own_tab"))
        self.open_folders_own_tab_checkbox.setChecked(self.config.viewer.get("open_folders_in_own_tab", False))
        self._apply_setting_tip("open_folders_in_own_tab", self.open_folders_own_tab_checkbox)
        tab_layout.addRow(self.open_folders_own_tab_checkbox)
        tab_group.setLayout(tab_layout)
        layout.addWidget(tab_group)
        
        # キャッシュ設定
        cache_group = QGroupBox(get_text("settings.cache_settings"))
        cache_layout = QFormLayout()
        
        # メモリキャッシュサイズ
        self.cache_memory_limit = QLineEdit()
        self.cache_memory_limit.setMaximumWidth(200)
        self.cache_memory_limit.setText(self.config.cache.get("memory_limit", "256MB"))
        self.cache_memory_limit.setPlaceholderText("256MB, 1GB, 2.5GB など")
        cache_layout.addRow(self._form_label("cache_memory_limit"), self.cache_memory_limit)
        self._apply_setting_tip("cache_memory_limit", self.cache_memory_limit)
        
        # キャッシュサイズの説明
        cache_description = QLabel(get_text("settings.cache_memory_limit_description"))
        cache_description.setStyleSheet("color: #666; font-size: 10px;")
        cache_description.setWordWrap(True)
        self._apply_setting_tip("cache_memory_limit", cache_description)
        cache_layout.addRow(cache_description)
        
        # プリフェッチページ数
        self.cache_prefetch_pages = QSpinBox()
        self.cache_prefetch_pages.setMaximumWidth(100)
        self.cache_prefetch_pages.setRange(1, 50)
        self.cache_prefetch_pages.setValue(self.config.cache.get("prefetch_pages", 15))
        cache_layout.addRow(self._form_label("cache_prefetch_pages"), self.cache_prefetch_pages)
        self._apply_setting_tip("cache_prefetch_pages", self.cache_prefetch_pages)
        
        # プリフェッチページ数の説明
        prefetch_description = QLabel(get_text("settings.cache_prefetch_pages_description"))
        prefetch_description.setStyleSheet("color: #666; font-size: 10px;")
        prefetch_description.setWordWrap(True)
        self._apply_setting_tip("cache_prefetch_pages", prefetch_description)
        cache_layout.addRow(prefetch_description)
        
        # 大きな画像の最適化
        self.optimize_large_images_checkbox = QCheckBox(get_text("settings.optimize_large_images"))
        self.optimize_large_images_checkbox.setChecked(self.config.cache.get("optimize_large_images", True))
        self._apply_setting_tip("optimize_large_images", self.optimize_large_images_checkbox)
        cache_layout.addRow(self.optimize_large_images_checkbox)
        
        # 最適化閾値
        self.optimize_threshold = QLineEdit()
        self.optimize_threshold.setMaximumWidth(200)
        self.optimize_threshold.setText(self.config.cache.get("optimize_threshold", "50MB"))
        self.optimize_threshold.setPlaceholderText("50MB, 100MB など")
        cache_layout.addRow(self._form_label("optimize_threshold"), self.optimize_threshold)
        self._apply_setting_tip("optimize_threshold", self.optimize_threshold)
        
        # 最適化閾値の説明
        optimize_threshold_description = QLabel(get_text("settings.optimize_threshold_description"))
        optimize_threshold_description.setStyleSheet("color: #666; font-size: 10px;")
        optimize_threshold_description.setWordWrap(True)
        self._apply_setting_tip("optimize_threshold", optimize_threshold_description)
        cache_layout.addRow(optimize_threshold_description)
        
        # 最大解像度
        self.optimize_max_resolution = QSpinBox()
        self.optimize_max_resolution.setMaximumWidth(100)
        self.optimize_max_resolution.setRange(1000, 10000)
        self.optimize_max_resolution.setValue(self.config.cache.get("optimize_max_resolution", 4000))
        cache_layout.addRow(self._form_label("optimize_max_resolution"), self.optimize_max_resolution)
        self._apply_setting_tip("optimize_max_resolution", self.optimize_max_resolution)
        
        # 最大解像度の説明
        optimize_max_resolution_description = QLabel(get_text("settings.optimize_max_resolution_description"))
        optimize_max_resolution_description.setStyleSheet("color: #666; font-size: 10px;")
        optimize_max_resolution_description.setWordWrap(True)
        self._apply_setting_tip("optimize_max_resolution", optimize_max_resolution_description)
        cache_layout.addRow(optimize_max_resolution_description)
        
        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)
        
        layout.addStretch()
        behavior_widget.setLayout(layout)
        
        self.tab_widget.addTab(scroll_area, get_text("settings.tab_behavior"))

    def create_development_tab(self):
        """開発タブを作成"""
        development_widget = QWidget()
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(development_widget)
        
        layout = QVBoxLayout()
        
        # デバッグ設定
        debug_group = QGroupBox(get_text("settings.debug_settings"))
        debug_layout = QFormLayout()
        
        # デバッグモード
        self.debug_mode_checkbox = QCheckBox(get_text("settings.debug_mode"))
        self.debug_mode_checkbox.setChecked(self.config.debug.get("enabled", False))
        self._apply_setting_tip("debug_mode", self.debug_mode_checkbox)
        debug_layout.addRow(self.debug_mode_checkbox)
        
        # デバッグモードの説明
        debug_description = QLabel(get_text("settings.debug_mode_description"))
        debug_description.setStyleSheet("color: #666; font-size: 10px;")
        self._apply_setting_tip("debug_mode", debug_description)
        debug_layout.addRow(debug_description)
        
        # ファイルハンドル管理設定
        self.keep_archive_handles_checkbox = QCheckBox(get_text("settings.keep_archive_handles"))
        self.keep_archive_handles_checkbox.setChecked(self.config.debug.get("keep_archive_handles", False))
        self._apply_setting_tip("keep_archive_handles", self.keep_archive_handles_checkbox)
        debug_layout.addRow(self.keep_archive_handles_checkbox)
        
        # ファイルハンドル管理の警告説明
        handle_warning = QLabel(get_text("settings.keep_archive_handles_description"))
        handle_warning.setStyleSheet("color: #d63031; font-size: 10px; font-weight: bold;")
        handle_warning.setWordWrap(True)
        self._apply_setting_tip("keep_archive_handles", handle_warning)
        debug_layout.addRow(handle_warning)
        
        # アーカイブメタデータキャッシュ設定
        self.cache_archive_metadata_checkbox = QCheckBox(get_text("settings.cache_archive_metadata"))
        self.cache_archive_metadata_checkbox.setChecked(self.config.debug.get("cache_archive_metadata", True))
        self._apply_setting_tip("cache_archive_metadata", self.cache_archive_metadata_checkbox)
        debug_layout.addRow(self.cache_archive_metadata_checkbox)
        
        # アーカイブメタデータキャッシュの説明
        metadata_description = QLabel(get_text("settings.cache_archive_metadata_description"))
        metadata_description.setStyleSheet("color: #666; font-size: 10px;")
        metadata_description.setWordWrap(True)
        self._apply_setting_tip("cache_archive_metadata", metadata_description)
        debug_layout.addRow(metadata_description)

        self.show_error_log_checkbox = QCheckBox(get_text("settings.show_error_log"))
        self.show_error_log_checkbox.setChecked(self.config.debug.get("show_error_log", False))
        self._apply_setting_tip("show_error_log", self.show_error_log_checkbox)
        debug_layout.addRow(self.show_error_log_checkbox)

        error_log_description = QLabel(get_text("settings.show_error_log_description"))
        error_log_description.setStyleSheet("color: #666; font-size: 10px;")
        error_log_description.setWordWrap(True)
        self._apply_setting_tip("show_error_log", error_log_description)
        debug_layout.addRow(error_log_description)
        
        debug_group.setLayout(debug_layout)
        layout.addWidget(debug_group)
        
        layout.addStretch()
        development_widget.setLayout(layout)
        
        self.tab_widget.addTab(scroll_area, get_text("settings.tab_development"))

    def select_background_color(self):
        """背景色を選択"""
        color = QColorDialog.getColor(
            QColor(self.config.viewer["background_color"]),
            self,
            get_text("settings.select_background_color")
        )
        if color.isValid():
            self.config.viewer["background_color"] = color.name()
            self.bg_color_button.setStyleSheet(
                f"background-color: {color.name()};"
                "min-width: 100px; max-width: 150px; min-height: 20px;"
            )
    def select_ui_font_color(self):
        color = QColorDialog.getColor(QColor(self.config.ui_font.get("font_color", "#0000ff")), self, get_text("settings.select_font_color"))
        if color.isValid():
            rgb = color.name()
            self.ui_font_color_btn.setStyleSheet(f"background-color: {rgb}; min-width: 100px; max-width: 150px; min-height: 20px;")
    def select_ui_bg_color(self):
        color = QColorDialog.getColor(QColor(self.config.ui_font.get("bg_color", "#ffffff")), self, get_text("settings.select_background_color"))
        if color.isValid():
            rgb = color.name()
            self.ui_bg_color_btn.setStyleSheet(f"background-color: {rgb}; min-width: 100px; max-width: 150px; min-height: 20px;")
    def on_sensitivity_slider_changed(self, value):
        """スライダーの値が変更された時の処理"""
        # 無限ループを防ぐため、一時的にシグナルを切断
        self.sensitivity_input.blockSignals(True)
        self.sensitivity_input.setText(f"{value / 10:.1f}")
        self.sensitivity_input.blockSignals(False)
    def on_sensitivity_input_changed(self, text):
        """テキストボックスの値が変更された時の処理"""
        # 無限ループを防ぐため、一時的にシグナルを切断
        self.sensitivity_slider.blockSignals(True)
        try:
            value = float(text)
            self.sensitivity_slider.setValue(int(value * 10))
        except ValueError:
            pass
        self.sensitivity_slider.blockSignals(False)
    def on_sensitivity_input_finished(self):
        """テキストボックスの編集が終了した時の処理"""
        try:
            value = float(self.sensitivity_input.text())
            # 範囲チェック（0.5～4.0）
            if value < 0.5 or value > 4.0:
                # 範囲外の場合はデフォルト値（2.0）に戻す
                value = 2.0
                self.sensitivity_input.setText(f"{value:.1f}")
            # スライダーを更新
            self.sensitivity_slider.blockSignals(True)
            self.sensitivity_slider.setValue(int(value * 10))
            self.sensitivity_slider.blockSignals(False)
        except ValueError:
            # 数値でない場合はデフォルト値（2.0）に戻す
            self.sensitivity_input.setText("2.0")
            self.sensitivity_slider.blockSignals(True)
            self.sensitivity_slider.setValue(20)  # 2.0 * 10
            self.sensitivity_slider.blockSignals(False)

    def on_gesture_threshold_slider_changed(self, value):
        """ジェスチャー判定距離スライダーの値が変更された時の処理"""
        # 無限ループを防ぐため、一時的にシグナルを切断
        self.gesture_threshold_input.blockSignals(True)
        self.gesture_threshold_input.setText(str(value))
        self.gesture_threshold_input.blockSignals(False)

    def on_gesture_threshold_input_changed(self, text):
        """ジェスチャー判定距離テキストボックスの値が変更された時の処理"""
        # 無限ループを防ぐため、一時的にシグナルを切断
        self.gesture_threshold_slider.blockSignals(True)
        try:
            value = int(text)
            self.gesture_threshold_slider.setValue(value)
        except ValueError:
            pass
        self.gesture_threshold_slider.blockSignals(False)

    def on_gesture_threshold_input_finished(self):
        """ジェスチャー判定距離テキストボックスの編集が終了した時の処理"""
        try:
            value = int(self.gesture_threshold_input.text())
            # 範囲チェック（20～60）
            if value < 20 or value > 60:
                # 範囲外の場合はデフォルト値（30）に戻す
                value = 30
                self.gesture_threshold_input.setText(str(value))
            # スライダーを更新
            self.gesture_threshold_slider.blockSignals(True)
            self.gesture_threshold_slider.setValue(value)
            self.gesture_threshold_slider.blockSignals(False)
        except ValueError:
            # 数値でない場合はデフォルト値（30）に戻す
            self.gesture_threshold_input.setText("50")
            self.gesture_threshold_slider.blockSignals(True)
            self.gesture_threshold_slider.setValue(50)
            self.gesture_threshold_slider.blockSignals(False)

    def on_mouse_repeat_initial_delay_slider_changed(self, value):
        """マウスリピート初期間隔スライダーの値が変更された時の処理"""
        self.mouse_repeat_initial_delay_input.blockSignals(True)
        self.mouse_repeat_initial_delay_input.setText(str(value))
        self.mouse_repeat_initial_delay_input.blockSignals(False)

    def on_mouse_repeat_initial_delay_input_changed(self, text):
        """マウスリピート初期間隔テキストボックスの値が変更された時の処理"""
        self.mouse_repeat_initial_delay_slider.blockSignals(True)
        try:
            value = int(text)
            self.mouse_repeat_initial_delay_slider.setValue(value)
        except ValueError:
            pass
        self.mouse_repeat_initial_delay_slider.blockSignals(False)

    def on_mouse_repeat_initial_delay_input_finished(self):
        """マウスリピート初期間隔テキストボックスの編集が終了した時の処理"""
        try:
            value = int(self.mouse_repeat_initial_delay_input.text())
            if value < 50 or value > 500:
                value = 100
                self.mouse_repeat_initial_delay_input.setText(str(value))
            self.mouse_repeat_initial_delay_slider.blockSignals(True)
            self.mouse_repeat_initial_delay_slider.setValue(value)
            self.mouse_repeat_initial_delay_slider.blockSignals(False)
        except ValueError:
            self.mouse_repeat_initial_delay_input.setText("100")
            self.mouse_repeat_initial_delay_slider.blockSignals(True)
            self.mouse_repeat_initial_delay_slider.setValue(100)
            self.mouse_repeat_initial_delay_slider.blockSignals(False)

    def on_mouse_repeat_acceleration_start_slider_changed(self, value):
        """マウスリピート加速開始時刻スライダーの値が変更された時の処理"""
        self.mouse_repeat_acceleration_start_input.blockSignals(True)
        self.mouse_repeat_acceleration_start_input.setText(str(value))
        self.mouse_repeat_acceleration_start_input.blockSignals(False)

    def on_mouse_repeat_acceleration_start_input_changed(self, text):
        """マウスリピート加速開始時刻テキストボックスの値が変更された時の処理"""
        self.mouse_repeat_acceleration_start_slider.blockSignals(True)
        try:
            value = int(text)
            self.mouse_repeat_acceleration_start_slider.setValue(value)
        except ValueError:
            pass
        self.mouse_repeat_acceleration_start_slider.blockSignals(False)

    def on_mouse_repeat_acceleration_start_input_finished(self):
        """マウスリピート加速開始時刻テキストボックスの編集が終了した時の処理"""
        try:
            value = int(self.mouse_repeat_acceleration_start_input.text())
            if value < 50 or value > 500:
                value = 100
                self.mouse_repeat_acceleration_start_input.setText(str(value))
            self.mouse_repeat_acceleration_start_slider.blockSignals(True)
            self.mouse_repeat_acceleration_start_slider.setValue(value)
            self.mouse_repeat_acceleration_start_slider.blockSignals(False)
        except ValueError:
            self.mouse_repeat_acceleration_start_input.setText("100")
            self.mouse_repeat_acceleration_start_slider.blockSignals(True)
            self.mouse_repeat_acceleration_start_slider.setValue(100)
            self.mouse_repeat_acceleration_start_slider.blockSignals(False)

    def on_mouse_repeat_min_interval_slider_changed(self, value):
        """マウスリピート最小間隔スライダーの値が変更された時の処理"""
        self.mouse_repeat_min_interval_input.blockSignals(True)
        self.mouse_repeat_min_interval_input.setText(str(value))
        self.mouse_repeat_min_interval_input.blockSignals(False)

    def on_mouse_repeat_min_interval_input_changed(self, text):
        """マウスリピート最小間隔テキストボックスの値が変更された時の処理"""
        self.mouse_repeat_min_interval_slider.blockSignals(True)
        try:
            value = int(text)
            self.mouse_repeat_min_interval_slider.setValue(value)
        except ValueError:
            pass
        self.mouse_repeat_min_interval_slider.blockSignals(False)

    def on_mouse_repeat_min_interval_input_finished(self):
        """マウスリピート最小間隔テキストボックスの編集が終了した時の処理"""
        try:
            value = int(self.mouse_repeat_min_interval_input.text())
            if value < 10 or value > 100:
                value = 30
                self.mouse_repeat_min_interval_input.setText(str(value))
            self.mouse_repeat_min_interval_slider.blockSignals(True)
            self.mouse_repeat_min_interval_slider.setValue(value)
            self.mouse_repeat_min_interval_slider.blockSignals(False)
        except ValueError:
            self.mouse_repeat_min_interval_input.setText("30")
            self.mouse_repeat_min_interval_slider.blockSignals(True)
            self.mouse_repeat_min_interval_slider.setValue(30)
            self.mouse_repeat_min_interval_slider.blockSignals(False)

    def update_font_variants(self):
        """選択されたフォントファミリーのバリアントを更新"""
        # 編集可能コンボボックスからテキストを取得
        current_family = self.ui_font_family.currentText()
        if not current_family:
            current_family = self.ui_font_family.lineEdit().text() if self.ui_font_family.lineEdit() else ""
        
        if not current_family:
            return
        
        # バリアント一覧を取得
        variants = FontFamilyManager.get_font_family_variants(current_family)
        
        # コンボボックスを更新
        self.ui_font_variant.blockSignals(True)
        self.ui_font_variant.clear()
        self.ui_font_variant.addItems(variants)
        
        # バリアント用コンプリーター設定
        if not hasattr(self, 'font_variant_completer'):
            self.font_variant_completer = QCompleter(variants)
            self.font_variant_completer.setCaseSensitivity(Qt.CaseInsensitive)
            self.font_variant_completer.setFilterMode(Qt.MatchContains)
            self.ui_font_variant.setCompleter(self.font_variant_completer)
        else:
            # コンプリーターのモデルを更新
            self.font_variant_completer.model().setStringList(variants)
        
        # プレースホルダーテキストを設定
        if self.ui_font_variant.lineEdit():
            self.ui_font_variant.lineEdit().setPlaceholderText(get_text("settings.font_style_placeholder"))
        
        # デフォルトで最初のバリアント（通常はRegular）を選択
        if variants:
            self.ui_font_variant.setEditText(variants[0])
        
        self.ui_font_variant.blockSignals(False)

    def reset_settings(self):
        """設定を初期化する"""
        reply = QMessageBox.question(
            self,
            get_text("settings.reset_settings_title"),
            get_text("settings.reset_settings_confirm"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # デフォルト設定を取得
            default_config = Config.get_default_config()
            
            # 各UI要素をデフォルト値で更新
            self._update_ui_with_config(default_config)
            
            # 初期化完了を通知
            QMessageBox.information(
                self,
                get_text("dialogs.information"),
                get_text("settings.reset_settings_completed")
            )

    def _update_ui_with_config(self, config_dict):
        """設定辞書の値でUIを更新"""
        # 言語設定
        if "language" in config_dict:
            language_code = config_dict["language"].get("code", "system")
            for i in range(self.language_combo.count()):
                if self.language_combo.itemData(i) == language_code:
                    self.language_combo.setCurrentIndex(i)
                    break

        # ウィンドウ設定
        if "window" in config_dict:
            self.auto_resize_checkbox.setChecked(config_dict["window"].get("auto_resize", True))
            self.save_window_state_checkbox.setChecked(config_dict["window"].get("save_window_state", True))
            self.maximize_on_startup_checkbox.setChecked(config_dict["window"].get("maximize_on_startup", False))

        # ビューア設定
        if "viewer" in config_dict:
            # 背景色
            bg_color = config_dict["viewer"].get("background_color", "#2b2b2b")
            self.bg_color_button.setStyleSheet(
                f"background-color: {bg_color};"
                "min-width: 100px; max-width: 150px; min-height: 20px;"
            )
            
            # その他のビューア設定
            self.fit_to_window_checkbox.setChecked(config_dict["viewer"].get("fit_to_window", True))
            self.fit_to_window_min_checkbox.setChecked(config_dict["viewer"].get("fit_to_window_minimum", True))
            self.spread_selected_as_axis_checkbox.setChecked(
                config_dict["viewer"].get(
                    "spread_selected_as_axis",
                    config_dict["viewer"].get("spread_cover_single", False),
                )
            )
            spread_pref = config_dict["viewer"].get("spread_toggle_preference", "keep_previous")
            pref_index = self.spread_toggle_preference_combo.findData(spread_pref)
            self.spread_toggle_preference_combo.setCurrentIndex(pref_index if pref_index >= 0 else 0)
            
            # 画像移動感度
            sensitivity = config_dict["viewer"].get("image_move_sensitivity", 2.0)
            self.sensitivity_input.setText(f"{sensitivity:.1f}")
            self.sensitivity_slider.setValue(int(sensitivity * 10))
            
            # ジェスチャー判定距離
            gesture_threshold = config_dict["viewer"].get("gesture_threshold", 50)
            self.gesture_threshold_input.setText(str(gesture_threshold))
            self.gesture_threshold_slider.setValue(gesture_threshold)
            
            # マウスリピート設定
            mouse_repeat_initial_delay = config_dict["viewer"].get("mouse_repeat_initial_delay", 100)
            self.mouse_repeat_initial_delay_input.setText(str(mouse_repeat_initial_delay))
            self.mouse_repeat_initial_delay_slider.setValue(mouse_repeat_initial_delay)
            
            mouse_repeat_acceleration_start = config_dict["viewer"].get("mouse_repeat_acceleration_start", 100)
            self.mouse_repeat_acceleration_start_input.setText(str(mouse_repeat_acceleration_start))
            self.mouse_repeat_acceleration_start_slider.setValue(mouse_repeat_acceleration_start)
            
            mouse_repeat_min_interval = config_dict["viewer"].get("mouse_repeat_min_interval", 30)
            self.mouse_repeat_min_interval_input.setText(str(mouse_repeat_min_interval))
            self.mouse_repeat_min_interval_slider.setValue(mouse_repeat_min_interval)

        # 履歴設定
        if "history" in config_dict:
            self.history_max_count_spin.setValue(config_dict["history"].get("max_count", 20))
            self.restore_page_checkbox.setChecked(config_dict["history"].get("restore_page_on_reopen", False))
            self.open_last_file_checkbox.setChecked(config_dict["history"].get("open_last_file_on_startup", False))

        if "viewer" in config_dict and hasattr(self, "drop_opens_combo"):
            drop_index = 1 if config_dict["viewer"].get("drop_opens_new_tab", False) else 0
            self.drop_opens_combo.setCurrentIndex(drop_index)
            if hasattr(self, "open_archives_own_tab_checkbox"):
                self.open_archives_own_tab_checkbox.setChecked(
                    config_dict["viewer"].get("open_archives_in_own_tab", True)
                )
            if hasattr(self, "open_folders_own_tab_checkbox"):
                self.open_folders_own_tab_checkbox.setChecked(
                    config_dict["viewer"].get("open_folders_in_own_tab", False)
                )

        # デバッグ設定
        if "debug" in config_dict:
            self.debug_mode_checkbox.setChecked(config_dict["debug"].get("enabled", False))
            self.keep_archive_handles_checkbox.setChecked(config_dict["debug"].get("keep_archive_handles", False))
            self.cache_archive_metadata_checkbox.setChecked(config_dict["debug"].get("cache_archive_metadata", True))
            self.show_error_log_checkbox.setChecked(config_dict["debug"].get("show_error_log", False))
        
        # キャッシュ設定
        if "cache" in config_dict:
            self.cache_memory_limit.setText(config_dict["cache"].get("memory_limit", "256MB"))
            self.cache_prefetch_pages.setValue(config_dict["cache"].get("prefetch_pages", 15))
            if hasattr(self, 'optimize_large_images_checkbox'):
                self.optimize_large_images_checkbox.setChecked(config_dict["cache"].get("optimize_large_images", True))
            if hasattr(self, 'optimize_threshold'):
                self.optimize_threshold.setText(config_dict["cache"].get("optimize_threshold", "50MB"))
            if hasattr(self, 'optimize_max_resolution'):
                self.optimize_max_resolution.setValue(config_dict["cache"].get("optimize_max_resolution", 4000))
            self.optimize_large_images_checkbox.setChecked(config_dict["cache"].get("optimize_large_images", True))
            self.optimize_threshold.setText(config_dict["cache"].get("optimize_threshold", "50MB"))
            self.optimize_max_resolution.setValue(config_dict["cache"].get("optimize_max_resolution", 4000))

        # UIフォント設定
        # 選択されたバリアントを使用（バリアントが選択されていない場合はファミリー名）
        selected_variant = self.ui_font_variant.currentText()
        if not selected_variant and self.ui_font_variant.lineEdit():
            selected_variant = self.ui_font_variant.lineEdit().text()
        
        if selected_variant:
            self.config.ui_font["font_family"] = selected_variant
        else:
            selected_family = self.ui_font_family.currentText()
            if not selected_family and self.ui_font_family.lineEdit():
                selected_family = self.ui_font_family.lineEdit().text()
            self.config.ui_font["font_family"] = selected_family
        
        self.config.ui_font["font_size"] = self.ui_font_size.value()
        self.config.ui_font["font_color"] = self.ui_font_color_btn.palette().button().color().name()
        self.config.ui_font["bg_color"] = self.ui_bg_color_btn.palette().button().color().name()
        self.config.ui_font["alpha"] = self.ui_alpha.value()



        # フォントが変更された場合、アプリケーション全体のフォントを更新
        if font_changed:
            try:
                from PySide6.QtWidgets import QApplication
                from PySide6.QtGui import QFont
                app = QApplication.instance()
                if app:
                    font_family = self.config.ui_font["font_family"]
                    font_size = self.config.ui_font["font_size"]
                    app_font = QFont(font_family, font_size)
                    app.setFont(app_font)
                    # 親ウィンドウ（メインウィンドウ）のフォントも更新
                    if self.parent():
                        self.parent().setFont(app_font)
            except Exception as e:
                logger.error(get_log_text("settings_dialog_font_update_error", error=e))

        # 言語が変更された場合、即座に言語を切り替えてメニューを再構築
        if language_changed:
            set_language(selected_language)
            parent = self.parent()
            if parent is not None and hasattr(parent, "refresh_plugin_language"):
                parent.refresh_plugin_language()
            if hasattr(self.parent(), 'rebuild_menu'):
                self.parent().rebuild_menu()

        # デバッグモードが有効になった場合、ログファイル作成の旨をダイアログで通知
        debug_enabled = self.debug_mode_checkbox.isChecked()
        if debug_enabled and not self.config.debug.get("enabled", False):
            QMessageBox.information(
                self,
                get_text("dialogs.information"),
                get_text("settings.debug_log_enabled")
            )

    def apply_settings(self):
        """設定を適用"""
        return self._save_settings()

    def accept(self):
        """OKボタンが押された時の処理"""
        if self.apply_settings() is False:
            return
        super().accept()

    def export_config(self):
        path, _ = QFileDialog.getSaveFileName(self, get_text("ui.export"), "config_export.yaml", get_log_text("settings_dialog_yaml_file_filter"))
        if path:
            export_data = Config.strip_profile_section(self.config.to_dict())
            with open(path, "w", encoding="utf-8") as f:
                yaml.dump(export_data, f, allow_unicode=True)
            QMessageBox.information(self, get_text("dialogs.information"), get_log_text("settings_dialog_config_saved", path=path))
    def import_config(self):
        path, _ = QFileDialog.getOpenFileName(self, get_text("ui.import"), "", get_log_text("settings_dialog_yaml_file_filter"))
        if path:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            data = Config.strip_profile_section(data or {})
            # デフォルト設定と比較して不足項目をチェック
            default_config = Config.get_default_config()
            original_data = data.copy() if data else {}
            # 不足項目を追加
            merged_data = Config.merge_with_defaults(data or {})
            # 追加された項目があるかチェック
            added_items = []
            for section_name, default_section in default_config.items():
                if section_name not in original_data:
                    added_items.append(get_log_text("settings_dialog_section_added", section_name=section_name))
                elif isinstance(default_section, dict) and isinstance(original_data.get(section_name), dict):
                    for key, value in default_section.items():
                        if key not in original_data[section_name]:
                            added_items.append(get_log_text("settings_dialog_key_added", section_name=section_name, config_key=key))
            # 不足項目がある場合はユーザーに通知
            if added_items:
                message = get_log_text("settings_dialog_missing_items_added", items=", ".join(added_items))
                QMessageBox.information(self, get_text("dialogs.information"), message)
            reply = QMessageBox.question(self, get_text("dialogs.question"), get_log_text("settings_dialog_overwrite_confirm"), QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.config.apply_dict(merged_data)
                self._update_ui_with_config(self.config.to_dict())
                if hasattr(self.parent(), 'save_config'):
                    self.parent().save_config()
                if hasattr(self.parent(), 'apply_loaded_profile_config'):
                    self.parent().apply_loaded_profile_config()
                QMessageBox.information(self, get_text("dialogs.information"), get_log_text("settings_dialog_config_imported"))

    def _save_settings(self):
        """設定を保存する共通処理"""
        location = self._current_location_settings()
        if location["data_location"] == LOCATION_CUSTOM and not location["custom_path"]:
            QMessageBox.warning(
                self,
                get_text("dialogs.warning"),
                get_text("settings.data_location_custom_required"),
            )
            return False
        target = resolve_data_root(location)
        if not is_writable_dir(target):
            QMessageBox.warning(
                self,
                get_text("dialogs.warning"),
                get_text("settings.data_location_not_writable"),
            )
        save_location_settings(location)

        # 言語設定
        selected_language = self.language_combo.currentData()
        language_changed = False
        if selected_language and selected_language != self.config.language.get("code", "system"):
            self.config.language["code"] = selected_language
            language_changed = True

        # UIフォント設定の変更検知
        font_changed = False
        if (
            self.config.ui_font["font_family"] != self.ui_font_family.currentText() or
            self.config.ui_font["font_size"] != self.ui_font_size.value() or
            self.config.ui_font["font_color"] != self.ui_font_color_btn.palette().button().color().name() or
            self.config.ui_font["bg_color"] != self.ui_bg_color_btn.palette().button().color().name() or
            self.config.ui_font.get("alpha", 255) != self.ui_alpha.value()
        ):
            font_changed = True

        # ウィンドウ設定
        self.config.window["auto_resize"] = self.auto_resize_checkbox.isChecked()
        self.config.window["save_window_state"] = self.save_window_state_checkbox.isChecked()
        self.config.window["maximize_on_startup"] = self.maximize_on_startup_checkbox.isChecked()

        # ビューア設定
        self.config.viewer["fit_to_window"] = self.fit_to_window_checkbox.isChecked()
        self.config.viewer["fit_to_window_minimum"] = self.fit_to_window_min_checkbox.isChecked()
        self.config.viewer["spread_selected_as_axis"] = self.spread_selected_as_axis_checkbox.isChecked()
        spread_pref = self.spread_toggle_preference_combo.currentData()
        if spread_pref not in ("keep_previous", "prefer_right", "prefer_left"):
            spread_pref = "keep_previous"
        self.config.viewer["spread_toggle_preference"] = spread_pref
        self.config.viewer["drop_opens_new_tab"] = bool(self.drop_opens_combo.currentData())
        self.config.viewer["open_archives_in_own_tab"] = self.open_archives_own_tab_checkbox.isChecked()
        self.config.viewer["open_folders_in_own_tab"] = self.open_folders_own_tab_checkbox.isChecked()
        try:
            sensitivity_value = float(self.sensitivity_input.text())
            # 範囲チェック
            if sensitivity_value < 0.5 or sensitivity_value > 4.0:
                sensitivity_value = 2.0
            self.config.viewer["image_move_sensitivity"] = sensitivity_value
        except ValueError:
            self.config.viewer["image_move_sensitivity"] = 2.0

        # ジェスチャー判定距離設定
        try:
            gesture_threshold_value = int(self.gesture_threshold_input.text())
            # 範囲チェック
            if gesture_threshold_value < 20 or gesture_threshold_value > 100:
                gesture_threshold_value = 50
            self.config.viewer["gesture_threshold"] = gesture_threshold_value
        except ValueError:
            self.config.viewer["gesture_threshold"] = 50
        
        # マウスリピート設定
        try:
            mouse_repeat_initial_delay_value = int(self.mouse_repeat_initial_delay_input.text())
            if mouse_repeat_initial_delay_value < 50 or mouse_repeat_initial_delay_value > 500:
                mouse_repeat_initial_delay_value = 100
            self.config.viewer["mouse_repeat_initial_delay"] = mouse_repeat_initial_delay_value
        except ValueError:
            self.config.viewer["mouse_repeat_initial_delay"] = 100
        
        try:
            mouse_repeat_acceleration_start_value = int(self.mouse_repeat_acceleration_start_input.text())
            if mouse_repeat_acceleration_start_value < 50 or mouse_repeat_acceleration_start_value > 500:
                mouse_repeat_acceleration_start_value = 100
            self.config.viewer["mouse_repeat_acceleration_start"] = mouse_repeat_acceleration_start_value
        except ValueError:
            self.config.viewer["mouse_repeat_acceleration_start"] = 100
        
        try:
            mouse_repeat_min_interval_value = int(self.mouse_repeat_min_interval_input.text())
            if mouse_repeat_min_interval_value < 10 or mouse_repeat_min_interval_value > 100:
                mouse_repeat_min_interval_value = 30
            self.config.viewer["mouse_repeat_min_interval"] = mouse_repeat_min_interval_value
        except ValueError:
            self.config.viewer["mouse_repeat_min_interval"] = 30

        # 履歴設定
        self.config.history["max_count"] = self.history_max_count_spin.value()
        self.config.history["restore_page_on_reopen"] = self.restore_page_checkbox.isChecked()
        self.config.history["open_last_file_on_startup"] = self.open_last_file_checkbox.isChecked()

        # デバッグ設定
        self.config.debug["enabled"] = self.debug_mode_checkbox.isChecked()
        self.config.debug["keep_archive_handles"] = self.keep_archive_handles_checkbox.isChecked()
        self.config.debug["cache_archive_metadata"] = self.cache_archive_metadata_checkbox.isChecked()
        self.config.debug["show_error_log"] = self.show_error_log_checkbox.isChecked()
        
        # キャッシュ設定
        # キャッシュサイズの入力値を検証
        cache_memory_limit_text = self.cache_memory_limit.text().strip()
        try:
            # humanfriendlyでパースして有効性をチェック
            humanfriendly.parse_size(cache_memory_limit_text)
            self.config.cache["memory_limit"] = cache_memory_limit_text
        except ValueError:
            # 無効な場合はデフォルト値に戻す
            self.config.cache["memory_limit"] = "256MB"
            self.cache_memory_limit.setText("256MB")
            QMessageBox.warning(
                self,
                get_text("dialogs.warning"),
                get_text("settings.invalid_cache_size_warning")
            )
        
        self.config.cache["prefetch_pages"] = self.cache_prefetch_pages.value()
        
        # 画像最適化設定
        self.config.cache["optimize_large_images"] = self.optimize_large_images_checkbox.isChecked()
        
        # 最適化閾値の検証
        optimize_threshold_text = self.optimize_threshold.text().strip()
        try:
            # humanfriendlyでパースして有効性をチェック
            humanfriendly.parse_size(optimize_threshold_text)
            self.config.cache["optimize_threshold"] = optimize_threshold_text
        except ValueError:
            # 無効な場合はデフォルト値に戻す
            self.config.cache["optimize_threshold"] = "50MB"
            self.optimize_threshold.setText("50MB")
            QMessageBox.warning(
                self,
                get_text("dialogs.warning"),
                get_text("settings.invalid_optimize_threshold_warning")
            )
        
        self.config.cache["optimize_max_resolution"] = self.optimize_max_resolution.value()

        # UIフォント設定
        # 選択されたバリアントを使用（バリアントが選択されていない場合はファミリー名）
        selected_variant = self.ui_font_variant.currentText()
        if not selected_variant and self.ui_font_variant.lineEdit():
            selected_variant = self.ui_font_variant.lineEdit().text()
        
        if selected_variant:
            self.config.ui_font["font_family"] = selected_variant
        else:
            selected_family = self.ui_font_family.currentText()
            if not selected_family and self.ui_font_family.lineEdit():
                selected_family = self.ui_font_family.lineEdit().text()
            self.config.ui_font["font_family"] = selected_family
        
        self.config.ui_font["font_size"] = self.ui_font_size.value()
        self.config.ui_font["font_color"] = self.ui_font_color_btn.palette().button().color().name()
        self.config.ui_font["bg_color"] = self.ui_bg_color_btn.palette().button().color().name()
        self.config.ui_font["alpha"] = self.ui_alpha.value()



        # フォントが変更された場合、アプリケーション全体のフォントを更新
        if font_changed:
            try:
                from PySide6.QtWidgets import QApplication
                from PySide6.QtGui import QFont
                app = QApplication.instance()
                if app:
                    font_family = self.config.ui_font["font_family"]
                    font_size = self.config.ui_font["font_size"]
                    app_font = QFont(font_family, font_size)
                    app.setFont(app_font)
                    # 親ウィンドウ（メインウィンドウ）のフォントも更新
                    if self.parent():
                        self.parent().setFont(app_font)
            except Exception as e:
                logger.error(get_log_text("settings_dialog_font_update_error", error=e))

        # 言語が変更された場合、即座に言語を切り替えてメニューを再構築
        if language_changed:
            set_language(selected_language)
            parent = self.parent()
            if parent is not None and hasattr(parent, "refresh_plugin_language"):
                parent.refresh_plugin_language()
            if hasattr(self.parent(), 'rebuild_menu'):
                self.parent().rebuild_menu()

        # デバッグモードが有効になった場合、ログファイル作成の旨をダイアログで通知
        debug_enabled = self.debug_mode_checkbox.isChecked()
        if debug_enabled and not self.config.debug.get("enabled", False):
            QMessageBox.information(
                self,
                get_text("dialogs.information"),
                get_text("settings.debug_log_enabled")
            )
        
        # 設定を保存（親ウィンドウのメソッドを使用）
        if hasattr(self.parent(), 'save_config'):
            self.parent().save_config()
        # 両開きの表紙単ページ設定を表示へ即反映
        parent = self.parent()
        if parent and hasattr(parent, 'update_image') and getattr(parent, 'file_handler', None):
            if hasattr(parent, '_clear_spread_force_single'):
                parent._clear_spread_force_single()
            if hasattr(parent, '_align_current_spread_index'):
                parent._align_current_spread_index()
            parent.update_image()
            if hasattr(parent, '_update_page_slider'):
                parent._update_page_slider()
        return True

    def reject(self):
        """Cancelボタンが押された時の処理"""
        super().reject()
 