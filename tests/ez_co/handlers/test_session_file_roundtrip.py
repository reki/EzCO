"""対象: ez_co.handlers.session_file — 保存と読み戻し。"""
from ez_co.handlers.session_file import load_session, save_session


def test_session_roundtrip(tmp_path):
    """保存したタブは pinned が False で読み戻され、現在インデックスも残る。"""
    path = tmp_path / "tabs.ezs"
    tabs = [{"path": "C:/a.png", "page": 3}, {"path": "C:/b.png", "page": 1}]
    save_session(path, tabs, 1)
    loaded = load_session(path)
    assert loaded["tabs"] == [
        {"path": "C:/a.png", "page": 3, "pinned": False},
        {"path": "C:/b.png", "page": 1, "pinned": False},
    ]
    assert loaded["current"] == 1


def test_session_roundtrip_keeps_pinned(tmp_path):
    """保存時の pinned と現在インデックスは読み戻しでそのまま残る。"""
    path = tmp_path / "pinned.ezs"
    tabs = [
        {"path": "C:/a.png", "page": 2, "pinned": True},
        {"path": "C:/b.png", "page": 1, "pinned": False},
    ]
    save_session(path, tabs, 0)
    loaded = load_session(path)
    assert loaded["tabs"] == tabs
    assert loaded["current"] == 0
