"""対象: tooling.langs_cli"""
import json
from pathlib import Path

import pytest

from tooling.langs_cli import (
    ApplyRecord,
    apply_delete,
    apply_merge,
    apply_move,
    default_apply_log,
    dump_json,
    duplicate_groups,
    find_missing,
    flatten,
    infer_reason,
    key_diff,
    main,
    render_apply_markdown,
    sort_lang_data,
    write_apply_log,
)


def test_key_diff_lists_only_one_side(tmp_path: Path):
    """両側にあるキーが差分に残り、片方だけにあるキーが落ちる。"""
    ja = {"ui": {"a": "あ", "b": "い"}}
    en = {"ui": {"a": "A", "c": "C"}}
    only_ja, only_en = key_diff(flatten(ja), flatten(en))
    assert only_ja == ["ui.b"]
    assert only_en == ["ui.c"]


def test_sort_lang_data_keeps_meta_then_sections():
    """メタ情報がセクションより後ろになり、セクション内のキーが名前順にならない。"""
    data = {
        "language_code": "ja",
        "ui": {"z": "Z", "a": "A"},
        "app_name": "EzCo",
        "language": "日本語",
        "settings": {"b": "B"},
    }
    ordered = sort_lang_data(data)
    assert list(ordered) == ["app_name", "language", "language_code", "settings", "ui"]
    assert list(ordered["ui"]) == ["a", "z"]


def test_apply_move_and_merge_write_markdown_log(tmp_path: Path):
    """移動と統合の節か理由が欠け、移動先の値が残らないか統合元のキーが残る。"""
    ja = {"settings": {"title": "設定", "note": "ログ"}, "ui": {"settings": "設定"}}
    en = {"settings": {"title": "Settings", "note": "log"}, "ui": {"settings": "Settings"}}
    record_move = apply_move(ja, en, "settings.note", "logging.note")
    record_merge = apply_merge(ja, en, "settings.title", "ui.settings")
    log = tmp_path / "langs_apply.md"
    write_apply_log(log, [record_move, record_merge])
    text = log.read_text(encoding="utf-8")
    assert "## Merge" in text
    assert "## Move" in text
    assert "重複のため" in text
    assert "ログ用のため" in text
    assert "settings.title" in text
    assert "ui.settings" in text
    assert "logging.note" in text
    assert flatten(ja)["logging.note"] == "ログ"
    assert "settings.title" not in flatten(ja)


def test_render_apply_markdown_has_table_headers():
    """適用ログの表から旧キー・新キー・理由が欠け、統合理由か呼び出し元のファイル名が無い。"""
    text = render_apply_markdown(
        [
            ApplyRecord(
                kind="merge",
                old_key="settings.title",
                new_key="ui.settings",
                ja_old="設定",
                ja_new="設定",
                en_old="Settings",
                en_new="Settings",
                calls=["settings_dialog.py"],
            )
        ]
    )
    assert "| 旧キー | 新キー | 理由 |" in text
    assert "重複のため" in text
    assert "`settings_dialog.py`" in text


def test_find_missing_host_and_plugin(tmp_path: Path):
    """本体の既存キーが欠落になり、プラグインの未定義キーが落ち、f文字列の穴が欠落になる。"""
    (tmp_path / "src" / "ez_co").mkdir(parents=True)
    (tmp_path / "src" / "ez_co" / "app.py").write_text(
        'from ez_co.utils.language_manager import get_text, get_log_text\n'
        'get_text("ui.hello")\n'
        'get_log_text("started")\n'
        'rows = ("ui.hello",)\n',
        encoding="utf-8",
    )
    plugin = tmp_path / "plugins" / "demo"
    (plugin / "resources" / "langs").mkdir(parents=True)
    (plugin / "src").mkdir(parents=True)
    dump_json(plugin / "resources" / "langs" / "ja.json", {"title": "題"})
    dump_json(plugin / "resources" / "langs" / "en.json", {"title": "Title"})
    (plugin / "src" / "plugin.py").write_text(
        'get_text("title")\nget_text("missing_plugin_key")\nlabel = "{title}"\n'
        'text = f"{message}"\nlink = f\'<a href="{homepage}">{homepage}</a>\'\n',
        encoding="utf-8",
    )
    ja = {"ui": {"hello": "こんにちは"}, "logging": {"started": "開始"}}
    en = {"ui": {"hello": "Hello"}, "logging": {"started": "started"}}
    report = find_missing(tmp_path, flatten(ja), flatten(en))
    assert report.missing_host == []
    assert report.missing_plugin == [
        ("demo", "plugins/demo/src/plugin.py", "missing_plugin_key")
    ]


