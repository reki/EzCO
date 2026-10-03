"""残っている config.yaml をどのプロファイルへ取り込むか選ぶダイアログ。"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit,
    QPushButton, QMessageBox
)
from ez_co.utils.language_manager import get_text
from ez_co.utils.database import get_default_profile_name


# コンボで新規プロファイル作成を表す、既存名と重ならない値。
NEW_PROFILE_SENTINEL = "__new_profile__"


class YamlImportDialog(QDialog):
    """残存する config.yaml をどのプロファイルへ取り込むかを選ぶダイアログ"""

    def __init__(self, profiles, parent=None):
        """候補のプロファイルでダイアログを組み立てる。

        Args:
            profiles: 既存のプロファイル名。無ければ空として扱う。
            parent: 親ウィジェット。
        """
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.yaml_import_title"))
        self._profiles = list(profiles or [])
        self._selected_profile = None
        self.setup_ui()

    def setup_ui(self):
        """説明、プロファイル選択、新規名の入力、ボタンを配置する。"""
        layout = QVBoxLayout()

        message = QLabel(get_text("ui.yaml_import_confirm"))
        message.setWordWrap(True)
        layout.addWidget(message)

        layout.addWidget(QLabel(get_text("ui.yaml_import_profile_label")))
        self.profile_combo = QComboBox()
        for name in self._profiles:
            self.profile_combo.addItem(name, name)
        self.profile_combo.addItem(get_text("ui.yaml_import_new_option"), NEW_PROFILE_SENTINEL)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        layout.addWidget(self.profile_combo)

        self.new_name_edit = QLineEdit()
        self.new_name_edit.setPlaceholderText(get_text("ui.enter_profile_name"))
        self.new_name_edit.setVisible(False)
        layout.addWidget(self.new_name_edit)

        buttons = QHBoxLayout()
        buttons.addStretch()
        yes_button = QPushButton(get_text("ui.ok"))
        no_button = QPushButton(get_text("ui.cancel"))
        yes_button.clicked.connect(self._accept_import)
        no_button.clicked.connect(self.reject)
        buttons.addWidget(yes_button)
        buttons.addWidget(no_button)
        layout.addLayout(buttons)

        self.setLayout(layout)
        self._on_profile_changed()

    def _on_profile_changed(self):
        """新規プロファイルのときだけ名前入力を出す。"""
        is_new = self.profile_combo.currentData() == NEW_PROFILE_SENTINEL
        self.new_name_edit.setVisible(is_new)

    def _accept_import(self):
        """選択を確定する。名前が空、または既存と重なる新規名は警告して閉じない。"""
        data = self.profile_combo.currentData()
        if data == NEW_PROFILE_SENTINEL:
            name = self.new_name_edit.text().strip()
            if not name:
                QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.profile_name_required"))
                return
            if name in self._profiles:
                QMessageBox.warning(self, get_text("dialogs.warning"), get_text("ui.profile_name_exists"))
                return
            self._selected_profile = name
            self._is_new = True
        else:
            self._selected_profile = data or get_default_profile_name()
            self._is_new = False
        self.accept()

    def selected_profile(self) -> str:
        """確定したプロファイル名を返す。

        Returns:
            確定した名前。未確定なら None。
        """
        return self._selected_profile

    def is_new_profile(self) -> bool:
        """新規プロファイルとして確定したかを返す。

        Returns:
            新規として確定したとき True。
        """
        return bool(getattr(self, "_is_new", False))
