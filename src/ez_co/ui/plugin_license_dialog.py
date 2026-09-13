"""プラグインルートの LICENSE を読み取り専用で表示する。"""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from ez_co.utils.language_manager import get_text


class _LicenseBrowser(QTextBrowser):
    def loadResource(self, resource_type, name):
        url = QUrl(name) if not isinstance(name, QUrl) else name
        scheme = (url.scheme() or "").lower()
        if scheme in ("http", "https"):
            return None
        return super().loadResource(resource_type, name)


class PluginLicenseDialog(QDialog):
    def __init__(self, plugin_name: str, kind: str, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(get_text("ui.plugin_license_title").format(name=plugin_name or "-"))
        self.setMinimumSize(520, 420)
        layout = QVBoxLayout(self)
        browser = _LicenseBrowser()
        browser.setOpenExternalLinks(False)
        browser.setOpenLinks(False)
        browser.anchorClicked.connect(self._open_link)
        if kind == "markdown":
            browser.setMarkdown(text or "")
        else:
            browser.setPlainText(text or "")
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _open_link(self, url: QUrl):
        scheme = (url.scheme() or "").lower()
        if scheme in ("http", "https"):
            QDesktopServices.openUrl(url)
