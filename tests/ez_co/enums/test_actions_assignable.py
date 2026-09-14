"""対象: ez_co.enums.actions — エイリアスで本体 ID を隠す。"""
from ez_co.enums import actions
from ez_co.enums.actions import ACTION_LIST, list_assignable_actions


class _Action:
    def __init__(self, public_id, aliases):
        self.public_id = public_id
        self.aliases = aliases


class _Host:
    def list_actions(self):
        return [_Action("plugin:com.example.x:go", ("next_page",))]


def test_alias_hides_builtin_action_id(monkeypatch):
    monkeypatch.setattr(actions, "_plugin_host", lambda: _Host())
    assignable = list_assignable_actions()
    assert "next_page" not in assignable
    assert "plugin:com.example.x:go" in assignable
    assert "prev_page" in assignable
    assert set(ACTION_LIST) - {"next_page"} <= set(assignable)
