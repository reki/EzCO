"""対象: ez_co.handlers.file_handler — 表示中ページをキャッシュから落とさない。"""
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler


def _handler(monkeypatch, memory_limit="1MB"):
    """指定メモリ上限で、ワーカーを起動しない FileHandler を作る。

    Args:
        memory_limit: キャッシュ上限。

    Returns:
        その FileHandler。
    """
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    config = SimpleNamespace(
        cache={
            "memory_limit": memory_limit,
            "prefetch_pages": 3,
            "optimize_large_images": False,
        },
        debug={"keep_archive_handles": False},
    )
    handler = FileHandler(config)
    return handler


def test_evict_keeps_current_and_neighbor_pages(tmp_path, monkeypatch):
    """上限超過の追い出し後も現在ページと隣はキャッシュに残り、遠いページは落ちる。"""
    handler = _handler(monkeypatch)
    files = [tmp_path / f"{index}.png" for index in range(8)]
    for path in files:
        path.write_bytes(b"")
    handler.current_files = files
    handler.current_index = 0
    handler.cache_limit = 2500

    for path in files:
        image = Image.new("RGB", (20, 20))
        key = handler._cache_key_for_file(path)
        handler._cache_put(key, image, handler._estimate_image_size(image))

    current_key = handler._cache_key_for_file(files[0])
    neighbor_key = handler._cache_key_for_file(files[1])
    far_key = handler._cache_key_for_file(files[7])
    assert current_key in handler.image_cache
    assert neighbor_key in handler.image_cache
    assert far_key not in handler.image_cache


def test_counts_prefetched_page_evicted_before_use(tmp_path, monkeypatch):
    """未使用の先読みが上限で落ちると、使用前追い出し回数が増える。"""
    handler = _handler(monkeypatch)
    files = [tmp_path / f"{index}.png" for index in range(5)]
    for path in files:
        path.write_bytes(b"")
    handler.current_files = files
    handler.current_index = 0
    handler.cache_limit = 2500

    for path in files:
        image = Image.new("RGB", (20, 20))
        handler._cache_put(
            handler._cache_key_for_file(path),
            image,
            handler._estimate_image_size(image),
            prefetched=True,
        )

    assert handler._prefetched_evicted_before_use > 0
