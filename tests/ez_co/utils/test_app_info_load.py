"""対象: ez_co.utils.app_info — resources/about の読み込み。"""
from ez_co.utils.app_info import load_app_info


def test_load_app_info_reads_packaged_fields():
    info = load_app_info()
    assert info["name"] == "EzCo"
    assert info["version"]
    assert info["author"]
    assert info["years"]
    assert info["license"] == "MIT"
    assert info["homepage"].startswith("http")
    assert info["description"] == "A lightweight comic viewer"
    assert not isinstance(info["description"], dict)
    assert info["hash"] == ""
