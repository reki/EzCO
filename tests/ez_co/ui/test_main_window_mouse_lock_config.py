"""対象: ez_co.ui.main_window — Configからマウスロックreasonへの反映。"""
from types import SimpleNamespace

from ez_co.ui.main_window import MainWindow
from ez_co.ui.mouse_lock_state import MouseLockState


def test_apply_mouse_lock_config_updates_persistent_and_keeps_fullscreen():
    """常時オンが全画面を消し、押下中を残し、同期を呼ばない。"""
    synced = []
    fake = SimpleNamespace(
        config=SimpleNamespace(viewer={"mouse_lock": True}),
        mouse_lock_state=MouseLockState(),
        _sync_mouse_lock_state=lambda: synced.append(True),
    )
    fake.mouse_lock_state.fullscreen = True
    fake.mouse_lock_state.press("Ctrl")
    MainWindow._apply_mouse_lock_config(fake)
    assert fake.mouse_lock_state.persistent is True
    assert fake.mouse_lock_state.fullscreen is True
    assert not fake.mouse_lock_state.temporary
    assert synced == [True]


def test_apply_mouse_lock_config_can_disable_persistent():
    """常時オフにしても、既に立っている常時理由が残る。"""
    fake = SimpleNamespace(
        config=SimpleNamespace(viewer={"mouse_lock": False}),
        mouse_lock_state=MouseLockState(),
        _sync_mouse_lock_state=lambda: None,
    )
    fake.mouse_lock_state.persistent = True
    MainWindow._apply_mouse_lock_config(fake)
    assert fake.mouse_lock_state.persistent is False
