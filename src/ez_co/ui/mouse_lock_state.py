"""マウスロックの常時・全画面と、押下中の反転を一つの状態にまとめる。"""
class MouseLockState:
    """常時・全画面の理由と、押下中の反転状態を集約する。"""

    def __init__(self):
        """常時・全画面・押下中の集合を初期化する。"""
        self.persistent = False
        self.fullscreen = False
        self.held_sources = set()

    @property
    def temporary(self) -> bool:
        """押下中の反転が有効かを返す。

        Returns:
            押下元が1つ以上あるとき True。
        """
        return bool(self.held_sources)

    @property
    def locked(self) -> bool:
        """常時または全画面と、押下中の反転からロック中かを返す。

        Returns:
            常時または全画面と、押下中が異なるとき True。
        """
        return (self.persistent or self.fullscreen) != self.temporary

    def press(self, source: str) -> bool:
        """押下元を追加する。

        Args:
            source: 押下の識別子。空なら追加しない。

        Returns:
            追加前は押下中でなく、今回追加したとき True。
        """
        if not source:
            return False
        before = self.temporary
        self.held_sources.add(source)
        return not before

    def release(self, source: str) -> bool:
        """押下元を外す。

        Args:
            source: 外す押下の識別子。

        Returns:
            外す前は押下中で、外したあとに押下中でなくなったとき True。
        """
        before = self.temporary
        self.held_sources.discard(source)
        return before and not self.temporary

    def clear_temporary(self) -> bool:
        """押下中の集合を空にする。

        Returns:
            空にする前に押下中だったとき True。
        """
        before = self.temporary
        self.held_sources.clear()
        return before
