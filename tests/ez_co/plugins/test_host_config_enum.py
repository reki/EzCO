"""対象: ez_co.plugins.host — choice の Enum（DB は name、get_config は member）。"""
from enum import Enum, IntEnum, StrEnum

import pytest

from ez_co.plugins.host import PluginHost, parse_config_choices


class _MemoryDb:
    """プラグイン設定を辞書に持つ、テスト用の DB。"""

    def __init__(self):
        """行の辞書を空にする。"""
        self.rows = {}

    def get_plugin_setting(self, plugin_id, key, default=None):
        """保存済みの値を返す。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            default: 行が無いときの値。

        Returns:
            保存値。無ければ default。
        """
        return self.rows.get((plugin_id, key), default)

    def set_plugin_setting(self, plugin_id, key, value):
        """設定を辞書へ書く。

        Args:
            plugin_id: プラグイン ID。
            key: 設定キー。
            value: 保存する値。

        Returns:
            常に真。
        """
        self.rows[(plugin_id, key)] = value
        return True


class Style(Enum):
    """同じ値の別名を持つ choice 用 Enum。"""

    PLAIN = "plain"
    BOLD = "bold"
    EMPHASIS = BOLD


class Count(IntEnum):
    """保存値が数値にならないかを見る IntEnum。"""

    ONE = 1
    TWO = 2


class Kind(StrEnum):
    """member を並べた choice が name の組になる StrEnum。"""

    PLAIN = "plain"
    BOLD = "bold"


class Other(Enum):
    """Style と混ぜると拒否される別 Enum。"""

    X = "x"


def _scoped():
    """メモリ DB を載せたホストと、そのスコープを返す。

    Returns:
        ホストと com.example.x のスコープ。
    """
    host = PluginHost()
    host._db = _MemoryDb()
    return host, host.scoped("com.example.x")


def test_parse_strenum_members_before_strings():
    """StrEnum の member がクラスと name の組にならず、文字列の選択肢になる。"""
    rows, enum_type = parse_config_choices([Kind.PLAIN, Kind.BOLD])
    assert enum_type is Kind
    assert rows == (("PLAIN", "PLAIN"), ("BOLD", "BOLD"))


def test_register_enum_class_and_member_default():
    """Enum クラスを渡すと enum_type と default の member が消え、get_config が member を返さない。"""
    _host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.PLAIN, choices=Style)
    field = _host.configs_for("com.example.x")[0]
    assert field.enum_type is Style
    assert field.default is Style.PLAIN
    assert scoped.get_config("style") is Style.PLAIN


def test_set_config_stores_canonical_name(monkeypatch):
    """別名 EMPHASIS の保存名が BOLD でなく、get_config と config_changed が BOLD member にならない。"""
    host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.PLAIN, choices=Style)
    seen = []
    scoped.on("config_changed", lambda payload: seen.append(payload))
    assert scoped.set_config("style", Style.EMPHASIS) is True
    assert host._db.rows[("com.example.x", "style")] == "BOLD"
    assert scoped.get_config("style") is Style.BOLD
    assert seen[-1]["value"] is Style.BOLD


def test_restore_unknown_name_uses_default():
    """DB の未知の name が default の member に戻らない。"""
    host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.PLAIN, choices=Style)
    host._db.rows[("com.example.x", "style")] = "GONE"
    assert scoped.get_config("style") is Style.PLAIN


def test_missing_row_uses_default():
    """行が無いとき default の member が返らない。"""
    _host, scoped = _scoped()
    scoped.register_config("style", "choice", default=Style.BOLD, choices=Style)
    assert scoped.get_config("style") is Style.BOLD


def test_intenum_stores_name_not_value():
    """IntEnum の保存値が数値の 2 になり、name の TWO にならない。"""
    host, scoped = _scoped()
    scoped.register_config("count", "choice", default=Count.ONE, choices=Count)
    scoped.set_config("count", Count.TWO)
    assert host._db.rows[("com.example.x", "count")] == "TWO"
    assert scoped.get_config("count") is Count.TWO


def test_invalid_default_rejected():
    """候補に無い default が ValueError にならず、フィールドが登録される。"""
    _host, scoped = _scoped()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("style", "choice", default="NOPE", choices=Style)
    assert _host.configs_for("com.example.x") == []


def test_mixed_enums_rejected():
    """別クラスの member を混ぜても ValueError にならない。"""
    _host, scoped = _scoped()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("style", "choice", choices=[Style.PLAIN, Other.X])


def test_empty_enum_rejected():
    """メンバーの無い Enum が ValueError にならない。"""
    class Empty(Enum):
        """メンバーを持たない choice。"""

        pass

    _host, scoped = _scoped()
    with pytest.raises(ValueError, match="com.example.x"):
        scoped.register_config("style", "choice", choices=Empty)


def test_list_choice_still_returns_string():
    """タプルの choices が member になり、保存値と get_config が文字列の bold にならない。"""
    host, scoped = _scoped()
    scoped.register_config(
        "mode",
        "choice",
        default="plain",
        choices=[("plain", "Plain"), ("bold", "Bold")],
    )
    scoped.set_config("mode", "bold")
    assert host._db.rows[("com.example.x", "mode")] == "bold"
    assert scoped.get_config("mode") == "bold"


def test_multiple_enum_roundtrip_and_invalid_resets_all():
    """複数選択の保存が name の配列にならず、未知の name が混ざった行が default の PLAIN 以外を返す。"""
    host, scoped = _scoped()
    scoped.register_config(
        "styles",
        "choice",
        default=[Style.PLAIN],
        choices=Style,
        multiple=True,
    )
    scoped.set_config("styles", [Style.PLAIN, Style.BOLD])
    assert host._db.rows[("com.example.x", "styles")] == ["PLAIN", "BOLD"]
    assert scoped.get_config("styles") == [Style.PLAIN, Style.BOLD]
    host._db.rows[("com.example.x", "styles")] = ["PLAIN", "GONE"]
    assert scoped.get_config("styles") == [Style.PLAIN]
