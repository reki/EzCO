"""対象: ez_co.enums.actions — 日英アクションリファレンスとの同期。"""
import re
from pathlib import Path

import pytest

from ez_co.enums.actions import ACTION_LIST

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "name",
    ["action-reference.html", "action-reference-en.html"],
)
def test_manual_lists_each_canonical_action_once(name):
    text = (ROOT / "resources" / "UserManual" / "files" / name).read_text(
        encoding="utf-8"
    )
    listed = re.findall(r'data-action-id="([^"]+)"', text)
    assert len(listed) == len(set(listed))
    assert set(listed) == set(ACTION_LIST)