def test_duplicate_groups_across_sections():
    """別セクションの同じ日本語が1組にならず、違う文まで同じ組に入る。"""
    groups = duplicate_groups(
        flatten({"ui": {"settings": "設定", "file": "ファイル"}, "settings": {"title": "設定"}})
    )
    assert len(groups) == 1
    value, keys = groups[0]
    assert value == "設定"
    assert set(keys) == {"settings.title", "ui.settings"}


def test_find_missing_action_fstring_accepts_ui_or_actions(tmp_path, monkeypatch):
    """actions の f文字列が、ui か actions のどちらかにあっても欠落になる。"""
    monkeypatch.setattr(
        "tooling.langs_cli._builtin_action_ids",
        lambda: ["next_page", "first_page", "close_app"],
    )
    (tmp_path / "src" / "ez_co").mkdir(parents=True)
    (tmp_path / "src" / "ez_co" / "actions.py").write_text(
        'get_text(f"actions.{name}")\n',
        encoding="utf-8",
    )
    ja = {
        "ui": {"next_page": "次", "exit": "終了"},
        "actions": {"first_page": "最初"},
    }
    en = {
        "ui": {"next_page": "Next", "exit": "Exit"},
        "actions": {"first_page": "First"},
    }
    report = find_missing(tmp_path, flatten(ja), flatten(en))
    assert report.missing_host == []


def test_default_apply_log_is_under_tooling_logs():
    """既定の適用ログが tooling/logs/langs_apply.md 以外になる。"""
    path = default_apply_log()
    assert path.name == "langs_apply.md"
    assert path.parent.name == "logs"
    assert path.parent.parent.name == "tooling"


def test_write_apply_log_creates_logs_dir(tmp_path: Path):
    """ログディレクトリが無いと書けず、追加キーか表示用の理由が欠ける。"""
    log = tmp_path / "tooling" / "logs" / "langs_apply.md"
    write_apply_log(log, [ApplyRecord(kind="add", old_key="", new_key="ui.hello")])
    assert log.is_file()
    assert "ui.hello" in log.read_text(encoding="utf-8")
    assert "表示用のため" in log.read_text(encoding="utf-8")


def test_infer_reason_by_kind(monkeypatch):
    """操作の種類と移動先から、重複・ログ用・表示用・未使用・enumに無い・抜けの理由が分かれるのに失敗する。"""
    monkeypatch.setattr("tooling.langs_cli._builtin_action_ids", lambda: ["next_page"])
    assert infer_reason("merge", "settings.title", "ui.settings") == "重複のため"
    assert infer_reason("move", "settings.note", "logging.note") == "ログ用のため"
    assert infer_reason("move", "logging.warn", "settings.warn") == "表示用のため"
    assert infer_reason("delete", "messages.loading") == "未使用のため"
    assert infer_reason("delete", "actions.toggle_product_info_dock") == "enumに無い"
    assert infer_reason("add", "", "logging.file_handler_x") == "抜けのため"
    assert infer_reason("add", "", "ui.min_scale_toggle") == "表示用のため"


def test_apply_delete_reason_can_be_overridden():
    """削除理由が呼び出し側の文言にならず、既定の理由にもできない。"""
    ja = {"messages": {"loading": "読み込み中..."}}
    en = {"messages": {"loading": "Loading..."}}
    record = apply_delete(ja, en, "messages.loading", reason="未使用のため")
    assert record.reason == "未使用のため"
    other = apply_delete({"ui": {"orphan": "x"}}, {"ui": {"orphan": "x"}}, "ui.orphan", reason="置き場が無い")
    assert other.reason == "置き場が無い"


def test_parse_keeps_reason_column(tmp_path: Path):
    """空の記録で書き直すと重複理由が消え、書き直し前のログから理由列の見出しが欠ける。"""
    log = tmp_path / "langs_apply.md"
    write_apply_log(
        log,
        [
            apply_merge(
                {"settings": {"title": "設定"}, "ui": {"settings": "設定"}},
                {"settings": {"title": "Settings"}, "ui": {"settings": "Settings"}},
                "settings.title",
                "ui.settings",
            )
        ],
    )
    text = log.read_text(encoding="utf-8")
    write_apply_log(log, [])
    assert "重複のため" in log.read_text(encoding="utf-8")
    assert "| 理由 |" in text


def test_langs_check_exits_1_on_key_diff(tmp_path: Path):
    """日英のキーがずれている check が終了コード 1 以外で終わる。"""
    dump_json(tmp_path / "ja.json", {"ui": {"a": "あ"}})
    dump_json(tmp_path / "en.json", {"ui": {"b": "B"}})
    (tmp_path / "src").mkdir()
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "check",
                "--ja",
                str(tmp_path / "ja.json"),
                "--en",
                str(tmp_path / "en.json"),
                "--root",
                str(tmp_path),
            ]
        )
    assert exc.value.code == 1
