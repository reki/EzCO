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
from pathlib import Path
from types import ModuleType
from typing import Any

from ez_co.plugins.api import HOST_API_VERSION
from ez_co.plugins.manifest import PluginManifest, parse_formats, parse_manifest, parse_sidebar
from ez_co.plugins.root import PluginRoot, open_plugin_source
from ez_co.utils.language_manager import get_log_text

logger = logging.getLogger(__name__)

# プラグインモジュール名の接頭辞。
PLUGIN_MODULE_PREFIX = "_ezco_plugin_"
# モジュール名に使えない文字。
_SAFE_ID_RE = re.compile(r"[^0-9a-zA-Z_]+")


def safe_module_prefix(plugin_id: str) -> str:
    """プラグイン ID を import できるモジュール接頭辞にする。

    Args:
        plugin_id: プラグイン ID。

    Returns:
        _ezco_plugin_ で始まる接頭辞。
    """
    cleaned = _SAFE_ID_RE.sub("_", plugin_id).strip("_").lower() or "plugin"
    if cleaned[0].isdigit():
        cleaned = f"p_{cleaned}"
    return f"{PLUGIN_MODULE_PREFIX}{cleaned}"


def _build_src_map(source) -> dict[str, str]:
    """src 以下の .py をモジュール名から ZIP 内パスへ対応付ける。

    Args:
        source: namelist を持つソース。

    Returns:
        モジュール名から ZIP 内パスへの対応。
    """
    src_map: dict[str, str] = {}
    for name in source.namelist():
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
    """ZIP 内の src をモジュールとして実行するローダー。"""

    def __init__(
        self,
        plugin_id: str,
        prefix: str,
        zip_path: Path,
        source,
        zip_name: str,
        src_map: dict[str, str],
        is_package: bool,
        get_text=None,
        host=None,
    ):
        """読み込むモジュールの場所と、注入する get_text と host を保持する。

        Args:
            plugin_id: プラグイン ID。
            prefix: モジュール接頭辞。
            zip_path: ZIP またはディレクトリのパス。
            source: バイト列を読むソース。
            zip_name: ZIP 内のパス。
            src_map: モジュール名から ZIP 内パスへの対応。
            is_package: パッケージとして扱うか。
            get_text: 注入する文言関数。
            host: 注入するホスト。
        """
        self.plugin_id = plugin_id
        self.prefix = prefix
        self.zip_path = zip_path
        self.source = source
        self.zip_name = zip_name
        self.src_map = src_map
        self._is_package = is_package
        self.get_text = get_text
        self.host = host

    def is_package(self, fullname):
        """このローダーがパッケージを表すなら True。

        Args:
            fullname: モジュールの完全名。判定には使わない。

        Returns:
            パッケージなら True。
        """
        return self._is_package

    def create_module(self, spec):
        """モジュール生成は import 機構に任せる。

        Args:
            spec: モジュール仕様。使わない。
        """
        return None

    def exec_module(self, module: ModuleType):
        """ソースを実行し、builtins に get_text と host を載せる。

        Args:
            module: 実行先のモジュール。
        """
        source = self.source.read_bytes(self.zip_name).decode("utf-8")
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
        """ez_co と他プラグインを拒み、src 内の名前は接頭辞付きで読む import を作る。

        Returns:
            差し替える __import__。
        """
        prefix = self.prefix
        src_map = self.src_map
        real_import = builtins.__import__

        def plugin_import(name, globals=None, locals=None, fromlist=(), level=0):
            """相対 import は通常どおり行い、ez_co と他プラグイン接頭辞は拒否する。

            Args:
                name: import する名前。
                globals: 呼び出し元のグローバル。
                locals: 呼び出し元のローカル。
                fromlist: from import の名前。
                level: 相対 import の段数。0 以外は通常の import。

            Returns:
                読み込んだモジュール。

            Raises:
                ImportError: ez_co、または他プラグインの接頭辞のとき。
            """
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
    """接頭辞付きモジュール名を ZIP 内 src へ解決するファインダ。"""

    def __init__(
        self,
        plugin_id: str,
        prefix: str,
        zip_path: Path,
        source,
        src_map: dict[str, str],
        get_text=None,
        host=None,
    ):
        """解決に使う接頭辞、ソース、src の対応を保持する。

        Args:
            plugin_id: プラグイン ID。
            prefix: モジュール接頭辞。
            zip_path: ZIP またはディレクトリのパス。
            source: バイト列を読むソース。
            src_map: モジュール名から ZIP 内パスへの対応。
            get_text: ローダーへ渡す文言関数。
            host: ローダーへ渡すホスト。
        """
        self.plugin_id = plugin_id
        self.prefix = prefix
        self.zip_path = zip_path
        self.source = source
        self.src_map = src_map
        self.get_text = get_text
        self.host = host

    def find_spec(self, fullname, path, target=None):
        """接頭辞に続く名前を src のモジュール仕様にする。

        Args:
            fullname: 探す完全名。
            path: 探索パス。このファインダは使わない。
            target: 既存モジュール。このファインダは使わない。

        Returns:
            見つかった仕様。接頭辞が違えば None。
        """
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
            if not self.source.exists(zip_name):
                spec = importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
                spec.submodule_search_locations = [f"{self.zip_path.as_posix()}/src/{local_name.replace('.', '/')}"]
                return spec
        loader = _PluginSrcLoader(
            self.plugin_id,
            self.prefix,
            self.zip_path,
            self.source,
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
    """接頭辞のモジュールと、同じ接頭辞のファインダを外す。

    Args:
        prefix: 外す接頭辞。
    """
    to_remove = [name for name in sys.modules if name == prefix or name.startswith(prefix + ".")]
    for name in to_remove:
        del sys.modules[name]
    sys.meta_path[:] = [
        finder
        for finder in sys.meta_path
        if not (isinstance(finder, PluginSrcFinder) and finder.prefix == prefix)
    ]


# ライセンスとして探すファイル名と形式。
LICENSE_FILES = (
    ("LICENSE.md", "markdown"),
    ("LICENSE.txt", "text"),
    ("LICENSE", "text"),
)


def peek_license(path: Path) -> dict[str, str] | None:
    """ルート直下の LICENSE.md / LICENSE.txt / LICENSE を優先順で読む。

    Args:
        path: ZIP またはディレクトリ。

    Returns:
        name、kind、text を持つ dict。無ければ None。
    """
    path = Path(path)
    source = open_plugin_source(path)
    try:
        for name, kind in LICENSE_FILES:
            if not source.exists(name):
                continue
            raw = source.read_bytes(name)
            text = raw.decode("utf-8-sig", errors="replace")
            return {"name": name, "kind": kind, "text": text}
    finally:
        source.close()
    return None


def peek_manifest(path: Path) -> dict:
    """実体化せず manifest.json から id / name / version / 提供物を読む。

    Args:
        path: ZIP またはディレクトリ。

    Returns:
        id、name、version、formats、sidebar を持つ dict。

    Raises:
        ValueError: manifest が無い、オブジェクトでない、または id が空のとき。
    """
    path = Path(path)
    source = open_plugin_source(path)
    try:
        try:
            raw = json.loads(source.read_bytes("manifest.json").decode("utf-8"))
        except KeyError as exc:
            # manifest が無ければ ValueError にして返す。
            raise ValueError("manifest.json is missing") from exc
    finally:
        source.close()
    if not isinstance(raw, dict):
        raise ValueError("manifest must be an object")
    plugin_id = str(raw.get("id") or "").strip()
    if not plugin_id:
        raise ValueError("manifest.id is required")
    name = str(raw.get("name") or "").strip() or path.name
    version = str(raw.get("version") or "").strip()
    formats = parse_formats(raw.get("formats"))
    return {
        "id": plugin_id,
        "name": name,
        "version": version,
        "formats": [[spec.extension, spec.kind.value] for spec in formats],
        "sidebar": parse_sidebar(raw.get("sidebar")),
    }


def _instantiate(module: ModuleType, class_name: str) -> Any:
    """モジュールから entry のクラスを引数なしで作る。

    Args:
        module: 読み込んだモジュール。
        class_name: クラス名。

    Returns:
        クラスのインスタンス。

    Raises:
        ValueError: クラスが無い、またはクラスでないとき。
    """
    exported = vars(module)
    if class_name not in exported:
        raise ValueError(f"entry class not found in module: {class_name}")
    candidate = exported[class_name]
    if not isinstance(candidate, type):
        raise ValueError(f"entry is not a class: {class_name}")
    return candidate()


def _call_load(instance, root: PluginRoot, get_text, host, plugin_id: str) -> None:
    """インスタンスの load に root、get_text、host を渡す。

    Args:
        instance: プラグインインスタンス。
        root: プラグインルート。
        get_text: 文言関数。
        host: スコープ付きホスト。
        plugin_id: エラー文言に載せる ID。

    Raises:
        ValueError: load が無い、または呼べないとき。
    """
    load = getattr(instance, "load", None)
    if not callable(load):
        raise ValueError(get_log_text("plugin_load_missing", plugin_id=plugin_id))
    load(root, get_text, host)


def load_plugin(path: Path, host=None) -> tuple[PluginManifest, Any, PluginRoot, Any]:
    """manifest を検証し、src を読み、load まで呼ぶ。

    Args:
        path: ZIP またはディレクトリ。
        host: 共有ホスト。省略時は新しい PluginHost。

    Returns:
        manifest、インスタンス、root、アーカイブ。

    Raises:
        ValueError: manifest が不正、API 版が違う、entry が src に無い、または担当も sidebar も setup も無いとき。
    """
    path = Path(path)
    source = open_plugin_source(path)
    try:
        try:
            raw = json.loads(source.read_bytes("manifest.json").decode("utf-8"))
        except KeyError as exc:
            # manifest が無ければ ValueError にして返す。
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
        src_map = _build_src_map(source)
        if manifest.entry_module not in src_map:
            raise ValueError(f"entry module not found in src/: {manifest.entry_module}")
        prefix = safe_module_prefix(f"{manifest.plugin_id}_{manifest.version}")
        _unload_prefix(prefix)
        from ez_co.plugins.host import PluginHost, ScopedPluginHost
        from ez_co.plugins.i18n import make_plugin_get_text
        shared = host or PluginHost()
        owner = shared._host if isinstance(shared, ScopedPluginHost) else shared
        if isinstance(shared, PluginHost):
            shared.set_manifest_permissions(manifest.plugin_id, manifest.permissions)
            shared.set_manifest_provides(manifest.plugin_id, manifest.formats, manifest.sidebar)
        if isinstance(shared, ScopedPluginHost):
            scoped = shared
        elif hasattr(shared, "scoped"):
            scoped = shared.scoped(manifest.plugin_id)
        else:
            scoped = shared
        root = PluginRoot(path, source, get_text=lambda key, **kwargs: key, host=scoped)
        get_text_fn = make_plugin_get_text(root)
        root.get_text = get_text_fn
        if isinstance(scoped, ScopedPluginHost):
            scoped.bind_plugin(root, get_text_fn)
        finder = PluginSrcFinder(
            manifest.plugin_id, prefix, path, source, src_map, get_text=get_text_fn, host=scoped
        )
        sys.meta_path.insert(0, finder)
        if prefix not in sys.modules:
            pkg = ModuleType(prefix)
            pkg.__path__ = [f"{path.as_posix()}/src"]
            pkg.__package__ = prefix
            sys.modules[prefix] = pkg
        try:
            if isinstance(owner, PluginHost):
                owner.enter_phase(manifest.plugin_id, "init")
            module = importlib.import_module(f"{prefix}.{manifest.entry_module}")
            instance = _instantiate(module, manifest.entry_class)
            if isinstance(owner, PluginHost):
                owner.enter_phase(manifest.plugin_id, "idle")
                owner.enter_phase(manifest.plugin_id, "load")
            _call_load(instance, root, get_text_fn, scoped, manifest.plugin_id)
            if isinstance(owner, PluginHost):
                owner.enter_phase(manifest.plugin_id, "idle")
        except Exception:
            # 読み込みに失敗したら phase を戻して例外を返す。
            if isinstance(owner, PluginHost):
                owner.abort_load(manifest.plugin_id)
            raise
        formats = list(manifest.formats)
        has_setup = callable(getattr(instance, "setup", None))
        if not formats and not manifest.sidebar and not has_setup:
            if isinstance(owner, PluginHost):
                owner.abort_load(manifest.plugin_id)
            raise ValueError(get_log_text("plugin_no_formats", plugin_id=manifest.plugin_id))
        instance._ezco_formats = formats
        return manifest, instance, root, source.archive
    except Exception:
        # 失敗したらソースを閉じて例外を返す。
        source.close()
        raise
