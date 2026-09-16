"""plugins/ の展開フォルダを dist-sample-plugins/ の配布 ZIP にする。`poetry run pack-plugins`"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from ez_co.plugins.api import HOST_API_VERSION
from ez_co.plugins.manifest import KNOWN_PERMISSIONS, parse_manifest


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def iter_plugin_dirs(plugins_root: Path) -> list[Path]:
    if not plugins_root.is_dir():
        return []
    found = [
        path
        for path in plugins_root.iterdir()
        if path.is_dir() and (path / "manifest.json").is_file()
    ]
    return sorted(found, key=lambda item: item.name.lower())


def _include_file(path: Path, src: Path) -> bool:
    if not path.is_file():
        return False
    return "__pycache__" not in path.relative_to(src).parts


def zip_name_for(folder_name: str, version: str) -> str:
    return f"{folder_name}-{version}.zip"


def _lint_version(version: str) -> None:
    try:
        from packaging.version import InvalidVersion, Version
    except ImportError as exc:
        raise ValueError("packaging が無く version を検証できない") from exc
    try:
        Version(version)
    except InvalidVersion as exc:
        raise ValueError(f"manifest.version is not a valid version: {version}") from exc


def _lint_permissions(raw) -> None:
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise ValueError("manifest.permissions must be an object")
    for key, value in raw.items():
        name = str(key or "").strip()
        if not name:
            raise ValueError("manifest.permissions has an empty key")
        if name not in KNOWN_PERMISSIONS:
            raise ValueError(f"manifest.permissions unknown key: {name}")
        if not isinstance(value, bool):
            raise ValueError(f"manifest.permissions.{name} must be a bool")


def _lint_entry_file(src: Path, entry_module: str) -> None:
    rel = Path(*entry_module.split("."))
    candidates = (src / "src" / rel.with_suffix(".py"), src / "src" / rel / "__init__.py")
    if not any(path.is_file() for path in candidates):
        raise ValueError(f"entry module not found: src/{rel.as_posix()}.py")


def lint_plugin_dir(src: Path):
    """manifest.json の JSON / 契約 / バージョン / 権限を検証する。"""
    manifest_path = src / "manifest.json"
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"manifest.json を読めない: {exc}") from exc
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"manifest.json の構文エラー: {exc}") from exc
    _lint_permissions(data.get("permissions") if isinstance(data, dict) else None)
    manifest = parse_manifest(data)
    _lint_version(manifest.version)
    if manifest.api_version != HOST_API_VERSION:
        raise ValueError(
            f"manifest.api_version must be {HOST_API_VERSION}: {manifest.api_version}"
        )
    _lint_entry_file(src, manifest.entry_module)
    return manifest


def pack_plugin_dir(src: Path, dest: Path) -> Path:
    """フォルダ直下を ZIP ルートにする。余分な親フォルダは挟まない。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(f".{dest.name}.tmp")
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(src.rglob("*")):
                if not _include_file(path, src):
                    continue
                archive.write(path, path.relative_to(src).as_posix())
        tmp.replace(dest)
    except Exception:
        if tmp.is_file():
            tmp.unlink()
        raise
    return dest


@dataclass
class PackReport:
    written: list[Path] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return len(self.written)

    @property
    def fail_count(self) -> int:
        return len(self.failed)


def _log_error(name: str, message: str) -> None:
    print(f"ERROR {name}: {message}", file=sys.stderr)


def pack_plugins(root: Path, names: list[str] | None = None) -> PackReport:
    plugins_root = root / "plugins"
    dest_root = root / "dist-sample-plugins"
    dirs = iter_plugin_dirs(plugins_root)
    report = PackReport()
    if names:
        wanted = {name.lower() for name in names}
        dirs = [path for path in dirs if path.name.lower() in wanted]
        missing = wanted - {path.name.lower() for path in dirs}
        for name in sorted(missing):
            message = "プラグインフォルダが見つかりません"
            report.failed.append((name, message))
            _log_error(name, message)
    if not dirs and not report.failed:
        message = f"pack 対象がありません: {plugins_root}"
        report.failed.append((str(plugins_root), message))
        _log_error(plugins_root.name, message)
        return report
    for src in dirs:
        try:
            manifest = lint_plugin_dir(src)
            dest = dest_root / zip_name_for(src.name, manifest.version)
            pack_plugin_dir(src, dest)
        except Exception as exc:
            report.failed.append((src.name, str(exc)))
            _log_error(src.name, str(exc))
            continue
        report.written.append(dest)
        print(f"wrote {dest.relative_to(root)}")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="plugins/ の manifest.json 付きフォルダを dist-sample-plugins/<名前>-<version>.zip にする"
    )
    parser.add_argument(
        "names",
        nargs="*",
        help="フォルダ名（省略時は全部）。例: example_zip",
    )
    args = parser.parse_args()
    root = _project_root()
    print("=== プラグイン ZIP ===")
    print(f"Project root: {root}")
    report = pack_plugins(root, args.names or None)
    print(f"成功: {report.success_count} 件 / 失敗: {report.fail_count} 件")
    if report.fail_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
