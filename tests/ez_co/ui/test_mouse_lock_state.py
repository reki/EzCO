"""対象: ez_co.ui.mouse_lock_state。"""
from ez_co.ui.mouse_lock_state import MouseLockState


def test_lock_reasons_are_combined():
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
    state = MouseLockState()
    state.press("Ctrl")
    assert state.locked
    state.release("Ctrl")
    assert not state.locked
    state.fullscreen = True
    state.press("Ctrl")
    assert not state.locked


def test_multiple_held_sources_and_auto_repeat():
    state = MouseLockState()
    assert state.press("Ctrl")
    assert not state.press("Ctrl")
    assert not state.press("MouseMiddle")
    assert not state.release("Ctrl")
    assert state.temporary
    assert state.release("MouseMiddle")
    assert not state.locked


def test_force_clear_only_removes_temporary_reason():
    state = MouseLockState()
    state.fullscreen = True
    state.press("Ctrl")
    assert state.clear_temporary()
    assert not state.temporary
    assert state.locked
