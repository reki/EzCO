class MouseLockState:
    """常時・全画面の理由と、押下中の反転状態を集約する。"""

    def __init__(self):
        self.persistent = False
        self.fullscreen = False
        self.held_sources = set()

    @property
    def temporary(self) -> bool:
        return bool(self.held_sources)

    @property
    def locked(self) -> bool:
        return (self.persistent or self.fullscreen) != self.temporary

    def press(self, source: str) -> bool:
        if not source:
            return False
        before = self.temporary
        self.held_sources.add(source)
        return not before

    def release(self, source: str) -> bool:
        before = self.temporary
        self.held_sources.discard(source)
        return before and not self.temporary

    def clear_temporary(self) -> bool:
        before = self.temporary
        self.held_sources.clear()
        return before
