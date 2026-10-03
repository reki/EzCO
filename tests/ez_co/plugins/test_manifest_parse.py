"""対象: ez_co.plugins.manifest — parse_manifest。"""
from __future__ import annotations

import pytest

from ez_co.plugins.manifest import parse_manifest


def _valid(**overrides):
    """必須項目を埋めた manifest 辞書を返す。

    Args:
        **overrides: 上書きする項目。

    Returns:
        parse_manifest に渡せる辞書。
    """
    body = {
        "id": "com.example.x",
        "name": "Example",
        "version": "1.0.0",
        "api_version": 1,
        "entry": "plugin:Probe",
    }
    body.update(overrides)
    return body


def test_parse_manifest_reads_required_fields():
    """id、name、version、api、entry の module と class、説明、作者が読めず、権限と形式と sidebar が空の既定にならない。"""
    manifest = parse_manifest(_valid(description="d", author="a"))
    assert manifest.plugin_id == "com.example.x"
    assert manifest.name == "Example"
    assert manifest.version == "1.0.0"
    assert manifest.api_version == 1
    assert manifest.entry_module == "plugin"
    assert manifest.entry_class == "Probe"
    assert manifest.description == "d"
    assert manifest.author == "a"
    assert dict(manifest.permissions) == {}
    assert manifest.formats == ()
    assert manifest.sidebar is False


@pytest.mark.parametrize(
    "payload, match",
    [
        ({}, "manifest.id"),
        (_valid(id=""), "manifest.id"),
        (_valid(name=""), "manifest.name"),
        (_valid(version=""), "manifest.version"),
        (_valid(entry=""), "manifest.entry"),
        (_valid(entry="plugin"), "module:Class"),
        (_valid(api_version="x"), "api_version"),
    ],
)
def test_parse_manifest_rejects_invalid(payload, match):
    """必須の欠落、空の id や name や version や entry、module:Class でない entry、数値でない api_version が、それぞれの文言で ValueError にならない。"""
    with pytest.raises(ValueError, match=match):
        parse_manifest(payload)


def test_parse_manifest_rejects_non_object():
    """配列の manifest が object の ValueError にならない。"""
    with pytest.raises(ValueError, match="object"):
        parse_manifest([])


def test_parse_manifest_permissions_default_empty():
    """permissions を書かないと空の辞書にならない。"""
    assert dict(parse_manifest(_valid()).permissions) == {}


def test_parse_manifest_reads_inactive_callback():
    """inactive_callback の true が真として残らない。"""
    manifest = parse_manifest(_valid(permissions={"inactive_callback": True}))
    assert manifest.permissions["inactive_callback"] is True


def test_parse_manifest_reads_inactive_callback_false():
    """inactive_callback の false が偽として残らない。"""
    manifest = parse_manifest(_valid(permissions={"inactive_callback": False}))
    assert manifest.permissions["inactive_callback"] is False


def test_parse_manifest_reads_filter_permission():
    """filter の true が真として残らない。"""
    manifest = parse_manifest(_valid(permissions={"filter": True}))
    assert manifest.permissions["filter"] is True


def test_parse_manifest_reads_filter_permission_false():
    """filter の false が偽として残らない。"""
    manifest = parse_manifest(_valid(permissions={"filter": False}))
    assert manifest.permissions["filter"] is False


@pytest.mark.parametrize("value", ["false", "true", 1, 0, None])
def test_parse_manifest_rejects_non_bool_filter_permission(value):
    """filter が文字列や数値や None でも、bool 必須の ValueError にならない。"""
    with pytest.raises(ValueError, match="must be a bool"):
        parse_manifest(_valid(permissions={"filter": value}))


def test_parse_manifest_ignores_unknown_permission_keys():
    """未知の権限キーや location が permissions に残る。"""
    manifest = parse_manifest(
        _valid(permissions={"inactive_callback": True, "location": True, "not-a-perm": 1})
    )
    assert dict(manifest.permissions) == {"inactive_callback": True}


@pytest.mark.parametrize("value", ["false", "true", 1, 0, None])
def test_parse_manifest_rejects_non_bool_permission(value):
    """inactive_callback が文字列や数値や None でも、bool 必須の ValueError にならない。"""
    with pytest.raises(ValueError, match="must be a bool"):
        parse_manifest(_valid(permissions={"inactive_callback": value}))


def test_parse_manifest_permissions_non_object_raises():
    """permissions が配列でも、object 必須の ValueError にならない。"""
    with pytest.raises(ValueError, match="must be an object"):
        parse_manifest(_valid(permissions=["inactive_callback"]))


def test_parse_manifest_permissions_come_from_json_only():
    """パース後に permissions へ代入でき、空だった辞書が変わる。"""
    manifest = parse_manifest(_valid())
    with pytest.raises(TypeError):
        manifest.permissions["inactive_callback"] = True
    assert dict(manifest.permissions) == {}


def test_parse_manifest_reads_formats_and_sidebar():
    """.TXT の archive と png の image に揃わず、sidebar の true が真にならない。"""
    from ez_co.plugins.api import FileKind

    manifest = parse_manifest(
        _valid(formats=[[".TXT", "arch"], {"ext": "png", "kind": "image"}], sidebar=True)
    )
    assert [(item.extension, item.kind) for item in manifest.formats] == [
        (".txt", FileKind.ARCHIVE),
        (".png", FileKind.IMAGE),
    ]
    assert manifest.sidebar is True


def test_parse_manifest_expands_format_ext_list():
    """ext の配列が .txt と .log の archive に展開されない。"""
    from ez_co.plugins.api import FileKind

    manifest = parse_manifest(_valid(formats=[[[".txt", ".log"], "archive"]]))
    assert [(item.extension, item.kind) for item in manifest.formats] == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_parse_manifest_rejects_invalid_formats():
    """文字列、kind の無いオブジェクト、extension と type の別名が manifest.formats の ValueError にならない。"""
    with pytest.raises(ValueError, match="manifest.formats"):
        parse_manifest(_valid(formats="zip"))
    with pytest.raises(ValueError, match="manifest.formats"):
        parse_manifest(_valid(formats=[{"no": "kind"}]))
    with pytest.raises(ValueError, match="manifest.formats"):
        parse_manifest(_valid(formats=[{"extension": ".txt", "type": "archive"}]))


def test_parse_manifest_rejects_invalid_sidebar():
    """sidebar が文字列でも manifest.sidebar の ValueError にならない。"""
    with pytest.raises(ValueError, match="manifest.sidebar"):
        parse_manifest(_valid(sidebar="yes"))
