"""対象: ez_co.utils.data_location — 同意の正規化。"""
from ez_co.utils import data_location


def test_consent_one_and_one_zero_zero_are_same(user_json):
    user_json({data_location.PLUGIN_CONSENT_KEY: "1"})
    assert data_location.plugin_consent_version() == "1.0.0"
    assert data_location.plugin_consent_accepted() is True


def test_consent_missing_is_not_accepted():
    assert data_location.plugin_consent_accepted() is False


def test_consent_other_version_is_not_accepted(user_json):
    user_json({data_location.PLUGIN_CONSENT_KEY: "2.0.0"})
    assert data_location.plugin_consent_accepted() is False


def test_accept_plugin_consent_writes_normalized_version():
    data_location.accept_plugin_consent()
    payload = data_location._load_user_payload()
    assert payload[data_location.PLUGIN_CONSENT_KEY] == "1.0.0"
    assert data_location.plugin_consent_accepted() is True
