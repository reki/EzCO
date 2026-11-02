"""分割中に、ショートカットとジェスチャーが効くタブを覚える。"""


class PaneFocus:
    """最後に操作したタブと、クリックやジェスチャーで選ぶタブ。"""

    def __init__(self):
        """操作対象をまだ無い状態にする。"""
        self.last = None

    def note(self, pane):
        """ショートカットとドックが追うタブを更新する。

        Args:
            pane: 最後に操作したタブ。無ければ None。

        Returns:
            覚えたタブ。
        """
        self.last = pane
        return pane

    def shortcut_target(self):
        """閉じるやページ送りが効くタブを返す。

        Returns:
            最後に操作したタブ。無ければ None。
        """
        return self.last

    def page_target(self):
        """ページ送りが効くタブを返す。

        Returns:
            最後に操作したタブ。無ければ None。
        """
        return self.last

    def dock_target(self):
        """ページスライダーなどが追うタブを返す。

        Returns:
            最後に操作したタブ。無ければ None。
        """
        return self.last

    def activate_tab(self, pane, visible):
        """タブの選択を、見えている面のフォーカスか差し替えにする。

        Args:
            pane: 選ばれたタブ。
            visible: 今見えているタブ。

        Returns:
            ("focus", タブ) か ("replace", 差し替える面, 新しいタブ)。
            見えている面が無く差し替えられないときは ("show", タブ)。
        """
        shown = set(visible)
        if pane in shown:
            self.note(pane)
            return ("focus", pane)
        slot = self.last if self.last in shown else next(iter(shown), None)
        self.note(pane)
        if slot is None:
            return ("show", pane)
        return ("replace", slot, pane)

    def gesture_target(self, hit, fallback):
        """ジェスチャーの開始位置から対象タブを決め、その後のショートカット対象にする。

        Args:
            hit: 開始位置のタブ。面にもタブにも当たらなければ None。
            fallback: 当たらないときに使う、最後に操作したタブ。

        Returns:
            このジェスチャーが効くタブ。
        """
        target = hit if hit is not None else fallback
        if target is not None:
            self.note(target)
        return target
