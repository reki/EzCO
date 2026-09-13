from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget


class ErrorCallbackPlugin:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
        self.widget = None

    def setup(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        button = QPushButton(self.get_text("error_button"))
        button.clicked.connect(self._raise_error)
        layout.addWidget(button)
        layout.addStretch()
        self.widget = widget
        self.host.register_sidebar("error_callback", self.get_text("title"), widget)
        self.host.register_action("raise_error", self.get_text("error_button"), self._raise_error)

    def teardown(self):
        self.host.unregister_sidebar("error_callback")
        self.host.unregister_action("raise_error")
        self.widget = None

    def _raise_error(self):
        raise RuntimeError(self.get_text("callback_error"))
