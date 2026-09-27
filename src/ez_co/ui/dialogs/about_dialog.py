"""本体のバージョン表示。"""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ez_co.utils.app_info import current_build_id, load_app_info, short_build_id
from ez_co.utils.language_manager import get_text


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        info = load_app_info()
        self._info = info
        self._build_id = current_build_id()
        self.setWindowTitle(get_text("ui.version"))
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        title = QLabel(info.get("name") or get_text("app_name"))
        font = QFont(title.font())
        font.setPointSize(max(font.pointSize() + 4, 14))
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        description = info.get("description") or ""
        if description:
            summary = QLabel(description)
            summary.setWordWrap(True)
            layout.addWidget(summary)
        form = QFormLayout()
        rows = (
            ("ui.version", info.get("version")),
            ("ui.about_author", info.get("author")),
            ("ui.about_years", info.get("years")),
            ("ui.about_license", info.get("license")),
        )
        for key, value in rows:
            if not value:
                continue
            form.addRow(QLabel(get_text(key)), QLabel(value))
        build_id = self._build_id
        if build_id:
            build_label = QLabel(short_build_id(build_id))
            build_label.setToolTip(build_id)
            build_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            form.addRow(QLabel(get_text("ui.about_hash")), build_label)
        homepage = info.get("homepage") or ""
        if homepage:
            link = QLabel(f'<a href="{homepage}">{homepage}</a>')
            link.setTextFormat(Qt.TextFormat.RichText)
            link.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            link.setOpenExternalLinks(False)
            link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
            form.addRow(QLabel(get_text("ui.about_homepage")), link)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        copy_button = QPushButton(get_text("ui.error_log_copy"))
        copy_button.clicked.connect(self.copy_to_clipboard)
        buttons.addButton(copy_button, QDialogButtonBox.ButtonRole.ActionRole)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def copy_text(self) -> str:
        """ダイアログに出している項目だけ。ビルド識別は64桁。"""
        lines = []
        name = self._info.get("name") or get_text("app_name")
        if name:
            lines.append(name)
        description = self._info.get("description") or ""
        if description:
            lines.append(description)
        rows = (
            ("ui.version", self._info.get("version")),
            ("ui.about_author", self._info.get("author")),
            ("ui.about_years", self._info.get("years")),
            ("ui.about_license", self._info.get("license")),
        )
        for key, value in rows:
            if value:
                lines.append(f"{get_text(key)}: {value}")
        if self._build_id:
            lines.append(f"{get_text('ui.about_hash')}: {self._build_id}")
        homepage = self._info.get("homepage") or ""
        if homepage:
            lines.append(f"{get_text('ui.about_homepage')}: {homepage}")
        return "\n".join(lines)

    def copy_to_clipboard(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.copy_text())
