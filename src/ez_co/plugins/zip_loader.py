"""ZIP プラグインを src ルートとして importlib で読み込む。"""
from __future__ import annotations

import builtins
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import json
import logging
import re
import sys
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

from ez_co.plugins.api import HOST_API_VERSION, normalize_formats
from ez_co.plugins.manifest import PluginManifest, parse_manifest
from ez_co.plugins.root import ZipPluginRoot
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)

PLUGIN_MODULE_PREFIX = "_ezco_plugin_"
_SAFE_ID_RE = re.compile(r"[^0-9a-zA-Z_]+")


def safe_module_prefix(plugin_id: str) -> str:
    cleaned = _SAFE_ID_RE.sub("_", plugin_id).strip("_").lower() or "plugin"
    if cleaned[0].isdigit():
        cleaned = f"p_{cleaned}"
    return f"{PLUGIN_MODULE_PREFIX}{cleaned}"


def _build_src_map(archive: zipfile.ZipFile) -> dict[str, str]:
    src_map: dict[str, str] = {}
    for name in archive.namelist():
        normalized = name.replace("\\", "/")
        if not normalized.startswith("src/") or normalized.endswith("/"):
            continue
        relative = normalized[len("src/") :]
        if not relative.endswith(".py"):
            continue
        if relative == "__init__.py":
            continue
        module = relative[: -len(".py")].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        src_map[module] = normalized
    return src_map


class _PluginSrcLoader(importlib.abc.Loader):
    def __init__(
        self,
        plugin_id: str,
        prefix: str,
        zip_path: Path,
        archive: zipfile.ZipFile,
        zip_name: str,
        src_map: dict[str, str],
        is_package: bool,
        get_text=None,
        host=None,
    ):
        self.plugin_id = plugin_id
        self.prefix = prefix
        self.zip_path = zip_path
        self.archive = archive
        self.zip_name = zip_name
        self.src_map = src_map
        self._is_package = is_package
        self.get_text = get_text
        self.host = host

    def is_package(self, fullname):
        return self._is_package

    def create_module(self, spec):
        return None

    def exec_module(self, module: ModuleType):
        source = self.archive.read(self.zip_name).decode("utf-8")
        relative = self.zip_name[len("src/") :] if self.zip_name.startswith("src/") else self.zip_name
        module.__file__ = f"{self.zip_path.as_posix()}/src/{relative}"
        module.__ezco_plugin_id__ = self.plugin_id
        if self._is_package:
            module.__path__ = [f"{self.zip_path.as_posix()}/src/{Path(relative).parent.as_posix()}"]
        plugin_builtins = ModuleType("builtins")
        plugin_builtins.__dict__.update(builtins.__dict__)
        plugin_builtins.__import__ = self._make_import()
        plugin_builtins.get_text = self.get_text
        plugin_builtins.host = self.host
        plugin_builtins.ask_password = self.host.ask_password
        plugin_builtins.show_dialog = self.host.show_dialog
        plugin_builtins.run_action = self.host.run_action
        module.__dict__["__builtins__"] = plugin_builtins
        exec(compile(source, module.__file__, "exec"), module.__dict__)

    def _make_import(self):
        prefix = self.prefix
        src_map = self.src_map
        real_import = builtins.__import__

        def plugin_import(name, globals=None, locals=None, fromlist=(), level=0):
            if level != 0:
                return real_import(name, globals, locals, fromlist, level)
            if name == "ez_co" or name.startswith("ez_co."):
                raise ImportError(get_log_text("plugin_import_blocked", name=name, plugin_id=self.plugin_id))
            if name.startswith(PLUGIN_MODULE_PREFIX) and not name.startswith(prefix):
                raise ImportError(get_log_text("plugin_import_blocked", name=name, plugin_id=self.plugin_id))
            top = name.split(".", 1)[0]
            if top in src_map or any(key == top or key.startswith(f"{top}.") for key in src_map):
                return real_import(f"{prefix}.{name}", globals, locals, fromlist, level)
            return real_import(name, globals, locals, fromlist, level)

        return plugin_import


