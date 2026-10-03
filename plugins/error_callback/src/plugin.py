"""ボタンとアクションから例外を出す確認用プラグイン。"""
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class ErrorCallbackPlugin:
    """ボタンとアクションで例外を出す確認用。"""

    def __init__(self):
        """root、get_text、host と、サイドバーの入れ物を空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None
        self.widget = None

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
        """例外を出すボタンとアクションをサイドバーへ登録する。"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        button = QPushButton(self.get_text("error_button"))
        button.clicked.connect(self._raise_error)
        layout.addWidget(button)
        layout.addStretch()
        self.widget = widget
        self.host.register_sidebar("error_callback", "{title}", widget)
        self.host.register_action("raise_error", "{error_button}", self._raise_error)

    def teardown(self):
        """サイドバーのウィジェットを捨てる。"""
        self.widget = None

    def _raise_error(self):
        """文言の例外を送出する。

        Raises:
            RuntimeError: 常に送出する。
        """
        raise RuntimeError(self.get_text("callback_error"))
