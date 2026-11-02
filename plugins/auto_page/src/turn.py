"""タブごとの自動改ページで、次の1手と停止を決める。"""
import math

# この回は送らない。
WAIT = "wait"
# 次ページアクション。
NEXT = "next"
# 指定ページアクション。
GOTO = "goto"
# そのタブの自動送りを止める。
STOP = "stop"
# 動いていない。
IDLE = "idle"
# 改ページ間隔の下限（秒）。
INTERVAL_MIN = 0.1
# 改ページ間隔の上限（秒）。10分。
INTERVAL_MAX = 600.0
# 改ページ間隔の既定（秒）。
INTERVAL_DEFAULT = 1.0
# 改ページ間隔の刻み（秒）。小数第1位。
INTERVAL_STEP = 0.1


def interval_seconds(value) -> float:
    """間隔を、小数第1位の秒に収める。

    Args:
        value: 秒。数値でなければ既定。

    Returns:
        0.1 以上 600.0 以下の秒。
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        # 数値でなければ既定の 1.0 秒に戻す。
        number = INTERVAL_DEFAULT
    if math.isnan(number):
        number = INTERVAL_DEFAULT
    number = round(number, 1)
    return min(INTERVAL_MAX, max(INTERVAL_MIN, number))



def interval_wait_ms(seconds) -> int:
    """秒を、タイマーの待ちミリ秒にする。

    Args:
        seconds: 秒。

    Returns:
        待ちミリ秒。
    """
    return int(round(interval_seconds(seconds) * 1000))



def can_begin(total) -> bool:
    """ページが1枚でもあれば開始できる。

    Args:
        total: ページ数。

    Returns:
        1以上なら True。
    """
    try:
        count = int(total or 0)
    except (TypeError, ValueError):
        # ページ数が整数でなければ、開始できないものとして扱う。
        return False
    return count > 0



class TabState:
    """1タブの範囲、間隔、動作中。"""

    def __init__(self, page, total, document, interval, loop=True):
        """開始 1、終了はページ数、ループは渡した値、間隔は小数第1位の秒で置く。

        Args:
            page: いまのページ。
            total: ページ数。
            document: 開いているファイルまたはフォルダ。ページが変わっても同じ値。
            interval: 間隔（秒）。
            loop: ループの初期値。
        """
        self.start = 1
        self.end = max(int(total or 1), 1)
        self.loop = bool(loop)
        self.running = False
        self.page = int(page or 1)
        self.document = document
        self.hold = False
        self.interval = interval_seconds(interval)
        self.interval_custom = False
        self.loop_custom = False


class TurnBook:
    """開いているタブの送り方を持つ。"""

    def __init__(self):
        """タブ id から状態への対応を空で作る。"""
        self.tabs = {}

    def touch(self, tab_id, page, total, document, interval, loop=True):
        """タブが初めてなら状態を作り、あればそれを返す。

        Args:
            tab_id: タブ id。
            page: いまのページ。
            total: ページ数。
            document: 開いているファイルまたはフォルダ。
            interval: まだ欄を触っていないときの間隔（秒）。
            loop: まだチェックを触っていないときのループ。

        Returns:
            そのタブの状態。
        """
        state = self.tabs.get(tab_id)
        if state is None:
            state = TabState(page, total, document, interval, loop)
            self.tabs[tab_id] = state
        return state

    def apply_default_interval(self, seconds):
        """欄を触っていないタブの間隔を、設定の値へ揃える。

        Args:
            seconds: 設定の間隔（秒）。
        """
        value = interval_seconds(seconds)
        for state in self.tabs.values():
            if not state.interval_custom:
                state.interval = value

    def apply_default_loop(self, enabled):
        """チェックを触っていないタブのループを、設定の値へ揃える。

        Args:
            enabled: 設定のループ。オンのとき True。
        """
        value = bool(enabled)
        for state in self.tabs.values():
            if not state.loop_custom:
                state.loop = value

    def begin(self, tab_id, page, shown):
        """自動送りを開始し、範囲外で見えていればすぐ開始ページへ行く指示を返す。

        Args:
            tab_id: タブ id。
            page: 開始したときのページ。
            shown: 見えているとき True。

        Returns:
            ("goto", ページ) または ("wait", None)。
        """
        state = self.tabs[tab_id]
        state.running = True
        state.page = int(page or 1)
        state.hold = not shown
        if shown and (state.page < state.start or state.page > state.end):
            return (GOTO, state.start)
        return (WAIT, None)

    def step(self, tab_id, shown):
        """次の1手を返す。非表示と、再表示の直後は送らない。

        Args:
            tab_id: タブ id。
            shown: 見えているとき True。

        Returns:
            ("wait", None)、("next", None)、("goto", ページ)、("stop", None)、("idle", None)。
        """
        state = self.tabs.get(tab_id)
        if state is None or not state.running:
            return (IDLE, None)
        if not shown:
            state.hold = True
            return (WAIT, None)
        if state.hold:
            state.hold = False
            return (WAIT, None)
        if state.page < state.start or state.page > state.end:
            return (GOTO, state.start)
        if state.page >= state.end:
            if state.loop:
                return (GOTO, state.start)
            state.running = False
            state.hold = False
            return (STOP, None)
        return (NEXT, None)

    def adopt(self, tab_id, page):
        """送りの結果としてページだけを合わせる。動作中は変えない。

        Args:
            tab_id: タブ id。
            page: 送ったあとのページ。
        """
        state = self.tabs.get(tab_id)
        if state is None:
            return
        state.page = int(page or 1)

    def observe_manual(self, tab_id, page):
        """自分の送り以外でページが変わっていたら、そのタブだけ止める。

        Args:
            tab_id: タブ id。
            page: 観測したページ。

        Returns:
            止めたとき True。
        """
        state = self.tabs.get(tab_id)
        if state is None:
            return False
        number = int(page or 1)
        if not state.running or number == state.page:
            state.page = number
            return False
        state.running = False
        state.hold = False
        state.page = number
        return True

    def note_document(self, tab_id, document, total, page):
        """開いているファイルが変わったら、範囲を戻して止める。

        Args:
            tab_id: タブ id。
            document: 開いているファイルまたはフォルダ。
            total: 新しいページ数。
            page: いまのページ。

        Returns:
            ファイルが変わったとき True。
        """
        state = self.tabs.get(tab_id)
        if state is None or state.document == document:
            return False
        state.document = document
        state.start = 1
        state.end = max(int(total or 1), 1)
        state.page = int(page or 1)
        state.running = False
        state.hold = False
        return True

    def drop_closed(self, live_ids):
        """閉じたタブの状態を捨てる。

        Args:
            live_ids: まだ開いているタブ id。

        Returns:
            捨てたタブ id。
        """
        removed = [tab_id for tab_id in list(self.tabs) if tab_id not in live_ids]
        for tab_id in removed:
            del self.tabs[tab_id]
        return removed
