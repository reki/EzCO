class ErrorSetupPlugin:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host

    def setup(self):
        raise RuntimeError(self.get_text("setup_error"))
