from PySide6.QtWidgets import QWidget


class ErrorRegisterPlugin:
    def __init__(self):
        self.root = None
        self.get_text = None
        self.host = None

    def load(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host

    def setup(self):
        # manifest に sidebar も permissions.filter も書いていない。
        # 本体は PluginRegistrationDenied を出し、このプラグインは使わない。
        # プラグイン設定の状態は「失敗: 権限がない登録がありました」。
        self.host.register_sidebar("denied", self.get_text("title"), QWidget())
