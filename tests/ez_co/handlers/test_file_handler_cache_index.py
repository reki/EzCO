"""対象: ez_co.handlers.file_handler — 追い出しの index は確定済みの表から引く。"""
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from ez_co.handlers.file_handler import FileHandler


def _handler(monkeypatch):
    """ワーカーを起動しない FileHandler を作る。

    Returns:
        その FileHandler。
    """
    monkeypatch.setattr(FileHandler, "_start_workers", lambda self: None)
    config = SimpleNamespace(
        cache={
            "memory_limit": "1MB",
            "prefetch_pages": 3,
            "optimize_large_images": False,
        },
        debug={"keep_archive_handles": False},
        archive={"enabled": True},
    )
    return FileHandler(config)


def _virtual_pages(archive: Path, count: int) -> list[str]:
    """連番の仮想パスを作る。

    Args:
        archive: 書庫パス。
        count: ページ数。

    Returns:
        archive:// 形式のパス列。
    """
    return [f"archive://{archive}|{index:04d}.jpg" for index in range(count)]


def _put_pages(handler, files, indexes):
    """指定インデックスのページを先読み未使用としてキャッシュに入れる。

    Args:
        handler: キャッシュを持つハンドラ。
        files: ページ列。
        indexes: 入れるインデックス。
    """
    for index in indexes:
        image = Image.new("L", (8, 8))
        key = handler._cache_key_for_file(files[index])
        handler.image_cache[key] = image
        handler._cache_usage[key] = {"prefetched": True, "used": False}
        handler.cache_size += handler._estimate_image_size(image)


def test_eviction_uses_index_map_without_scanning_files(tmp_path, monkeypatch):
    """表がある追い出しはファイル走査をせず、現在と隣を残して遠いページを落とす。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    archive.write_bytes(b"")
    files = _virtual_pages(archive, 200)
    handler.current_files = files
    handler.current_index = 100
    handler._rebuild_file_index_map()
    _put_pages(handler, files, list(range(40)) + [99, 100, 101])
    handler.cache_limit = 8 * 8 * 3

    scans = {"count": 0}
    original = handler._find_file_index_by_cache_key

    def counting(cache_key, *, files=None):
        """ファイル走査の回数を数えて元の検索を呼ぶ。

        Args:
            cache_key: 探すキャッシュキー。
            files: 走査するファイル列。省略時はハンドラ側の既定。

        Returns:
            見つかったインデックス。
        """
        scans["count"] += 1
        return original(cache_key, files=files)

    handler._find_file_index_by_cache_key = counting
    handler._evict_cache()

    assert scans["count"] == 0
    for index in (99, 100, 101):
        assert handler._cache_key_for_file(files[index]) in handler.image_cache
    assert handler._cache_key_for_file(files[0]) not in handler.image_cache


def test_index_lookup_does_not_resolve_after_the_map_is_built(tmp_path, monkeypatch):
    """表を作ったあとの距離計算は Path.resolve を増やさない。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    archive.write_bytes(b"")
    files = _virtual_pages(archive, 200)
    handler.current_files = files
    handler.current_index = 100

    resolves = {"count": 0}
    real_resolve = Path.resolve

    def counting_resolve(self, *args, **kwargs):
        """Path.resolve の回数を数えて元の解決を呼ぶ。

        Args:
            args: resolve へ渡す位置引数。
            kwargs: resolve へ渡すキーワード引数。

        Returns:
            解決したパス。
        """
        resolves["count"] += 1
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", counting_resolve)
    handler._rebuild_file_index_map()
    assert resolves["count"] == len(files)

    resolves["count"] = 0
    for key, index in list(handler._cache_key_to_index.items())[:40]:
        assert handler._calculate_page_distance(key) == abs(index - 100)
    assert resolves["count"] == 0


