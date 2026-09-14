class ProbePlugin:
    def __init__(self, root, get_text, host):
        self.root = root

    def supported_formats(self):
        return [(".probe", "image")]

    def setup(self):
        return None
