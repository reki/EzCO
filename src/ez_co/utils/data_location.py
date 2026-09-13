"""プロファイル横断のデータの置き場とユーザ設定。場所と同意はユーザーフォルダの user.json。"""
from __future__ import annotations

import json
import os
import shutil
from importlib import resources
from pathlib import Path
from typing import Optional

from ez_co.utils.path_utils import get_project_root

LOCATION_USER = "user"
LOCATION_EXE = "exe"
LOCATION_CUSTOM = "custom"
LOCATION_MODES = (LOCATION_USER, LOCATION_EXE, LOCATION_CUSTOM)
LOCATION_FILENAME = "user.json"
PLUGIN_CONSENT_KEY = "plugin_consent_version"
APP_FOLDER_NAME = "EzCo"
USER_DATA_ITEMS = ("config.db", "plugins", "font", "langs")

_data_root: Optional[Path] = None
_consent_version_cache: Optional[str] = None


def get_app_location_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_FOLDER_NAME
    return Path.home() / "AppData" / "Roaming" / APP_FOLDER_NAME


def location_file_path() -> Path:
    return get_app_location_dir() / LOCATION_FILENAME


def has_location_file() -> bool:
    return location_file_path().is_file()


def exe_config_db_path() -> Path:
    return get_project_root() / "config.db"


def default_location_settings() -> dict:
    return {"data_location": LOCATION_USER, "custom_path": ""}


def _load_user_payload() -> dict:
    path = location_file_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _parse_consent_version(value) -> Optional[tuple[int, int, int]]:
    text = str(value or "").strip()
    if not text:
        return None
    parts = text.split(".")
    if not 1 <= len(parts) <= 3:
        return None
    numbers = []
    for part in parts:
        if not part.isdigit():
            return None
        numbers.append(int(part))
    while len(numbers) < 3:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2]


def _consent_version(value) -> str:
    parsed = _parse_consent_version(value)
    if parsed is None:
        return ""
    return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"


def load_location_settings() -> Optional[dict]:
    path = location_file_path()
    if not path.is_file():
        return None
    data = _load_user_payload()
    mode = data.get("data_location", LOCATION_USER)
    if mode not in LOCATION_MODES:
        mode = LOCATION_USER
    custom = data.get("custom_path") or ""
    result = {"data_location": mode, "custom_path": str(custom)}
    if PLUGIN_CONSENT_KEY in data:
        result[PLUGIN_CONSENT_KEY] = _consent_version(data.get(PLUGIN_CONSENT_KEY))
    return result


def save_location_settings(settings: dict) -> Path:
    payload = dict(_load_user_payload())
    mode = settings.get("data_location", payload.get("data_location", LOCATION_USER))
    if mode not in LOCATION_MODES:
        mode = LOCATION_USER
    payload["data_location"] = mode
    if "custom_path" in settings:
        payload["custom_path"] = str(settings.get("custom_path") or "")
    elif "custom_path" not in payload:
        payload["custom_path"] = ""
    if PLUGIN_CONSENT_KEY in settings:
        payload[PLUGIN_CONSENT_KEY] = _consent_version(settings.get(PLUGIN_CONSENT_KEY))
    dest_dir = get_app_location_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / LOCATION_FILENAME
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(path)
    return path


def plugin_consent_version() -> str:
    global _consent_version_cache
    if _consent_version_cache is not None:
        return _consent_version_cache
    try:
        text = (
            resources.files("ez_co.resources")
            .joinpath("plugin_consent", "version.txt")
            .read_text(encoding="utf-8")
        )
        line = (text or "").strip().splitlines()
        _consent_version_cache = _consent_version(line[0] if line else "")
    except (OSError, FileNotFoundError, AttributeError):
        _consent_version_cache = ""
    return _consent_version_cache


def plugin_consent_markdown(lang_code: Optional[str] = None) -> str:
    codes: list[str] = []
    if lang_code:
        codes.append(str(lang_code).split("_")[0].split("-")[0])
    else:
        from ez_co.utils.language_manager import language_manager
        current = language_manager.get_current_language()
        if current == "system":
            info = language_manager.available_languages.get("system") or {}
            current = str(info.get("code") or "ja")
        codes.append(str(current).split("_")[0].split("-")[0])
    for fallback in ("ja", "en"):
        if fallback not in codes:
            codes.append(fallback)
    root = resources.files("ez_co.resources").joinpath("plugin_consent")
    for code in codes:
        path = root.joinpath(f"{code}.md")
        try:
            if path.is_file():
                return path.read_text(encoding="utf-8")
        except (OSError, FileNotFoundError, AttributeError):
            continue
    return ""


def plugin_consent_accepted() -> bool:
    current = plugin_consent_version()
    stored = _consent_version(_load_user_payload().get(PLUGIN_CONSENT_KEY))
    return bool(current) and stored == current


def accept_plugin_consent() -> None:
    payload = dict(_load_user_payload())
    if payload.get("data_location") not in LOCATION_MODES:
        payload["data_location"] = LOCATION_USER
    if "custom_path" not in payload:
        payload["custom_path"] = ""
    payload[PLUGIN_CONSENT_KEY] = plugin_consent_version()
    save_location_settings(payload)


def resolve_data_root(settings: Optional[dict] = None) -> Path:
    data = settings if settings is not None else load_location_settings()
    if not data:
        return get_app_location_dir()
    mode = data.get("data_location", LOCATION_USER)
    if mode == LOCATION_EXE:
        return get_project_root()
    if mode == LOCATION_CUSTOM:
        custom = str(data.get("custom_path") or "").strip()
        if custom:
            return Path(custom).expanduser()
    return get_app_location_dir()


def get_data_root() -> Path:
    global _data_root
    if _data_root is not None:
        return _data_root
    settings = load_location_settings()
    if settings is None:
        return get_app_location_dir()
    _data_root = resolve_data_root(settings)
    _data_root.mkdir(parents=True, exist_ok=True)
    return _data_root


def set_data_root(path: Path) -> Path:
    global _data_root
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    _data_root = root
    return root


def apply_data_location(settings: dict, *, copy_from_exe: bool = False) -> Path:
    save_location_settings(settings)
    root = resolve_data_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    if copy_from_exe:
        copy_user_data(get_project_root(), root)
    return set_data_root(root)


def copy_user_data(src: Path, dst: Path) -> None:
    if src.resolve() == dst.resolve():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for name in USER_DATA_ITEMS:
        source = src / name
        dest = dst / name
        if not source.exists():
            continue
        if source.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source, dest)
        else:
            shutil.copy2(source, dest)


def is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ezco_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def logs_dir() -> Path:
    path = get_data_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
