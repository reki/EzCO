"""対象: ez_co.ui.mouse_lock_state。"""
from ez_co.ui.mouse_lock_state import MouseLockState


def test_lock_reasons_are_combined():
    """常時中の押下で解除されず、離したあと全画面だけがロックを失う。"""
    state = MouseLockState()
    state.persistent = True
    state.press("Ctrl")
    assert not state.locked
    state.release("Ctrl")
    assert state.locked
    state.persistent = False
    state.fullscreen = True
    assert state.locked


def test_held_source_inverts_unlocked_and_fullscreen_states():
    """未ロックで押してもロックせず、全画面中の押下でロックが残る。"""
    state = MouseLockState()
    state.press("Ctrl")
    assert state.locked
    state.release("Ctrl")
    assert not state.locked
    state.fullscreen = True
    state.press("Ctrl")
    assert not state.locked


def test_multiple_held_sources_and_auto_repeat():
    """同じ押下の繰り返しや、別の押下が残っているあいだに一時理由が消える。"""
    state = MouseLockState()
    assert state.press("Ctrl")
    assert not state.press("Ctrl")
    assert not state.press("MouseMiddle")
    assert not state.release("Ctrl")
    assert state.temporary
    assert state.release("MouseMiddle")
    assert not state.locked


def test_force_clear_only_removes_temporary_reason():
    """一時理由を消したとき全画面のロックまで落ちる。"""
    state = MouseLockState()
    state.fullscreen = True
    state.press("Ctrl")
    assert state.clear_temporary()
    assert not state.temporary
    assert state.locked
