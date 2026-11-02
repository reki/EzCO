"""対象: plugins/auto_page/src/turn.py — 送り先、停止、非表示、タブ閉じ。"""
import importlib.util
from pathlib import Path


def _load():
    """送り先モジュールを、プラグインのファイルから読む。

    Returns:
        turn モジュール。
    """
    path = Path(__file__).resolve().parents[4] / "plugins" / "auto_page" / "src" / "turn.py"
    spec = importlib.util.spec_from_file_location("auto_page_turn", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


turn = _load()


def _state(tab_id="a", page=2, total=10, start=1, end=10, loop=False):
    """動作中のタブ状態を作る。

    Args:
        tab_id: タブ id。
        page: いまのページ。
        total: ページ数。
        start: 開始ページ。
        end: 終了ページ。
        loop: ループするとき True。

    Returns:
        (TurnBook, そのタブの状態)。
    """
    book = turn.TurnBook()
    state = book.touch(tab_id, page, total, "doc", 1)
    state.start = start
    state.end = end
    state.loop = loop
    state.page = page
    state.running = True
    return book, state


def test_inside_range_turns_next_without_jumping_to_start():
    """範囲内なのに開始ページへ飛ぶ、または次ページにならない。"""
    book = turn.TurnBook()
    state = book.touch("a", 3, 10, "doc", 1)
    state.end = 10
    assert book.begin("a", 3, True) == (turn.WAIT, None)
    assert book.step("a", True) == (turn.NEXT, None)


def test_outside_range_goes_to_start():
    """範囲の前や終了のあとが、開始ページへ移らない。"""
    book, _state_a = _state(page=1, start=3, end=8)
    assert book.step("a", True) == (turn.GOTO, 3)
    book, _state_b = _state(page=12, start=1, end=10, loop=False)
    assert book.step("a", True) == (turn.GOTO, 1)
    book, _state_c = _state(page=12, start=1, end=10, loop=True)
    assert book.step("a", True) == (turn.GOTO, 1)


def test_end_page_stops_or_returns_to_start():
    """終了ページの次が、ループなしで動き続けるか、ループありで開始へ戻らない。"""
    book, state = _state(page=10, start=1, end=10, loop=False)
    assert book.step("a", True) == (turn.STOP, None)
    assert state.running is False
    book, state = _state(page=10, start=2, end=10, loop=True)
    assert book.step("a", True) == (turn.GOTO, 2)
    assert state.running is True


def test_hidden_tab_does_not_turn():
    """見えていないタブがページを送る。"""
    book, state = _state(page=3, start=1, end=10)
    assert book.step("a", False) == (turn.WAIT, None)
    assert state.running is True


def test_just_shown_waits_one_interval():
    """再表示の直後に送り、次の間隔を待たない。"""
    book, state = _state(page=3, start=1, end=10)
    assert book.step("a", False) == (turn.WAIT, None)
    assert book.step("a", True) == (turn.WAIT, None)
    assert state.running is True
    assert book.step("a", True) == (turn.NEXT, None)


def test_own_turn_does_not_stop():
    """自分の送りでページが進むと、そのタブが止まる。"""
    book, state = _state(page=3, start=1, end=10)
    book.adopt("a", 4)
    assert state.running is True
    assert book.observe_manual("a", 4) is False
    assert state.running is True


def test_manual_change_stops_only_that_tab():
    """手動のページ変更が、他のタブまで止める。"""
    book, _state_a = _state("a", page=3)
    state_b = book.touch("b", 2, 10, "other", 1)
    state_b.running = True
    state_b.page = 2
    assert book.observe_manual("a", 6) is True
    assert book.tabs["a"].running is False
    assert book.tabs["b"].running is True


def test_unchanged_turn_does_not_ignore_later_manual():
    """ページが変わらなかった送りのあと、手動の変更を無視する。"""
    book, state = _state(page=4, start=1, end=10)
    book.adopt("a", 4)
    assert book.observe_manual("a", 7) is True
    assert state.running is False


def test_closed_tab_state_is_dropped():
    """閉じたタブの開始や動作中が残る。"""
    book, _state_a = _state("a")
    book.touch("b", 1, 5, "other", 1)
    removed = book.drop_closed({"b"})
    assert removed == ["a"]
    assert "a" not in book.tabs
    assert "b" in book.tabs


def test_start_outside_range_goes_immediately():
    """開始した瞬間に範囲外なのに、間隔を待ってから開始ページへ移る。"""
    book = turn.TurnBook()
    state = book.touch("a", 1, 10, "doc", 1)
    state.start = 4
    state.end = 9
    assert book.begin("a", 1, True) == (turn.GOTO, 4)
    assert state.running is True


def test_new_tab_loop_starts_on():
    """新しいタブのループがオフで始まる。"""
    book = turn.TurnBook()
    state = book.touch("a", 1, 10, "doc", 1)
    assert state.loop is True


def test_file_change_resets_range_and_stops():
    """別のファイルになっても、開始と終了が残るか、動き続けるか、ループの選択が戻る。"""
    book, state = _state(page=5, start=3, end=8)
    state.loop = False
    state.interval_custom = True
    state.loop_custom = True
    assert book.note_document("a", "other", 20, 1) is True
    assert state.running is False
    assert state.start == 1
    assert state.end == 20
    assert state.loop is False
    assert state.interval_custom is True
    assert state.loop_custom is True


def test_default_interval_skips_edited_tabs():
    """間隔を触ったタブまで、設定の初期値で上書きされる。"""
    book, state = _state("a")
    other = book.touch("b", 1, 5, "other", 1)
    state.interval = 9
    state.interval_custom = True
    book.apply_default_interval(4)
    assert state.interval == 9
    assert other.interval == 4


def test_interval_rounds_to_one_decimal_second():
    """間隔が小数第1位の秒に収まらず、範囲の外が残る。"""
    book = turn.TurnBook()
    state = book.touch("a", 1, 10, "doc", 1.26)
    assert state.interval == 1.3
    book.apply_default_interval(0.04)
    assert state.interval == 0.1
    book.apply_default_interval(1000)
    assert state.interval == 600.0


def test_wait_converts_seconds_to_milliseconds():
    """0.1秒が100ミリ秒、1.5秒が1500ミリ秒の待ちにならない。"""
    assert turn.interval_wait_ms(0.1) == 100
    assert turn.interval_wait_ms(1.5) == 1500


def test_touch_uses_given_loop_default():
    """渡したループ初期値が、新しいタブのループに入らない。"""
    book = turn.TurnBook()
    state = book.touch("a", 1, 10, "doc", 1000, False)
    assert state.loop is False
    assert state.loop_custom is False


def test_default_loop_skips_edited_tabs():
    """ループを触ったタブまで、設定の初期値で上書きされる。"""
    book, state = _state("a", loop=False)
    state.loop_custom = True
    other = book.touch("b", 1, 5, "other", 1000, True)
    book.apply_default_loop(False)
    assert state.loop is False
    assert other.loop is False
    book.apply_default_loop(True)
    assert state.loop is False
    assert other.loop is True


def test_empty_page_count_cannot_begin():
    """ページが無いタブを開始でき、ページがあるタブを開始できない。"""
    assert turn.can_begin(0) is False
    assert turn.can_begin(None) is False
    assert turn.can_begin("none") is False
    assert turn.can_begin(1) is True
