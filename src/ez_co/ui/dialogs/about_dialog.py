"""本体のバージョン表示。"""
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QVBoxLayout

from ez_co.utils.app_info import load_app_info
from ez_co.utils.language_manager import get_text


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        info = load_app_info()
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
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
