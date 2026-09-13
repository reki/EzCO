"""商品ページの HTML が変わって項目が取れなくなったかを見る。

値の一致は見ない。タイトル・表紙・概要などが空でないことだけを確認する。
ネットワークが必要なので、普段の本体テストとは別に実行する。

    poetry run pytest plugins/product_info/test/test_fetch_fields.py -s
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fetch import fetch_product, match_product

# サイドバーが表示に使う項目。値は見ない。サイト種別で取れない欄は必須にしない。
# DMM: 年齢／カテゴリ／ファイル形式は取らない。VJ (pro) はファイル形式欄が無いことが多い。
_COMMON = ("タイトル", "URL", "PID", "ブランド名", "作品種別", "genre一覧", "概要")
_CASES = (
    ("dmm", "d_802808", _COMMON),
    ("dlsite", "RJ01530423", _COMMON + ("カテゴリー", "年齢種別", "作品形式", "ファイル形式")),
    ("dlsite", "VJ01004239", _COMMON + ("カテゴリー", "年齢種別", "作品形式")),
)


def _present(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (bytes, bytearray)):
        return bool(value)
    if isinstance(value, (list, tuple, set)):
        return any(_present(item) for item in value)
    return bool(str(value).strip())


def _missing(data: dict | None, keys) -> list[str]:
    if not data:
        return ["(fetch returned None)"] + list(keys) + ["_cover"]
    missing = [key for key in keys if not _present(data.get(key))]
    if not _present(data.get("_cover")):
        missing.append("_cover")
    return missing


@pytest.mark.parametrize("kind,product_id,keys", _CASES)
def test_match_product_id(kind, product_id, keys):
    matched = match_product(product_id)
    assert matched is not None, f"{product_id} did not match"
    assert matched[0] == kind
    assert matched[1].upper() == product_id.upper() or matched[1] == product_id


@pytest.mark.parametrize("kind,product_id,keys", _CASES)
def test_fetch_sidebar_fields(kind, product_id, keys):
    data = fetch_product(kind, product_id)
    missing = _missing(data, keys)
    if missing:
        got = []
        if data:
            got = [key for key in (*keys, "_cover") if key not in missing]
        pytest.fail(
            f"{product_id} ({kind}) missing: {', '.join(missing)}"
            + (f" / got: {', '.join(got)}" if got else "")
        )
