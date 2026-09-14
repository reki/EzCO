"""対象: ez_co.handlers.session_file — 保存と読み戻し。"""
from ez_co.handlers.session_file import load_session, save_session


def test_session_roundtrip(tmp_path):
    path = tmp_path / "tabs.ezs"
    tabs = [{"path": "C:/a.png", "page": 3}, {"path": "C:/b.png", "page": 1}]
    save_session(path, tabs, 1)
    loaded = load_session(path)
    assert loaded["tabs"] == tabs
    assert loaded["current"] == 1
