"""対象: ez_co.plugins.api — version_sort_key / normalize_extension / normalize_formats。"""
from ez_co.plugins.api import FileKind, FormatSpec, normalize_extension, normalize_formats, version_sort_key


def test_normalize_extension_adds_dot_and_lowercases():
    """ドット無しや大文字の拡張子が小文字の .付きに揃わず、空文字まで何かが入る。"""
    assert normalize_extension("PNG") == ".png"
    assert normalize_extension(".JpG") == ".jpg"
    assert normalize_extension("") == ""


def test_version_sort_key_orders_semver():
    """プレリリースが同一版より後ろ、1.10 が 1.2 より前、2.0 が 1.10 より前に並ぶ。"""
    versions = ["1.10.0", "1.2.0", "2.0.0", "1.2.0-beta"]
    ordered = sorted(versions, key=version_sort_key)
    assert ordered.index("1.2.0-beta") < ordered.index("1.2.0")
    assert ordered.index("1.2.0") < ordered.index("1.10.0")
    assert ordered.index("1.10.0") < ordered.index("2.0.0")


def _pairs(specs):
    """正規化結果から拡張子と種類の組を取り出す。

    Args:
        specs: 正規化済みの形式。

    Returns:
        拡張子と種類の組。
    """
    return [(item.extension, item.kind) for item in specs]


def test_normalize_formats_string_pair():
    """拡張子と種類の組が archive の .txt にならない。"""
    assert _pairs(normalize_formats([[".txt", "archive"]])) == [(".txt", FileKind.ARCHIVE)]


def test_normalize_formats_expands_tuple_first_list():
    """先頭の拡張子リストが、同じ種類の複数形式に展開されない。"""
    assert _pairs(normalize_formats([[[".txt", ".log"], "archive"]])) == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_normalize_formats_expands_object_ext_list():
    """オブジェクトの ext 配列が、小文字の .付きで展開されない。"""
    assert _pairs(normalize_formats([{"ext": [".TXT", "log"], "kind": "archive"}])) == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_normalize_formats_object_ext_string():
    """ext が文字列のとき image の .png にならない。"""
    assert _pairs(normalize_formats([{"ext": "png", "kind": "image"}])) == [(".png", FileKind.IMAGE)]


def test_normalize_formats_ignores_extension_and_type_aliases():
    """extension や type という別名キーが形式として残る。"""
    assert normalize_formats([{"extension": ".txt", "type": "archive"}]) == []
    assert normalize_formats([{"extension": ".txt", "kind": "archive"}]) == []
    assert normalize_formats([{"ext": ".txt", "type": "archive"}]) == []


def test_normalize_formats_does_not_treat_flat_list_as_many_exts():
    """拡張子が3つ並んだフラットなリストが、複数形式として通る。"""
    assert normalize_formats([[".txt", ".log", "archive"]]) == []


def test_normalize_formats_skips_blank_and_dedupes():
    """空の拡張子が残り、同じ拡張子が重複したままになる。"""
    assert _pairs(normalize_formats([[[".txt", "", ".txt", ".log"], "arch"]])) == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_normalize_formats_keeps_format_spec():
    """FormatSpec の拡張子が小文字の .付きに揃わない。"""
    specs = normalize_formats([FormatSpec(".PNG", FileKind.IMAGE)])
    assert _pairs(specs) == [(".png", FileKind.IMAGE)]


def test_normalize_formats_skips_invalid_entries_keeps_valid():
    """壊れた要素で全体が落ち、後ろの有効な形式まで消える。"""
    assert _pairs(normalize_formats([{"no": "kind"}, [".txt", "archive"]])) == [
        (".txt", FileKind.ARCHIVE)
    ]
