"""本体 langs の差分・重複・ソート・抜けキー。`poetry run langs`"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

SCREEN_SECTIONS = ("ui", "settings", "dialogs", "actions", "messages")
META_KEYS = ("app_name", "language", "language_code")
REASON_DUPLICATE = "重複のため"
REASON_DISPLAY = "表示用のため"
REASON_LOG = "ログ用のため"
REASON_UNUSED = "未使用のため"
REASON_MISSING = "抜けのため"
REASON_NO_ENUM = "enumに無い"
GET_TEXT_RE = re.compile(r"""get_text\(\s*(['"])([^'"]+)\1""")
GET_LOG_TEXT_RE = re.compile(r"""get_log_text\(\s*(['"])([^'"]+)\1""")
EXPAND_KEY_RE = re.compile(
    r"""(?<![fF])(?<!DEFAULT )(['"])\{([A-Za-z0-9_.]+)\}\1(?=\s*[,\}\)\]]|\s*$)""",
    re.M,
)
QUOTED_LANG_RE = re.compile(
    r"""(['"])((?:ui|settings|dialogs|actions|logging|messages|app_name)(?:\.[A-Za-z0-9_]+)+)\1"""
)
DYNAMIC_GET_TEXT_RE = re.compile(r"get_text\(\s*f['\"]")
DYNAMIC_GET_LOG_RE = re.compile(r"get_log_text\(\s*f['\"]")
PLACEHOLDER_RE = re.compile(r"\{[^}]+\}")


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_ja(root: Path | None = None) -> Path:
    return (root or project_root()) / "src" / "ez_co" / "resources" / "langs" / "ja.json"


def default_en(root: Path | None = None) -> Path:
    return (root or project_root()) / "src" / "ez_co" / "resources" / "langs" / "en.json"


def default_apply_log(root: Path | None = None) -> Path:
    return (root or project_root()) / "tooling" / "logs" / "langs_apply.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, data: dict) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def flatten(obj: Any, prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(flatten(value, name))
            elif isinstance(value, str):
                out[name] = value
    return out


def _set_nested(data: dict, key: str, value: str) -> None:
    parts = key.split(".")
    cursor = data
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            cursor[part] = next_value
        cursor = next_value
    cursor[parts[-1]] = value


def _del_nested(data: dict, key: str) -> bool:
    parts = key.split(".")
    cursor = data
    stack: list[tuple[dict, str]] = []
    for part in parts[:-1]:
        next_value = cursor.get(part)
        if not isinstance(next_value, dict):
            return False
        stack.append((cursor, part))
        cursor = next_value
    if parts[-1] not in cursor:
        return False
    del cursor[parts[-1]]
    for parent, name in reversed(stack):
        child = parent.get(name)
        if isinstance(child, dict) and not child:
            del parent[name]
        else:
            break
    return True


def get_nested(data: dict, key: str) -> str | None:
    cursor: Any = data
    try:
        for part in key.split("."):
            cursor = cursor[part]
    except (KeyError, TypeError):
        return None
    return cursor if isinstance(cursor, str) else None


def sort_lang_data(data: dict) -> dict:
    sections = {key: value for key, value in data.items() if key not in META_KEYS}
    ordered: dict[str, Any] = {}
    for key in META_KEYS:
        if key in data:
            ordered[key] = data[key]
    for key in sorted(sections):
        value = sections[key]
        if isinstance(value, dict):
            ordered[key] = {item: value[item] for item in sorted(value)}
        else:
            ordered[key] = value
    return ordered


def key_diff(ja: dict[str, str], en: dict[str, str]) -> tuple[list[str], list[str]]:
    only_ja = sorted(set(ja) - set(en))
    only_en = sorted(set(en) - set(ja))
    return only_ja, only_en


def screen_items(flat: dict[str, str]) -> dict[str, str]:
    out = {}
    for key, value in flat.items():
        section = key.split(".", 1)[0]
        if section in SCREEN_SECTIONS or key in META_KEYS:
            out[key] = value
    return out


def duplicate_groups(flat: dict[str, str]) -> list[tuple[str, list[str]]]:
    by_value: dict[str, list[str]] = defaultdict(list)
    for key, value in screen_items(flat).items():
        if value.strip():
            by_value[value].append(key)
    groups = [(value, keys) for value, keys in by_value.items() if len(keys) > 1]
    groups.sort(key=lambda item: (-len(item[1]), item[1][0]))
    return groups


def _normalize(value: str) -> str:
    return PLACEHOLDER_RE.sub("{}", re.sub(r"\s+", " ", value)).strip().lower()


def similar_pairs(flat: dict[str, str], threshold: float) -> list[tuple[float, str, str, str, str]]:
    items = [(key, value, _normalize(value)) for key, value in screen_items(flat).items() if len(value) >= 2]
    pairs: list[tuple[float, str, str, str, str]] = []
    for index, (key_a, value_a, norm_a) in enumerate(items):
        if not norm_a:
            continue
        for key_b, value_b, norm_b in items[index + 1 :]:
            if not norm_b or norm_a == norm_b:
                if norm_a == norm_b and value_a == value_b:
                    continue
            contained = norm_a in norm_b or norm_b in norm_a
            ratio = SequenceMatcher(None, norm_a, norm_b).ratio()
            if contained and min(len(norm_a), len(norm_b)) >= 2:
                ratio = max(ratio, 0.91)
            if ratio >= threshold and key_a != key_b:
                pairs.append((ratio, key_a, key_b, value_a, value_b))
    pairs.sort(reverse=True)
    return pairs


def _builtin_action_ids() -> list[str]:
    try:
        from ez_co.enums.actions import ACTION_LIST
    except Exception:
        return []
    return list(ACTION_LIST)


def _iter_python_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return (path for path in root.rglob("*.py") if "__pycache__" not in path.parts)


def _plugin_lang_keys(plugin_dir: Path) -> set[str]:
    keys: set[str] = set()
    candidates = (
        plugin_dir / "resources" / "langs",
        plugin_dir / "langs",
        plugin_dir / "src" / "langs",
    )
    for folder in candidates:
        if not folder.is_dir():
            continue
        for name in ("ja.json", "en.json"):
            path = folder / name
            if path.is_file():
                keys.update(flatten(load_json(path)))
    return keys


@dataclass
class MissingReport:
    missing_host: list[tuple[str, str]] = field(default_factory=list)
    missing_plugin: list[tuple[str, str, str]] = field(default_factory=list)
    dynamic: list[tuple[str, str]] = field(default_factory=list)

    def has_failures(self) -> bool:
        return bool(self.missing_host or self.missing_plugin)


def _action_display_keys(action: str) -> list[str]:
    try:
        from ez_co.enums.actions import _ACTION_TEXT_KEYS
        preferred = _ACTION_TEXT_KEYS.get(action, f"ui.{action}")
    except Exception:
        preferred = f"ui.{action}"
    keys = [preferred, f"actions.{action}"]
    return list(dict.fromkeys(keys))


def _action_key_present(action: str, available: set[str]) -> bool:
    return any(key in available for key in _action_display_keys(action))


def collect_refs(py_path: Path) -> tuple[set[str], list[str], bool]:
    text = py_path.read_text(encoding="utf-8")
    keys = {item[1] for item in GET_TEXT_RE.findall(text)}
    keys.update(f"logging.{item[1]}" for item in GET_LOG_TEXT_RE.findall(text))
    keys.update(item[1] for item in EXPAND_KEY_RE.findall(text))
    keys.update(item[1] for item in QUOTED_LANG_RE.findall(text))
    needs_actions = "get_text(f\"actions." in text or "get_text(f'actions." in text
    dynamic: list[str] = []
    if DYNAMIC_GET_TEXT_RE.search(text) or DYNAMIC_GET_LOG_RE.search(text):
        if not needs_actions or DYNAMIC_GET_LOG_RE.search(text):
            dynamic.append("dynamic get_text/get_log_text")
        elif "f\"ui." in text or "f'ui." in text:
            dynamic.append("dynamic get_text/get_log_text")
    return keys, dynamic, needs_actions


def find_missing(root: Path, ja: dict[str, str], en: dict[str, str]) -> MissingReport:
    host_keys = set(ja) & set(en)
    report = MissingReport()
    src_root = root / "src"
    for path in _iter_python_files(src_root):
        keys, dynamic, needs_actions = collect_refs(path)
        rel = str(path.relative_to(root)).replace("\\", "/")
        for key in sorted(keys):
            if key not in host_keys:
                report.missing_host.append((rel, key))
        if needs_actions:
            for action in _builtin_action_ids():
                if not _action_key_present(action, host_keys):
                    report.missing_host.append((rel, f"actions.{action}"))
        for item in dynamic:
            report.dynamic.append((rel, item))
    plugins_root = root / "plugins"
    if plugins_root.is_dir():
        for plugin_dir in sorted(path for path in plugins_root.iterdir() if path.is_dir()):
            plugin_keys = _plugin_lang_keys(plugin_dir)
            available = host_keys | plugin_keys
            for path in _iter_python_files(plugin_dir):
                keys, dynamic, needs_actions = collect_refs(path)
                rel = str(path.relative_to(root)).replace("\\", "/")
                for key in sorted(keys):
                    if key not in available:
                        report.missing_plugin.append((plugin_dir.name, rel, key))
                if needs_actions:
                    for action in _builtin_action_ids():
                        if not _action_key_present(action, available):
                            report.missing_plugin.append((plugin_dir.name, rel, f"actions.{action}"))
                for item in dynamic:
                    report.dynamic.append((rel, item))
    return report


def _key_section(key: str) -> str:
    return key.split(".", 1)[0] if key else ""


def infer_reason(kind: str, old_key: str = "", new_key: str = "") -> str:
    """行動のざっくりした理由。`--reason` で上書きする。"""
    if kind == "merge":
        return REASON_DUPLICATE
    if kind == "move":
        new_sec = _key_section(new_key)
        old_sec = _key_section(old_key)
        if new_sec == "logging":
            return REASON_LOG
        if old_sec == "logging" or new_sec in SCREEN_SECTIONS or new_sec in META_KEYS:
            return REASON_DISPLAY
        return REASON_DISPLAY
    if kind == "delete":
        name = old_key.split(".", 1)[-1] if old_key.startswith("actions.") else ""
        if name:
            ids = _builtin_action_ids()
            if ids and name not in ids:
                return REASON_NO_ENUM
        return REASON_UNUSED
    if kind == "add":
        if _key_section(new_key) == "logging":
            return REASON_MISSING
        return REASON_DISPLAY
    return ""


def _apply_reason(record: "ApplyRecord", reason: str) -> "ApplyRecord":
    record.reason = reason or infer_reason(record.kind, record.old_key, record.new_key)
    return record


@dataclass
class ApplyRecord:
    kind: str
    old_key: str
    new_key: str = ""
    ja_old: str = ""
    ja_new: str = ""
    en_old: str = ""
    en_new: str = ""
    calls: list[str] = field(default_factory=list)
    reason: str = ""


def _cell_change(old: str, new: str) -> str:
    old = old.replace("|", "\\|").replace("\n", "\\n")
    new = new.replace("|", "\\|").replace("\n", "\\n")
    if not new or old == new:
        return old
    return f"{old} → {new}"


def render_apply_markdown(records: list[ApplyRecord]) -> str:
    groups: dict[str, list[ApplyRecord]] = defaultdict(list)
    order = ("Merge", "Move", "Delete", "Add")
    titles = {"merge": "Merge", "move": "Move", "delete": "Delete", "add": "Add"}
    for record in records:
        groups[titles.get(record.kind, record.kind.title())].append(record)
    lines = ["# langs apply", ""]
    for title in order:
        rows = groups.get(title) or []
        if not rows:
            continue
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"{len(rows)} 件")
        lines.append("")
        lines.append("| 旧キー | 新キー | 理由 | ja（旧 → 新） | en（旧 → 新） | 呼び出し |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for record in rows:
            calls = ", ".join(f"`{item}`" for item in record.calls) if record.calls else ""
            reason = record.reason or infer_reason(record.kind, record.old_key, record.new_key)
            lines.append(
                "| {old} | {new} | {reason} | {ja} | {en} | {calls} |".format(
                    old=record.old_key,
                    new=record.new_key,
                    reason=reason,
                    ja=_cell_change(record.ja_old, record.ja_new),
                    en=_cell_change(record.en_old, record.en_new),
                    calls=calls,
                )
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_apply_log(path: Path, records: list[ApplyRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else "# langs apply\n"
    parsed = _parse_apply_markdown(existing)
    parsed.extend(records)
    path.write_text(render_apply_markdown(parsed), encoding="utf-8")


def _parse_apply_markdown(text: str) -> list[ApplyRecord]:
    records: list[ApplyRecord] = []
    kind = ""
    has_reason = False
    kind_map = {"Merge": "merge", "Move": "move", "Delete": "delete", "Add": "add"}
    for line in text.splitlines():
        if line.startswith("## "):
            kind = kind_map.get(line[3:].strip(), "")
            continue
        if line.startswith("| 旧キー"):
            has_reason = "理由" in line
            continue
        if not line.startswith("|") or line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 4 or not kind:
            continue
        if has_reason and len(cells) >= 6:
            reason = cells[2]
            ja_old, ja_new = _split_change(cells[3])
            en_old, en_new = _split_change(cells[4])
            calls = [item.strip().strip("`") for item in cells[5].split(",") if item.strip()]
        else:
            reason = ""
            ja_old, ja_new = _split_change(cells[2])
            en_old, en_new = _split_change(cells[3])
            calls = []
            if len(cells) > 4:
                calls = [item.strip().strip("`") for item in cells[4].split(",") if item.strip()]
        records.append(
            ApplyRecord(
                kind=kind,
                old_key=cells[0],
                new_key=cells[1],
                ja_old=ja_old,
                ja_new=ja_new,
                en_old=en_old,
                en_new=en_new,
                calls=calls,
                reason=reason or infer_reason(kind, cells[0], cells[1]),
            )
        )
    return records


def _split_change(cell: str) -> tuple[str, str]:
    if " → " in cell:
        left, right = cell.split(" → ", 1)
        return left, right
    return cell, ""


def apply_move(ja: dict, en: dict, old_key: str, new_key: str, reason: str = "") -> ApplyRecord:
    ja_old = get_nested(ja, old_key) or ""
    en_old = get_nested(en, old_key) or ""
    if ja_old:
        _set_nested(ja, new_key, ja_old)
    if en_old:
        _set_nested(en, new_key, en_old)
    _del_nested(ja, old_key)
    _del_nested(en, old_key)
    return _apply_reason(
        ApplyRecord(
            kind="move",
            old_key=old_key,
            new_key=new_key,
            ja_old=ja_old,
            ja_new=ja_old,
            en_old=en_old,
            en_new=en_old,
        ),
        reason,
    )


def apply_merge(ja: dict, en: dict, old_key: str, new_key: str, reason: str = "") -> ApplyRecord:
    ja_old = get_nested(ja, old_key) or ""
    en_old = get_nested(en, old_key) or ""
    ja_new = get_nested(ja, new_key) or ""
    en_new = get_nested(en, new_key) or ""
    _del_nested(ja, old_key)
    _del_nested(en, old_key)
    return _apply_reason(
        ApplyRecord(
            kind="merge",
            old_key=old_key,
            new_key=new_key,
            ja_old=ja_old,
            ja_new=ja_new,
            en_old=en_old,
            en_new=en_new,
        ),
        reason,
    )


def apply_delete(ja: dict, en: dict, old_key: str, reason: str = "") -> ApplyRecord:
    ja_old = get_nested(ja, old_key) or ""
    en_old = get_nested(en, old_key) or ""
    _del_nested(ja, old_key)
    _del_nested(en, old_key)
    return _apply_reason(ApplyRecord(kind="delete", old_key=old_key, ja_old=ja_old, en_old=en_old), reason)


def apply_add(ja: dict, en: dict, new_key: str, ja_text: str, en_text: str, reason: str = "") -> ApplyRecord:
    _set_nested(ja, new_key, ja_text)
    _set_nested(en, new_key, en_text)
    return _apply_reason(
        ApplyRecord(
            kind="add",
            old_key="",
            new_key=new_key,
            ja_new=ja_text,
            en_new=en_text,
        ),
        reason,
    )


def _cmd_diff(args: argparse.Namespace) -> int:
    ja = flatten(load_json(Path(args.ja)))
    en = flatten(load_json(Path(args.en)))
    only_ja, only_en = key_diff(ja, en)
    print(f"only ja: {len(only_ja)}")
    for key in only_ja:
        print(f"  JA {key}")
    print(f"only en: {len(only_en)}")
    for key in only_en:
        print(f"  EN {key}")
    return 1 if only_ja or only_en else 0


def _cmd_dupes(args: argparse.Namespace) -> int:
    groups = duplicate_groups(flatten(load_json(Path(args.ja))))
    print(f"groups: {len(groups)}")
    for value, keys in groups:
        print(f"\n[{len(keys)}] {value}")
        for key in keys:
            print(f"  {key}")
    return 0


def _cmd_similar(args: argparse.Namespace) -> int:
    pairs = similar_pairs(flatten(load_json(Path(args.ja))), args.threshold)
    print(f"pairs: {len(pairs)}")
    for ratio, key_a, key_b, value_a, value_b in pairs:
        print(f"{ratio:.2f} {key_a} | {key_b}")
        print(f"     {value_a}")
        print(f"     {value_b}")
    return 0


def _cmd_sort(args: argparse.Namespace) -> int:
    for path in (Path(args.ja), Path(args.en)):
        data = sort_lang_data(load_json(path))
        if args.write:
            dump_json(path, data)
            print(f"wrote {path}")
        else:
            print(path)
    return 0


def _cmd_missing(args: argparse.Namespace) -> int:
    root = Path(args.root)
    ja = flatten(load_json(Path(args.ja)))
    en = flatten(load_json(Path(args.en)))
    report = find_missing(root, ja, en)
    print(f"missing host: {len(report.missing_host)}")
    for rel, key in report.missing_host:
        print(f"  {rel} {key}")
    print(f"missing plugin: {len(report.missing_plugin)}")
    for plugin, rel, key in report.missing_plugin:
        print(f"  {plugin} {rel} {key}")
    if report.dynamic:
        print(f"dynamic (review): {len(report.dynamic)}")
        for rel, item in report.dynamic:
            print(f"  {rel} {item}")
    return 1 if report.has_failures() else 0


def _cmd_check(args: argparse.Namespace) -> int:
    diff_rc = _cmd_diff(args)
    missing_rc = _cmd_missing(args)
    return 1 if diff_rc or missing_rc else 0


def _save_langs(args: argparse.Namespace, ja: dict, en: dict, record: ApplyRecord) -> None:
    if args.calls:
        record.calls = [item.strip() for item in args.calls.split(",") if item.strip()]
    if getattr(args, "reason", ""):
        record.reason = args.reason
    dump_json(Path(args.ja), ja)
    dump_json(Path(args.en), en)
    write_apply_log(Path(args.log), [record])
    print(f"{record.kind} {record.old_key} -> {record.new_key}".strip())


def _cmd_move(args: argparse.Namespace) -> int:
    ja = load_json(Path(args.ja))
    en = load_json(Path(args.en))
    _save_langs(args, ja, en, apply_move(ja, en, args.old, args.new, args.reason))
    return 0


def _cmd_merge(args: argparse.Namespace) -> int:
    ja = load_json(Path(args.ja))
    en = load_json(Path(args.en))
    _save_langs(args, ja, en, apply_merge(ja, en, args.old, args.new, args.reason))
    return 0


def _cmd_delete(args: argparse.Namespace) -> int:
    ja = load_json(Path(args.ja))
    en = load_json(Path(args.en))
    _save_langs(args, ja, en, apply_delete(ja, en, args.old, args.reason))
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    ja = load_json(Path(args.ja))
    en = load_json(Path(args.en))
    record = apply_add(ja, en, args.new, args.ja_text, args.en_text, args.reason)
    _save_langs(args, ja, en, record)
    return 0


def _add_lang_paths(parser: argparse.ArgumentParser) -> None:
    root = project_root()
    parser.add_argument("--ja", default=str(default_ja(root)))
    parser.add_argument("--en", default=str(default_en(root)))


def _add_apply_paths(parser: argparse.ArgumentParser) -> None:
    _add_lang_paths(parser)
    parser.add_argument("--log", default=str(default_apply_log()))
    parser.add_argument("--calls", default="")
    parser.add_argument("--reason", default="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="本体 langs の差分・重複・ソート・抜け確認")
    sub = parser.add_subparsers(dest="command", required=True)

    diff = sub.add_parser("diff")
    _add_lang_paths(diff)
    diff.set_defaults(func=_cmd_diff)

    dupes = sub.add_parser("dupes")
    _add_lang_paths(dupes)
    dupes.set_defaults(func=_cmd_dupes)

    similar = sub.add_parser("similar")
    _add_lang_paths(similar)
    similar.add_argument("--threshold", type=float, default=0.9)
    similar.set_defaults(func=_cmd_similar)

    sort = sub.add_parser("sort")
    _add_lang_paths(sort)
    sort.add_argument("--write", action="store_true")
    sort.set_defaults(func=_cmd_sort)

    missing = sub.add_parser("missing")
    _add_lang_paths(missing)
    missing.add_argument("--root", default=str(project_root()))
    missing.set_defaults(func=_cmd_missing)

    check = sub.add_parser("check")
    _add_lang_paths(check)
    check.add_argument("--root", default=str(project_root()))
    check.set_defaults(func=_cmd_check)

    move = sub.add_parser("move")
    _add_apply_paths(move)
    move.add_argument("old")
    move.add_argument("new")
    move.set_defaults(func=_cmd_move)

    merge = sub.add_parser("merge")
    _add_apply_paths(merge)
    merge.add_argument("old")
    merge.add_argument("new")
    merge.set_defaults(func=_cmd_merge)

    delete = sub.add_parser("delete")
    _add_apply_paths(delete)
    delete.add_argument("old")
    delete.set_defaults(func=_cmd_delete)

    add = sub.add_parser("add")
    _add_apply_paths(add)
    add.add_argument("new")
    add.add_argument("--ja-text", required=True)
    add.add_argument("--en-text", required=True)
    add.set_defaults(func=_cmd_add)
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    raise SystemExit(args.func(args))


if __name__ == "__main__":
    main()
