"""対象: ez_co.plugins.api — version_sort_key / normalize_extension。"""
from ez_co.plugins.api import normalize_extension, version_sort_key


def test_normalize_extension_adds_dot_and_lowercases():
    assert normalize_extension("PNG") == ".png"
    assert normalize_extension(".JpG") == ".jpg"
    assert normalize_extension("") == ""


def test_version_sort_key_orders_semver():
    versions = ["1.10.0", "1.2.0", "2.0.0", "1.2.0-beta"]
    ordered = sorted(versions, key=version_sort_key)
    assert ordered.index("1.2.0-beta") < ordered.index("1.2.0")
    assert ordered.index("1.2.0") < ordered.index("1.10.0")
    assert ordered.index("1.10.0") < ordered.index("2.0.0")
