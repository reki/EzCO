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
