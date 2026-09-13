"""プラグイン導入の知情同意。はい／いいえ。閉じる・Esc はいえと同じ。"""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from ez_co.utils.data_location import plugin_consent_markdown
from ez_co.utils.language_manager import get_text


class _ConsentBrowser(QTextBrowser):
    def loadResource(self, resource_type, name):
        url = QUrl(name) if not isinstance(name, QUrl) else name
        scheme = (url.scheme() or "").lower()
        if scheme in ("http", "https"):
            return None
        return super().loadResource(resource_type, name)


class PluginConsentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.plugin_consent_title"))
        self.setMinimumSize(480, 360)
        layout = QVBoxLayout(self)
        browser = _ConsentBrowser()
        browser.setOpenExternalLinks(False)
        browser.setOpenLinks(False)
        browser.anchorClicked.connect(self._open_link)
        browser.setMarkdown(plugin_consent_markdown() or "")
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No
        )
        yes_button = buttons.button(QDialogButtonBox.StandardButton.Yes)
        no_button = buttons.button(QDialogButtonBox.StandardButton.No)
        if yes_button is not None:
            yes_button.setText(get_text("ui.plugin_consent_yes"))
        if no_button is not None:
            no_button.setText(get_text("ui.plugin_consent_no"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _open_link(self, url: QUrl):
        scheme = (url.scheme() or "").lower()
        if scheme in ("http", "https"):
            QDesktopServices.openUrl(url)
