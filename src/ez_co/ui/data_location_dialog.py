from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QRadioButton,
    QPushButton,
    QHBoxLayout,
    QButtonGroup,
)
from ez_co.utils.language_manager import get_text


def _note_style(warning: bool = False) -> str:
    """暗い背景でも読める補足／注意の色。"""
    if warning:
        return "margin-left: 1.4em; color: #c47d00;"
    return "margin-left: 1.4em; color: palette(window-text);"


class DataLocationDialog(QDialog):
    """初回起動でデータの置き場を選ぶ。"""

    CHOICE_USER_NEW = "user_new"
    CHOICE_USER_COPY = "user_copy"
    CHOICE_EXE = "exe"

    def __init__(self, has_exe_settings: bool, parent=None):
        super().__init__(parent)
        self._has_exe_settings = has_exe_settings
        self._choice = self.CHOICE_USER_NEW
        self.setWindowTitle(get_text("ui.data_location_title"))
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()
        message = QLabel(
            get_text("ui.data_location_found_message")
            if self._has_exe_settings
            else get_text("ui.data_location_first_message")
        )
        message.setWordWrap(True)
        layout.addWidget(message)

        self._group = QButtonGroup(self)
        if self._has_exe_settings:
            options = [
                (self.CHOICE_USER_NEW, "ui.data_location_discard", "ui.data_location_discard_desc", False),
                (self.CHOICE_USER_COPY, "ui.data_location_copy", "ui.data_location_copy_desc", False),
                (self.CHOICE_EXE, "ui.data_location_use_exe", "ui.data_location_use_exe_desc", True),
            ]
        else:
            options = [
                (self.CHOICE_USER_NEW, "ui.data_location_use_user", "ui.data_location_use_user_desc", False),
                (self.CHOICE_EXE, "ui.data_location_use_exe_new", "ui.data_location_use_exe_new_desc", True),
            ]

        for index, (value, title_key, desc_key, warn) in enumerate(options):
            radio = QRadioButton(get_text(title_key))
            radio.setProperty("choice", value)
            self._group.addButton(radio, index)
            if index == 0:
                radio.setChecked(True)
            layout.addWidget(radio)
            desc = QLabel(get_text(desc_key))
            desc.setWordWrap(True)
            desc.setStyleSheet(_note_style())
            layout.addWidget(desc)
            if warn:
                note = QLabel(get_text("ui.data_location_exe_warning"))
                note.setWordWrap(True)
                note.setStyleSheet(_note_style(warning=True))
                layout.addWidget(note)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton(get_text("ui.exit"))
        cancel_button.clicked.connect(self.reject)
        ok_button = QPushButton(get_text("ui.ok"))
        ok_button.clicked.connect(self.accept)
        ok_button.setDefault(True)
        buttons.addWidget(cancel_button)
        buttons.addWidget(ok_button)
        layout.addLayout(buttons)
        self.setLayout(layout)

    def choice(self) -> str:
        button = self._group.checkedButton()
        if button is not None:
            return button.property("choice") or self.CHOICE_USER_NEW
        return self.CHOICE_USER_NEW