class PluginSrcFinder(importlib.abc.MetaPathFinder):
    def __init__(
        self,
        plugin_id: str,
        prefix: str,
        zip_path: Path,
        archive: zipfile.ZipFile,
        src_map: dict[str, str],
        get_text=None,
        host=None,
    ):
        self.plugin_id = plugin_id
        self.prefix = prefix
        self.zip_path = zip_path
        self.archive = archive
        self.src_map = src_map
        self.get_text = get_text
        self.host = host

    def find_spec(self, fullname, path, target=None):
        if fullname == self.prefix:
            spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            spec.submodule_search_locations = [f"{self.zip_path.as_posix()}/src"]
            return spec
        prefix_dot = f"{self.prefix}."
        if not fullname.startswith(prefix_dot):
            return None
        local_name = fullname[len(prefix_dot) :]
        zip_name = self.src_map.get(local_name)
        is_package = any(key.startswith(f"{local_name}.") for key in self.src_map)
        if zip_name is None:
            if not is_package:
                return None
            zip_name = f"src/{local_name.replace('.', '/')}/__init__.py"
            if zip_name not in self.archive.namelist():
                spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
                spec.submodule_search_locations = [f"{self.zip_path.as_posix()}/src/{local_name.replace('.', '/')}"]
                return spec
        loader = _PluginSrcLoader(
            self.plugin_id,
            self.prefix,
            self.zip_path,
            self.archive,
            zip_name,
            self.src_map,
            is_package=is_package or zip_name.endswith("/__init__.py"),
            get_text=self.get_text,
            host=self.host,
        )
        spec = importlib.util.spec_from_loader(fullname, loader, origin=f"{self.zip_path}/src/{local_name}")
        if spec is not None and (is_package or zip_name.endswith("/__init__.py")):
            spec.submodule_search_locations = [f"{self.zip_path.as_posix()}/src/{local_name.replace('.', '/')}"]
        return spec


def _unload_prefix(prefix: str) -> None:
    to_remove = [name for name in sys.modules if name == prefix or name.startswith(prefix + ".")]
    for name in to_remove:
        del sys.modules[name]
    sys.meta_path[:] = [
        finder
        for finder in sys.meta_path
        if not (isinstance(finder, PluginSrcFinder) and finder.prefix == prefix)
    ]


def _instantiate(module: ModuleType, class_name: str, root: ZipPluginRoot, get_text, host) -> Any:
    exported = vars(module)
    if class_name not in exported:
        raise ValueError(f"entry class not found in module: {class_name}")
    candidate = exported[class_name]
    if not isinstance(candidate, type):
        raise ValueError(f"entry is not a class: {class_name}")
    return candidate(root, get_text, host)


def load_zip_plugin(zip_path: Path, host=None) -> tuple[PluginManifest, Any, ZipPluginRoot, zipfile.ZipFile]:
    archive = zipfile.ZipFile(zip_path, "r")
    try:
        try:
            raw = json.loads(archive.read("manifest.json").decode("utf-8"))
        except KeyError as exc:
            raise ValueError("manifest.json is missing") from exc
        manifest = parse_manifest(raw)
        if manifest.api_version != HOST_API_VERSION:
            raise ValueError(
                get_log_text(
                    "plugin_api_version_unsupported",
                    plugin_id=manifest.plugin_id,
                    api_version=manifest.api_version,
                    host_api_version=HOST_API_VERSION,
                )
            )
        src_map = _build_src_map(archive)
        if manifest.entry_module not in src_map:
            raise ValueError(f"entry module not found in src/: {manifest.entry_module}")
        prefix = safe_module_prefix(f"{manifest.plugin_id}_{manifest.version}")
        _unload_prefix(prefix)
        from ez_co.plugins.host import PluginHost
        from ez_co.plugins.i18n import make_plugin_get_text
        host = host or PluginHost()
        root = ZipPluginRoot(zip_path, archive, get_text=lambda key, **kwargs: key, host=host)
        get_text_fn = make_plugin_get_text(root)
        root.get_text = get_text_fn
        finder = PluginSrcFinder(
            manifest.plugin_id, prefix, zip_path, archive, src_map, get_text=get_text_fn, host=host
        )
        sys.meta_path.insert(0, finder)
        if prefix not in sys.modules:
            pkg = ModuleType(prefix)
            pkg.__path__ = [f"{zip_path.as_posix()}/src"]
            pkg.__package__ = prefix
            sys.modules[prefix] = pkg
        module = importlib.import_module(f"{prefix}.{manifest.entry_module}")
        instance = _instantiate(module, manifest.entry_class, root, get_text_fn, host)
        try:
            formats = normalize_formats(instance.supported_formats())
        except AttributeError as exc:
            raise ValueError("plugin has no supported_formats") from exc
        if not formats:
            raise ValueError(get_log_text("plugin_no_formats", plugin_id=manifest.plugin_id))
        instance._ezco_formats = formats
        return manifest, instance, root, archive
    except Exception:
        archive.close()
        raise
