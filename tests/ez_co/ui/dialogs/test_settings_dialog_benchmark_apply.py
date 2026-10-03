"""対象: ez_co.ui.dialogs.settings_dialog"""
import pytest

from ez_co.config import Config
from ez_co.services.image_loading_benchmark_evaluator import BenchmarkOutcome
from ez_co.ui.dialogs import settings_dialog
from ez_co.ui.dialogs.settings_dialog import SettingsDialog

# 1GiB のバイト数。
GIB = 1024**3

# このモジュールのテストは QApplication 付きで動かす。
pytestmark = pytest.mark.usefixtures("qapp")


@pytest.fixture(autouse=True)
def stub_environment(monkeypatch: pytest.MonkeyPatch):
    """データ位置と CPU・物理メモリを固定し、実環境を読ませない。"""
    monkeypatch.setattr(
        settings_dialog,
        "load_location_settings",
        lambda: {"data_location": "user", "custom_path": ""},
    )
    monkeypatch.setattr(settings_dialog, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(settings_dialog, "physical_memory_bytes", lambda: 32 * GIB)


def _dialog(config):
    """ワーカー数を固定した設定ダイアログを開く。

    Args:
        config: ダイアログへ渡す設定。

    Returns:
        開いた設定ダイアログ。
    """
    config.freeze_image_loader_workers(logical_cpu_count=24)
    return SettingsDialog(config)


def _outcome(**kwargs):
    """計測結果の既定値を上書きして返す。

    Args:
        **kwargs: BenchmarkOutcome の上書き項目。

    Returns:
        ウィジェットへ載せる計測結果。
    """
    defaults = dict(
        memory_limit="512MB",
        prefetch_pages=10,
        image_loader_workers="auto",
        effective_workers=4,
        p95_latency_ms=32.5,
        max_latency_ms=91.0,
        condition_rss_delta_bytes=123_456_789,
        elapsed_seconds=75.0,
    )
    defaults.update(kwargs)
    return BenchmarkOutcome(**defaults)


def test_measured_result_only_changes_widgets():
    """計測結果が設定オブジェクトのキャッシュ値まで書き、ウィジェットが計測値にならない。"""
    config = Config.from_dict(
        {
            "cache": {
                "memory_limit": "256MB",
                "prefetch_pages": 5,
                "image_loader_workers": 8,
            }
        }
    )
    dialog = _dialog(config)
    try:
        dialog.apply_benchmark_outcome(_outcome())

        assert dialog.cache_memory_limit.text() == "512MB"
        assert dialog.cache_prefetch_pages.value() == 10
        assert dialog.cache_image_loader_workers.currentData() == "auto"
        assert config.cache["memory_limit"] == "256MB"
        assert config.cache["prefetch_pages"] == 5
        assert config.cache["image_loader_workers"] == 8
    finally:
        dialog.close()


def test_measured_manual_worker_count_is_selected_in_the_combo():
    """計測が手動のワーカー数を返しても、コンボの選択がその数にならない。"""
    dialog = _dialog(Config())
    try:
        dialog.apply_benchmark_outcome(
            _outcome(image_loader_workers=6, effective_workers=6)
        )

        assert dialog.cache_image_loader_workers.currentData() == 6
    finally:
        dialog.close()


def test_measure_button_is_enabled_without_runtime_overrides():
    """実行時上書きが無いのに計測ボタンが無効で、無効理由が出る。"""
    dialog = _dialog(Config())
    try:
        assert dialog.cache_measure_button.isEnabled()
        assert not dialog.cache_measure_disabled_label.isVisible()
    finally:
        dialog.close()


@pytest.mark.parametrize(
    "override_key, override_value",
    [
        ("cache.memory_limit", "128MB"),
        ("cache.prefetch_pages", 20),
        ("cache.image_loader_workers", 7),
    ],
)
def test_measure_button_is_disabled_when_any_cache_key_is_overridden(
    override_key,
    override_value,
):
    """メモリ上限・先読み・ワーカー数のどれか一つが実行時上書きでも、計測ボタンが有効のまま。"""
    config = Config()
    config.set_runtime_override(override_key, override_value)
    dialog = _dialog(config)
    try:
        assert not dialog.cache_measure_button.isEnabled()
        assert dialog.cache_measure_disabled_label.text()
    finally:
        dialog.close()


def test_measure_action_does_nothing_when_the_dialog_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
):
    """計測ダイアログが結果を返さないのに、メモリ上限の入力が変わる。"""
    from ez_co.ui.dialogs import image_loading_benchmark_dialog

    monkeypatch.setattr(
        image_loading_benchmark_dialog,
        "run_image_loading_benchmark_dialog",
        lambda parent: None,
    )
    config = Config()
    dialog = _dialog(config)
    try:
        before = dialog.cache_memory_limit.text()

        dialog.measure_best_cache_settings()

        assert dialog.cache_memory_limit.text() == before
    finally:
        dialog.close()


def test_measure_action_applies_the_returned_outcome(monkeypatch: pytest.MonkeyPatch):
    """計測ダイアログの戻り値がウィジェットに載らず、設定オブジェクトのメモリ上限まで変わる。"""
    from ez_co.ui.dialogs import image_loading_benchmark_dialog

    monkeypatch.setattr(
        image_loading_benchmark_dialog,
        "run_image_loading_benchmark_dialog",
        lambda parent: _outcome(memory_limit="256MB", prefetch_pages=5),
    )
    config = Config.from_dict({"cache": {"memory_limit": "1GB", "prefetch_pages": 30}})
    dialog = _dialog(config)
    try:
        dialog.measure_best_cache_settings()

        assert dialog.cache_memory_limit.text() == "256MB"
        assert dialog.cache_prefetch_pages.value() == 5
        assert config.cache["memory_limit"] == "1GB"
    finally:
        dialog.close()
