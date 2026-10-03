"""setup で例外を出す確認用プラグイン。"""
class ErrorSetupPlugin:
    """setup で例外を出す確認用。"""

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
        """文言の例外を送出する。

        Raises:
            RuntimeError: 常に送出する。
        """
        raise RuntimeError(self.get_text("setup_error"))
