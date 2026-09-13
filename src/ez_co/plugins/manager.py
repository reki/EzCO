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
        self._backends = (ZipPythonBackend(), DllBackend())
        self._scanned = False
        self.host = PluginHost()

    def scan(self, directory: Optional[Path] = None) -> None:
        directory = directory or plugins_dir()
        self.plugins.clear()
        self.failed.clear()
        if not directory.is_dir():
            logger.info(get_log_text("plugin_dir_missing", path=directory))
            self._scanned = True
            return
        logger.info(get_log_text("plugin_scan_start", path=directory))
        for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
            if not path.is_file():
                continue
            backend = next((item for item in self._backends if item.can_load(path)), None)
            if backend is None:
                continue
            try:
                loaded = backend.load(path, host=self.host)
                if loaded is None:
                    continue
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
                    zip_path=path,
                    formats=formats,
                    _archive=archive,
                )
                existing = self._match_plugin(plugin.provider_id, exact_version=True)
                if existing is not None:
                    raise ValueError(
                        get_log_text(
                            "plugin_duplicate_provider",
                            provider_id=plugin.provider_id,
                            path=path,
                            existing_path=existing.zip_path,
                        )
                    )
                self.plugins.append(plugin)
                logger.info(
                    get_log_text(
                        "plugin_loaded",
                        plugin_id=plugin.plugin_id,
                        name=plugin.name,
                        version=plugin.manifest.version,
                        path=path,
                    )
                )
            except Exception as exc:
                message = str(exc)
                self.failed.append((path, message))
                logger.warning(get_log_text("plugin_load_failed", path=path, error=exc))
                report_error("load", exc, plugin_id=str(path.name))
        self._scanned = True

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
        _manager.scan()
    return _manager


def reset_plugin_manager() -> None:
    global _manager
    _manager = None
