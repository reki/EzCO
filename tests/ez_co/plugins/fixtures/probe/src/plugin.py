class ProbePlugin:
    def __init__(self):
        self.root = None

    def load(self, root, get_text, host):
        self.root = root

    def setup(self):
        return None
