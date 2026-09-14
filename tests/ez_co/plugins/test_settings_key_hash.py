"""対象: ez_co.plugins.settings_key — hash_plugin_id。"""
from ez_co.plugins.settings_key import hash_plugin_id


def test_hash_plugin_id_is_stable_and_salted():
    first = hash_plugin_id("com.example.x")
    assert first == hash_plugin_id("com.example.x")
    assert first != hash_plugin_id("com.example.y")
    assert len(first) == 64


def test_hash_plugin_id_treats_empty_as_empty_string():
    assert hash_plugin_id("") == hash_plugin_id(None)
