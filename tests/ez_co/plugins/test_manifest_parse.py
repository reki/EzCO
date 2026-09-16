"""対象: ez_co.plugins.manifest — parse_manifest。"""
from __future__ import annotations

import pytest

from ez_co.plugins.manifest import parse_manifest


def _valid(**overrides):
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
    with pytest.raises(ValueError, match=match):
        parse_manifest(payload)


def test_parse_manifest_rejects_non_object():
    with pytest.raises(ValueError, match="object"):
        parse_manifest([])


def test_parse_manifest_permissions_default_empty():
    assert dict(parse_manifest(_valid()).permissions) == {}


def test_parse_manifest_reads_inactive_callback():
    manifest = parse_manifest(_valid(permissions={"inactive_callback": True}))
    assert manifest.permissions["inactive_callback"] is True


def test_parse_manifest_reads_inactive_callback_false():
    manifest = parse_manifest(_valid(permissions={"inactive_callback": False}))
    assert manifest.permissions["inactive_callback"] is False


def test_parse_manifest_reads_filter_permission():
    manifest = parse_manifest(_valid(permissions={"filter": True}))
    assert manifest.permissions["filter"] is True


def test_parse_manifest_reads_filter_permission_false():
    manifest = parse_manifest(_valid(permissions={"filter": False}))
    assert manifest.permissions["filter"] is False


@pytest.mark.parametrize("value", ["false", "true", 1, 0, None])
def test_parse_manifest_rejects_non_bool_filter_permission(value):
    with pytest.raises(ValueError, match="must be a bool"):
        parse_manifest(_valid(permissions={"filter": value}))


def test_parse_manifest_ignores_unknown_permission_keys():
    manifest = parse_manifest(
        _valid(permissions={"inactive_callback": True, "location": True, "not-a-perm": 1})
    )
    assert dict(manifest.permissions) == {"inactive_callback": True}


@pytest.mark.parametrize("value", ["false", "true", 1, 0, None])
def test_parse_manifest_rejects_non_bool_permission(value):
    with pytest.raises(ValueError, match="must be a bool"):
        parse_manifest(_valid(permissions={"inactive_callback": value}))


def test_parse_manifest_permissions_non_object_raises():
    with pytest.raises(ValueError, match="must be an object"):
        parse_manifest(_valid(permissions=["inactive_callback"]))


def test_parse_manifest_permissions_come_from_json_only():
    manifest = parse_manifest(_valid())
    with pytest.raises(TypeError):
        manifest.permissions["inactive_callback"] = True
    assert dict(manifest.permissions) == {}


def test_parse_manifest_reads_formats_and_sidebar():
    from ez_co.plugins.api import FileKind

    manifest = parse_manifest(
        _valid(formats=[[".TXT", "arch"], {"ext": "png", "type": "image"}], sidebar=True)
    )
    assert [(item.extension, item.kind) for item in manifest.formats] == [
        (".txt", FileKind.ARCHIVE),
        (".png", FileKind.IMAGE),
    ]
    assert manifest.sidebar is True


def test_parse_manifest_rejects_invalid_formats():
    with pytest.raises(ValueError, match="manifest.formats"):
        parse_manifest(_valid(formats="zip"))
    with pytest.raises(ValueError, match="manifest.formats"):
        parse_manifest(_valid(formats=[{"no": "kind"}]))


def test_parse_manifest_rejects_invalid_sidebar():
    with pytest.raises(ValueError, match="manifest.sidebar"):
        parse_manifest(_valid(sidebar="yes"))
