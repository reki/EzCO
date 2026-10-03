"""未宣言のサイドバー登録を行う確認用プラグイン。"""
from PySide6.QtWidgets import QWidget


class ErrorRegisterPlugin:
    """未宣言のサイドバー登録を行う確認用。"""

    def __init__(self):
        """root、get_text、host の入れ物を空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None

    def load(self, root, get_text, host):
        """root、get_text、host を保持する。

        Args:
            root: プラグインルート。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
        self.root = root
        self.get_text = get_text
        self.host = host

    def setup(self):
        """未宣言のサイドバーを登録する。"""
        # manifest に sidebar も permissions.filter も書いていない。
        # 本体は PluginRegistrationDenied を出し、このプラグインは使わない。
        # プラグイン設定の状態は「失敗: 権限がない登録がありました」。
        self.host.register_sidebar("denied", "{title}", QWidget())