def test_rebuilt_map_follows_replaced_file_list(tmp_path, monkeypatch):
    """ファイル一覧を差し替えて表を作り直すと、旧キーは消え新キーの位置が入る。"""
    handler = _handler(monkeypatch)
    first = _virtual_pages(tmp_path / "first.zip", 5)
    second = _virtual_pages(tmp_path / "second.zip", 5)
    handler.current_files = first
    handler._rebuild_file_index_map()
    handler.current_files = second
    handler._rebuild_file_index_map()

    old_key = handler._cache_key_for_file(first[0])
    new_key = handler._cache_key_for_file(second[3])
    assert old_key not in handler._cache_key_to_index
    assert handler._cache_key_to_index[new_key] == 3


def test_duplicate_cache_key_keeps_the_first_index(tmp_path, monkeypatch):
    """同じキャッシュキーが複数あっても表は最初のインデックスを残す。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    page = f"archive://{archive}|same.jpg"
    later = f"archive://{archive}|later.jpg"
    handler.current_files = [page, page, later]
    handler._rebuild_file_index_map()

    assert handler._cache_key_to_index[handler._cache_key_for_file(page)] == 0
    assert handler._cache_key_to_index[handler._cache_key_for_file(later)] == 2


def test_unknown_cache_key_uses_file_scan(tmp_path, monkeypatch):
    """表に無いキーの距離はファイル走査 1 回で計算される。"""
    handler = _handler(monkeypatch)
    files = [tmp_path / f"{index}.png" for index in range(4)]
    for path in files:
        path.write_bytes(b"")
    handler.current_files = files
    handler.current_index = 1
    handler._rebuild_file_index_map()
    missing = handler._cache_key_for_file(files[3])
    del handler._cache_key_to_index[missing]

    scans = {"count": 0}
    original = handler._find_file_index_by_cache_key

    def counting(cache_key, *, files=None):
        """ファイル走査の回数を数えて元の検索を呼ぶ。

        Args:
            cache_key: 探すキャッシュキー。
            files: 走査するファイル列。省略時はハンドラ側の既定。

        Returns:
            見つかったインデックス。
        """
        scans["count"] += 1
        return original(cache_key, files=files)

    handler._find_file_index_by_cache_key = counting
    assert handler._calculate_page_distance(missing) == 2
    assert scans["count"] == 1


def test_open_files_rebuilds_the_map_once_after_appends(tmp_path, monkeypatch):
    """open_files は空のときと追加が終わった 6 件のときだけ表を作り、インデックス 4 の位置は 4 になる。"""
    sizes = []
    original = FileHandler._rebuild_file_index_map

    def wrapped(self):
        """再構築時のファイル数を記録して元の再構築を呼ぶ。

        Returns:
            元の再構築の結果。
        """
        sizes.append(len(self.current_files))
        return original(self)

    monkeypatch.setattr(FileHandler, "_rebuild_file_index_map", wrapped)
    handler = _handler(monkeypatch)
    handler._resolve_handler = lambda file_path: SimpleNamespace(
        is_skipped=False,
        is_archive=False,
        is_plugin=False,
        is_image=False,
        plugin=None,
    )
    files = []
    for index in range(6):
        path = tmp_path / f"{index}.png"
        path.write_bytes(b"")
        files.append(path)

    assert handler.open_files(files) is True
    assert sizes == [0, 6]
    assert handler._cache_key_to_index[handler._cache_key_for_file(files[4])] == 4


def test_open_archive_refreshes_the_map(tmp_path, monkeypatch):
    """書庫を開くと展開後のページ位置が表に入る。"""
    handler = _handler(monkeypatch)
    archive = tmp_path / "book.zip"
    pages = _virtual_pages(archive, 4)
    handler._resolve_handler = lambda file_path: SimpleNamespace(plugin=object(), is_archive=True)
    handler._expand_archive = lambda file_path: pages

    assert handler._open_archive(archive) is True
    assert handler._cache_key_to_index[handler._cache_key_for_file(pages[2])] == 2
