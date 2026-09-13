"""データフォルダ plugins/ の掃引と拡張子優先度の解決。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from ez_co.enums.archives import ArchiveInfo
from ez_co.enums.images import ImageInfo
from ez_co.plugins.api import (
    BUILTIN_PROVIDER_ID,
    SKIP_PROVIDER_ID,
    FileKind,
    FormatSpec,
    make_provider_id,
    normalize_extension,
    parse_provider_id,
    version_sort_key,
)
from ez_co.plugins.backends import DllBackend, ZipPythonBackend
from ez_co.plugins.host import PluginHost
from ez_co.plugins.manifest import PluginManifest
from ez_co.utils.error_logger import report_error
from ez_co.utils.language_manager import get_log_text
from ez_co.utils.data_location import get_data_root

logger = logging.getLogger(__name__)

_manager: Optional["PluginManager"] = None
SOURCE_NONE = SKIP_PROVIDER_ID


@dataclass
class PluginCandidate:
    path: Path
    plugin_id: str
    name: str
    version: str


@dataclass
class SkippedPlugin:
    path: Path
    plugin_id: str
    name: str
    version: str
    reason: str
    selected_name: Optional[str] = None


def sort_conflict_candidates(candidates: list[PluginCandidate]) -> list[PluginCandidate]:
    items = list(candidates)
    items.sort(key=lambda item: item.path.name.lower())
    items.sort(key=lambda item: 0 if item.path.is_dir() else 1)
    items.sort(key=lambda item: version_sort_key(item.version), reverse=True)
    return items


def candidate_names(candidates: list[PluginCandidate]) -> list[str]:
    return sorted(item.path.name for item in candidates)


def source_choice_entry(value) -> Optional[dict]:
    if isinstance(value, str):
        source = value.strip()
        if not source:
            return None
        return {"source": source, "seen": []}
    if not isinstance(value, dict):
        return None
    source = str(value.get("source") or "").strip()
    if not source:
        return None
    seen = value.get("seen")
    if not isinstance(seen, list):
        seen = []
    return {"source": source, "seen": [str(item) for item in seen]}


def source_choice_is_current(entry, candidates: list[PluginCandidate]) -> bool:
    parsed = source_choice_entry(entry)
    if parsed is None:
        return False
    if parsed["source"] == SOURCE_NONE:
        return True
    return parsed["source"] in candidate_names(candidates)


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    instance: object
    zip_path: Path
    formats: list[FormatSpec]
    error: Optional[str] = None
    ui_active: bool = False
    _archive: object = field(default=None, repr=False)

    @property
    def has_formats(self) -> bool:
        return bool(self.formats)

    @property
    def has_sidebar(self) -> bool:
        setup = getattr(self.instance, "setup", None)
        if callable(setup):
            return True
        host = getattr(self.instance, "host", None)
        if host is not None and hasattr(host, "has_pending_sidebars"):
            return bool(host.has_pending_sidebars())
        return False

    @property
    def plugin_id(self) -> str:
        return self.manifest.plugin_id

    @property
    def version(self) -> str:
        return self.manifest.version

    @property
    def provider_id(self) -> str:
        return make_provider_id(self.manifest.plugin_id, self.manifest.version)

    @property
    def name(self) -> str:
        return self.manifest.name

    def offers(self, extension: str) -> Optional[FileKind]:
        ext = normalize_extension(extension)
        for spec in self.formats:
            if spec.extension == ext:
                return spec.kind
        return None

    def get_file_count(self, file_path: str) -> int:
        try:
            return int(self.instance.get_file_count(file_path))
        except Exception as exc:
            report_error("get_file_count", exc, plugin_id=self.plugin_id)
            return 0

    def list_entries(self, file_path: str) -> list[str]:
        try:
            names = self.instance.list_entries(file_path)
            return [str(name) for name in names]
        except Exception as exc:
            report_error("list_entries", exc, plugin_id=self.plugin_id)
            return []

    def read_entry(self, file_path: str, index: int):
        try:
            return self.instance.read_entry(file_path, index)
        except Exception as exc:
            report_error("read_entry", exc, plugin_id=self.plugin_id)
            return None


@dataclass(frozen=True)
class HandlerDecision:
    provider_id: str
    kind: Optional[FileKind]
    plugin: Optional[LoadedPlugin] = None

    @property
    def is_plugin(self) -> bool:
        return self.plugin is not None

    @property
    def is_skipped(self) -> bool:
        return self.provider_id == SKIP_PROVIDER_ID

    @property
    def is_archive(self) -> bool:
        return self.kind == FileKind.ARCHIVE

    @property
    def is_image(self) -> bool:
        return self.kind == FileKind.IMAGE


@dataclass
class ExtensionProviderRow:
    extension: str
    kind: FileKind
    providers: list[tuple[str, str]]
    selected: str


def plugins_dir() -> Path:
    return get_data_root() / "plugins"


def builtin_kind_for_extension(extension: str) -> Optional[FileKind]:
    ext = normalize_extension(extension)
    if ext in ImageInfo.get_all_extensions():
        return FileKind.IMAGE
    for archive_ext in ArchiveInfo.get_all_extensions():
        if ext == archive_ext:
            return FileKind.ARCHIVE
    return None


def extension_for_path(file_path: str) -> str:
    name = Path(file_path).name.lower()
    archive_exts = sorted(ArchiveInfo.get_all_extensions(), key=len, reverse=True)
    for ext in archive_exts:
        if name.endswith(ext):
            return ext
    return normalize_extension(Path(file_path).suffix)


def is_legacy_archive_disabled(config, extension: str) -> bool:
    """旧アーカイブ設定（archive.enabled / 種類キー）で無効なら True。"""
    if config is None:
        return False
    archive = getattr(config, "archive", None) or {}
    if not isinstance(archive, dict):
        return False
    ext = normalize_extension(extension)
    archive_type = ArchiveInfo.get_archive_type_by_extension(ext)
    if archive_type is None:
        archive_type = ArchiveInfo.get_archive_type_by_path(f"file{ext}")
    if archive_type is None:
        return False
    if not archive.get("enabled", True):
        return True
    return not archive.get(ArchiveInfo.get_config_key(archive_type), True)


class PluginManager:
    def __init__(self):
        self.plugins: list[LoadedPlugin] = []
        self.failed: list[tuple[Path, str]] = []
        self.skipped: list[SkippedPlugin] = []
        self.candidates: list[PluginCandidate] = []
        self._backends = (ZipPythonBackend(), DllBackend())
        self._discovered = False
        self._loaded = False
        self.host = PluginHost()

    def scan(self, directory: Optional[Path] = None, config=None) -> None:
        self.discover(directory)
        self.load_selected(config)

    def discover(self, directory: Optional[Path] = None) -> None:
        if self.plugins:
            self.unload_loaded()
        directory = directory or plugins_dir()
        self.plugins.clear()
        self.failed.clear()
        self.skipped.clear()
        self.candidates.clear()
        self._loaded = False
        if not directory.is_dir():
            logger.info(get_log_text("plugin_dir_missing", path=directory))
            self._discovered = True
            return
        logger.info(get_log_text("plugin_scan_start", path=directory))
        for path in sorted(directory.iterdir(), key=lambda item: (item.is_file(), item.name.lower())):
            backend = next((item for item in self._backends if item.can_load(path)), None)
            if backend is None:
                continue
            peek = getattr(backend, "peek", None)
            if peek is None:
                try:
                    if backend.load(path, host=self.host) is None:
                        continue
                except Exception as exc:
                    self.failed.append((path, str(exc)))
                    logger.warning(get_log_text("plugin_load_failed", path=path, error=exc))
                    report_error("load", exc, plugin_id=str(path.name))
                continue
            try:
                peeked = peek(path)
                self.candidates.append(
                    PluginCandidate(
                        path=path,
                        plugin_id=str(peeked.get("id") or "").strip(),
                        name=str(peeked.get("name") or path.name).strip() or path.name,
                        version=str(peeked.get("version") or "").strip(),
                    )
                )
            except Exception as exc:
                self.failed.append((path, str(exc)))
                logger.warning(get_log_text("plugin_load_failed", path=path, error=exc))
                report_error("load", exc, plugin_id=str(path.name))
        self._discovered = True

    def candidate_groups(self) -> dict[str, list[PluginCandidate]]:
        groups: dict[str, list[PluginCandidate]] = {}
        for item in self.candidates:
            if not item.plugin_id:
                continue
            groups.setdefault(item.plugin_id, []).append(item)
        return groups

    def conflict_groups(self) -> dict[str, list[PluginCandidate]]:
        return {
            plugin_id: sort_conflict_candidates(items)
            for plugin_id, items in self.candidate_groups().items()
            if len(items) > 1
        }

    def unresolved_groups(self, config=None) -> dict[str, list[PluginCandidate]]:
        choices = self._source_choice_map(config)
        unresolved: dict[str, list[PluginCandidate]] = {}
        for plugin_id, items in self.conflict_groups().items():
            if not source_choice_is_current(choices.get(plugin_id), items):
                unresolved[plugin_id] = items
        return unresolved

    def current_source_choices(self, config=None) -> dict[str, str]:
        stored = self._source_choice_map(config)
        result: dict[str, str] = {}
        for plugin_id, items in self.conflict_groups().items():
            entry = source_choice_entry(stored.get(plugin_id))
            if source_choice_is_current(entry, items):
                result[plugin_id] = entry["source"]
                continue
            loaded = next((plugin for plugin in self.plugins if plugin.plugin_id == plugin_id), None)
            if loaded is not None:
                result[plugin_id] = loaded.zip_path.name
        return result

    def record_choices(self, choices: dict[str, str], config) -> None:
        if config is None:
            return
        stored = dict(getattr(config, "plugins", {}).get("source_choice") or {})
        groups = self.candidate_groups()
        for plugin_id, source in choices.items():
            items = groups.get(plugin_id) or []
            stored[plugin_id] = {
                "source": str(source or SOURCE_NONE).strip() or SOURCE_NONE,
                "seen": candidate_names(items),
            }
        config.plugins["source_choice"] = stored

    def load_selected(self, config=None) -> None:
        if self._loaded:
            return
        self.plugins.clear()
        self.skipped.clear()
        choices = self._source_choice_map(config)
        for plugin_id, items in self.candidate_groups().items():
            if len(items) == 1:
                self._load_candidate(items[0])
                continue
            entry = source_choice_entry(choices.get(plugin_id))
            source = entry["source"] if source_choice_is_current(entry, items) else SOURCE_NONE
            if source == SOURCE_NONE:
                for item in items:
                    self._skip_candidate(item, "not_selected", None)
                continue
            selected = next((item for item in items if item.path.name == source), None)
            if selected is None:
                for item in items:
                    self._skip_candidate(item, "not_selected", None)
                continue
            self._load_candidate(selected)
            for item in items:
                if item.path != selected.path:
                    self._skip_candidate(item, "duplicate", selected.path.name)
        self._loaded = True

    def unload_loaded(self) -> None:
        for plugin in list(self.plugins):
            self._deactivate_plugin(plugin)
            archive = plugin._archive
            if archive is not None and hasattr(archive, "close"):
                try:
                    archive.close()
                except Exception:
                    pass
        self.plugins.clear()
        self.skipped.clear()
        self._loaded = False

    def reload_selected(self, config=None, directory: Optional[Path] = None) -> None:
        self.discover(directory)
        self.load_selected(config)

    def _source_choice_map(self, config) -> dict:
        if config is None:
            return {}
        raw = getattr(config, "plugins", {}).get("source_choice") or {}
        if not isinstance(raw, dict):
            return {}
        return raw

    def _backend_for(self, path: Path):
        return next((item for item in self._backends if item.can_load(path)), None)

    def _load_candidate(self, item: PluginCandidate) -> None:
        backend = self._backend_for(item.path)
        if backend is None:
            return
        try:
            loaded = backend.load(item.path, host=self.host)
            if loaded is None:
                return
            manifest, instance, _root, archive = loaded
            formats = list(getattr(instance, "_ezco_formats", []))
            if not formats:
                supported = getattr(instance, "supported_formats", None)
                if callable(supported):
                    from ez_co.plugins.api import normalize_formats
                    formats = normalize_formats(supported())
            plugin = LoadedPlugin(
                manifest=manifest,
                instance=instance,
                zip_path=item.path,
                formats=formats,
                _archive=archive,
            )
            self.plugins.append(plugin)
            logger.info(
                get_log_text(
                    "plugin_loaded",
                    plugin_id=plugin.plugin_id,
                    name=plugin.name,
                    version=plugin.manifest.version,
                    path=item.path,
                )
            )
        except Exception as exc:
            self.failed.append((item.path, str(exc)))
            logger.warning(get_log_text("plugin_load_failed", path=item.path, error=exc))
            report_error("load", exc, plugin_id=str(item.path.name))

    def _skip_candidate(self, item: PluginCandidate, reason: str, selected_name: Optional[str]) -> None:
        self.skipped.append(
            SkippedPlugin(
                path=item.path,
                plugin_id=item.plugin_id,
                name=item.name,
                version=item.version,
                reason=reason,
                selected_name=selected_name,
            )
        )
        log_key = "plugin_skipped_duplicate" if reason == "duplicate" else "plugin_skipped_not_selected"
        logger.info(
            get_log_text(
                log_key,
                plugin_id=item.plugin_id,
                path=item.path,
                selected=selected_name or SOURCE_NONE,
            )
        )

    def is_enabled(self, plugin_id: str, config=None) -> bool:
        if config is None:
            return True
        enabled = dict(getattr(config, "plugins", {}).get("enabled") or {})
        if plugin_id not in enabled:
            return True
        return bool(enabled[plugin_id])

    def enabled_plugins(self, config=None) -> list[LoadedPlugin]:
        return [
            plugin
            for plugin in self.plugins
            if self.is_enabled(plugin.plugin_id, config) and not plugin.error
        ]

    def get_plugin(self, plugin_id: str) -> Optional[LoadedPlugin]:
        """provider キー（id(ver:version)）または旧形式の id だけで探す。"""
        return self._match_plugin(plugin_id, exact_version=False)

    def _match_plugin(self, key: str, exact_version: bool = False) -> Optional[LoadedPlugin]:
        plugin_id, version = parse_provider_id(key)
        if not plugin_id or plugin_id in (BUILTIN_PROVIDER_ID, SKIP_PROVIDER_ID):
            return None
        matches = [plugin for plugin in self.plugins if plugin.plugin_id == plugin_id]
        if version:
            for plugin in matches:
                if plugin.version == version:
                    return plugin
            if exact_version:
                return None
        if len(matches) == 1:
            return matches[0]
        if matches:
            return max(matches, key=lambda item: version_sort_key(item.version))
        return None

    def knows_extension(self, extension: str, config=None) -> bool:
        ext = normalize_extension(extension)
        if builtin_kind_for_extension(ext) is not None:
            return True
        return any(plugin.offers(ext) is not None for plugin in self.enabled_plugins(config))

    def plugin_extensions(self, config=None) -> set[str]:
        exts: set[str] = set()
        for plugin in self.enabled_plugins(config):
            for spec in plugin.formats:
                exts.add(spec.extension)
        return exts

    def configured_provider(self, config, extension: str) -> Optional[str]:
        ext = normalize_extension(extension)
        handlers = {}
        if config is not None:
            handlers = dict(config.plugins.get("extension_handlers") or {})
        value = handlers.get(ext)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def resolve(self, file_path: str, config=None) -> HandlerDecision:
        extension = extension_for_path(file_path)
        return self.resolve_extension(extension, config)

    def resolve_extension(self, extension: str, config=None) -> HandlerDecision:
        ext = normalize_extension(extension)
        builtin_kind = builtin_kind_for_extension(ext)
        active = self.enabled_plugins(config)
        plugin_offers = [(plugin, plugin.offers(ext)) for plugin in active if plugin.offers(ext) is not None]
        configured = self.configured_provider(config, ext)

        if configured == SKIP_PROVIDER_ID:
            return HandlerDecision(SKIP_PROVIDER_ID, None, None)
        if configured is None and is_legacy_archive_disabled(config, ext):
            return HandlerDecision(SKIP_PROVIDER_ID, None, None)

        if configured and configured != BUILTIN_PROVIDER_ID:
            plugin = self.get_plugin(configured)
            if plugin is not None and not self.is_enabled(plugin.plugin_id, config):
                plugin = None
            kind = plugin.offers(ext) if plugin else None
            if plugin is not None and kind is not None:
                return HandlerDecision(plugin.provider_id, kind, plugin)

        if configured == BUILTIN_PROVIDER_ID and builtin_kind is not None:
            return HandlerDecision(BUILTIN_PROVIDER_ID, builtin_kind, None)

        if builtin_kind is not None:
            return HandlerDecision(BUILTIN_PROVIDER_ID, builtin_kind, None)

        if plugin_offers:
            plugin, kind = plugin_offers[0]
            return HandlerDecision(plugin.provider_id, kind, plugin)

        return HandlerDecision(BUILTIN_PROVIDER_ID, None, None)

    def activate_ui(self, config=None) -> None:
        for plugin in self.plugins:
            if self.is_enabled(plugin.plugin_id, config):
                self._activate_plugin(plugin)
            else:
                self._deactivate_plugin(plugin)

    def _activate_plugin(self, plugin: LoadedPlugin) -> None:
        if plugin.ui_active:
            return
        plugin.error = None
        setup = getattr(plugin.instance, "setup", None)
        if callable(setup):
            try:
                setup()
            except Exception as exc:
                plugin.error = str(exc)
                plugin.ui_active = False
                self.host.clear_plugin(plugin.plugin_id)
                logger.warning(get_log_text("plugin_setup_failed", plugin_id=plugin.plugin_id, error=exc))
                report_error("setup", exc, plugin_id=plugin.plugin_id)
                return
        plugin.ui_active = True

    def _deactivate_plugin(self, plugin: LoadedPlugin) -> None:
        teardown = getattr(plugin.instance, "teardown", None)
        if callable(teardown):
            try:
                teardown()
            except Exception as exc:
                logger.debug(get_log_text("plugin_teardown_failed", plugin_id=plugin.plugin_id, error=exc))
                report_error("teardown", exc, plugin_id=plugin.plugin_id)
        self.host.clear_plugin(plugin.plugin_id)
        plugin.ui_active = False

    def extension_rows(self, config=None, enabled_ids=None) -> list[ExtensionProviderRow]:
        rows: dict[str, ExtensionProviderRow] = {}
        for ext in sorted(ImageInfo.get_all_extensions()):
            kind = FileKind.IMAGE
            rows[ext] = ExtensionProviderRow(
                extension=ext,
                kind=kind,
                providers=[(BUILTIN_PROVIDER_ID, "")],
                selected=BUILTIN_PROVIDER_ID,
            )
        for ext in sorted(ArchiveInfo.get_all_extensions()):
            if ext in rows:
                continue
            rows[ext] = ExtensionProviderRow(
                extension=ext,
                kind=FileKind.ARCHIVE,
                providers=[(BUILTIN_PROVIDER_ID, "")],
                selected=BUILTIN_PROVIDER_ID,
            )
        if enabled_ids is None:
            active = self.enabled_plugins(config)
        else:
            allowed = {str(item) for item in enabled_ids}
            active = [plugin for plugin in self.plugins if plugin.plugin_id in allowed]
        for plugin in active:
            for spec in plugin.formats:
                row = rows.get(spec.extension)
                if row is None:
                    row = ExtensionProviderRow(
                        extension=spec.extension,
                        kind=spec.kind,
                        providers=[],
                        selected=plugin.provider_id,
                    )
                    rows[spec.extension] = row
                if not any(provider_id == plugin.provider_id for provider_id, _name in row.providers):
                    row.providers.append((plugin.provider_id, plugin.name))
        for row in rows.values():
            if not any(provider_id == BUILTIN_PROVIDER_ID for provider_id, _name in row.providers):
                if builtin_kind_for_extension(row.extension) is not None:
                    row.providers.insert(0, (BUILTIN_PROVIDER_ID, ""))
            if not any(provider_id == SKIP_PROVIDER_ID for provider_id, _name in row.providers):
                row.providers.append((SKIP_PROVIDER_ID, ""))
            configured = self.configured_provider(config, row.extension)
            valid_ids = {provider_id for provider_id, _name in row.providers}
            if configured == SKIP_PROVIDER_ID or (
                configured is None and is_legacy_archive_disabled(config, row.extension)
            ):
                row.selected = SKIP_PROVIDER_ID
                continue
            matched = self.get_plugin(configured) if configured and configured != BUILTIN_PROVIDER_ID else None
            if matched is not None and matched.provider_id in valid_ids:
                row.selected = matched.provider_id
            elif configured in valid_ids:
                row.selected = configured
            elif BUILTIN_PROVIDER_ID in valid_ids:
                row.selected = BUILTIN_PROVIDER_ID
            elif row.providers:
                row.selected = row.providers[0][0]
        return [rows[key] for key in sorted(rows)]


def get_plugin_manager() -> PluginManager:
    global _manager
    if _manager is None:
        _manager = PluginManager()
        _manager.discover()
    return _manager


def reset_plugin_manager() -> None:
    global _manager
    _manager = None
