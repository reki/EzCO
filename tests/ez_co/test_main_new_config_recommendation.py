"""対象: ez_co.main"""
import pytest

from ez_co import main as main_module
from ez_co.utils import system_resources

GIB = 1024**3

pytestmark = pytest.mark.usefixtures("qapp")


class _FakeDatabaseManager:
    """load_config_from_db が使う最小のDB窓口。"""

    def __init__(self, data=None):
        """読み戻す設定と保存先を持つ。

        Args:
            data: 読み戻す設定。省略時は空。
        """
        self.current_profile = "default"
        self.data = data
        self.saved = {}

    def load_profile_config(self, profile_name):
        """コンストラクタで渡した設定を返す。

        Args:
            profile_name: プロファイル名。

        Returns:
            渡された設定。
        """
        return self.data

    def save_profile_config(self, profile_name, payload):
        """プロファイル名ごとに保存内容を覚え、成功を返す。

        Args:
            profile_name: プロファイル名。
            payload: 保存する設定。

        Returns:
            成功を表す真。
        """
        self.saved[profile_name] = payload
        return True


@pytest.fixture
def large_ram(monkeypatch: pytest.MonkeyPatch):
    """CPU 24、物理メモリ 32GB に固定する。"""
    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 24)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 32 * GIB)


def test_new_profile_config_is_created_with_recommended_values(large_ram):
    """設定の無いプロファイルは 512MB、先読み 5、ワーカー auto で作られ、その上限と先読みが保存される。"""
    db_manager = _FakeDatabaseManager()

    config = main_module.load_config_from_db(db_manager)

    assert config.cache["memory_limit"] == "512MB"
    assert config.cache["prefetch_pages"] == 5
    assert config.cache["image_loader_workers"] == "auto"
    assert db_manager.saved["default"]["cache"]["memory_limit"] == "512MB"
    assert db_manager.saved["default"]["cache"]["prefetch_pages"] == 5


def test_low_ram_machine_gets_safe_cache_limit(monkeypatch: pytest.MonkeyPatch):
    """小容量メモリでは新しい設定のキャッシュ上限が 256MB になり、先読みは 5 になる。"""
    monkeypatch.setattr(system_resources, "logical_cpu_count", lambda: 4)
    monkeypatch.setattr(system_resources, "physical_memory_bytes", lambda: 8 * GIB)
    db_manager = _FakeDatabaseManager()

    config = main_module.load_config_from_db(db_manager)

    assert config.cache["memory_limit"] == "256MB"
    assert config.cache["prefetch_pages"] == 5


def test_existing_config_is_not_overwritten_by_recommendation(large_ram):
    """既にある 1GB、先読み 30、ワーカー 8 は推奨で上書きされず、保存もされない。"""
    existing = main_module.Config.from_dict(
        {
            "cache": {
                "memory_limit": "1GB",
                "prefetch_pages": 30,
                "image_loader_workers": 8,
            }
        }
    )
    db_manager = _FakeDatabaseManager(existing.to_dict())

    config = main_module.load_config_from_db(db_manager)

    assert config.cache["memory_limit"] == "1GB"
    assert config.cache["prefetch_pages"] == 30
    assert config.cache["image_loader_workers"] == 8
    assert db_manager.saved == {}
