"""対象: ez_co.plugins.api — version_sort_key / normalize_extension / normalize_formats。"""
from ez_co.plugins.api import FileKind, FormatSpec, normalize_extension, normalize_formats, version_sort_key


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


def _pairs(specs):
    return [(item.extension, item.kind) for item in specs]


def test_normalize_formats_string_pair():
    assert _pairs(normalize_formats([[".txt", "archive"]])) == [(".txt", FileKind.ARCHIVE)]


def test_normalize_formats_expands_tuple_first_list():
    assert _pairs(normalize_formats([[[".txt", ".log"], "archive"]])) == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_normalize_formats_expands_object_ext_list():
    assert _pairs(normalize_formats([{"ext": [".TXT", "log"], "kind": "archive"}])) == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_normalize_formats_object_ext_string():
    assert _pairs(normalize_formats([{"ext": "png", "kind": "image"}])) == [(".png", FileKind.IMAGE)]


def test_normalize_formats_ignores_extension_and_type_aliases():
    assert normalize_formats([{"extension": ".txt", "type": "archive"}]) == []
    assert normalize_formats([{"extension": ".txt", "kind": "archive"}]) == []
    assert normalize_formats([{"ext": ".txt", "type": "archive"}]) == []


def test_normalize_formats_does_not_treat_flat_list_as_many_exts():
    assert normalize_formats([[".txt", ".log", "archive"]]) == []


def test_normalize_formats_skips_blank_and_dedupes():
    assert _pairs(normalize_formats([[[".txt", "", ".txt", ".log"], "arch"]])) == [
        (".txt", FileKind.ARCHIVE),
        (".log", FileKind.ARCHIVE),
    ]


def test_normalize_formats_keeps_format_spec():
    specs = normalize_formats([FormatSpec(".PNG", FileKind.IMAGE)])
    assert _pairs(specs) == [(".png", FileKind.IMAGE)]


def test_normalize_formats_skips_invalid_entries_keeps_valid():
    assert _pairs(normalize_formats([{"no": "kind"}, [".txt", "archive"]])) == [
        (".txt", FileKind.ARCHIVE)
    ]
