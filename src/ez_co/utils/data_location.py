"""プロファイル横断のデータの置き場とユーザ設定。場所と同意はユーザーフォルダの user.json。"""
from __future__ import annotations

import json
import os
import shutil
from importlib import resources
from pathlib import Path
from typing import Optional

from ez_co.utils.path_utils import get_project_root

# ユーザーフォルダに置く場所
LOCATION_USER = "user"
# 実行ファイルの隣に置く場所
LOCATION_EXE = "exe"
# 指定したフォルダに置く場所
LOCATION_CUSTOM = "custom"
# 選べるデータの置き場所
LOCATION_MODES = (LOCATION_USER, LOCATION_EXE, LOCATION_CUSTOM)
# 場所と同意を書くファイル名
LOCATION_FILENAME = "user.json"
# プラグイン同意の版を書くキー
PLUGIN_CONSENT_KEY = "plugin_consent_version"
# ユーザーデータ用のフォルダ名
APP_FOLDER_NAME = "EzCo"
# ユーザーフォルダへ移す項目
USER_DATA_ITEMS = ("config.db", "plugins", "font", "langs")

_data_root: Optional[Path] = None
_consent_version_cache: Optional[str] = None


def get_app_location_dir() -> Path:
    """ユーザーフォルダ側のアプリデータディレクトリを返す。

    Returns:
        APPDATA 配下のディレクトリ。環境変数が無ければ home 側の同じ位置
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_FOLDER_NAME
    return Path.home() / "AppData" / "Roaming" / APP_FOLDER_NAME


def location_file_path() -> Path:
    """場所と同意を書く user.json のパスを返す。

    Returns:
        user.json のパス
    """
    return get_app_location_dir() / LOCATION_FILENAME


def has_location_file() -> bool:
    """user.json があるかを返す。

    Returns:
        ファイルがあれば True
    """
    return location_file_path().is_file()


def exe_config_db_path() -> Path:
    """実行フォルダ側の config.db のパスを返す。

    Returns:
        プロジェクトルートの config.db
    """
    return get_project_root() / "config.db"


def default_location_settings() -> dict:
    """場所設定の初期値を返す。

    Returns:
        ユーザーフォルダを使い、custom_path は空の辞書
    """
    return {"data_location": LOCATION_USER, "custom_path": ""}


def _load_user_payload() -> dict:
    """user.json を辞書として読む。

    Returns:
        読めた辞書。無い、壊れている、辞書でないときは空
    """
    path = location_file_path()
    if not path.is_file():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError):
        # 読めないか壊れていれば空の辞書を返す
        return {}
    return data if isinstance(data, dict) else {}


def _parse_consent_version(value) -> Optional[tuple[int, int, int]]:
    """同意バージョンを3つの整数に分ける。

    Args:
        value: バージョンの文字列

    Returns:
        足りない桁を 0 で埋めた3つ組。空、または形式が違えば None
    """
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
    """同意バージョンを3桁の文字列にする。

    Args:
        value: バージョンの文字列

    Returns:
        major.minor.patch。形式が違えば空
    """
    parsed = _parse_consent_version(value)
    if parsed is None:
        return ""
    return f"{parsed[0]}.{parsed[1]}.{parsed[2]}"


def load_location_settings() -> Optional[dict]:
    """user.json から場所と同意を読む。

    Returns:
        data_location と custom_path。同意があればそれも含む。ファイルが無ければ None
    """
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
    """場所と同意を user.json へ書く。

    Args:
        settings: 書き込む data_location、custom_path、同意バージョン

    Returns:
        書いた user.json のパス
    """
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
    """同梱の同意文のバージョンを返す。

    Returns:
        version.txt の版。読めなければ空
    """
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
        # 同意の版を読めなければ空文字にする
        _consent_version_cache = ""
    return _consent_version_cache


def plugin_consent_markdown(lang_code: Optional[str] = None) -> str:
    """同意文の Markdown を返す。

    Args:
        lang_code: 優先する言語コード。無いときは現在の言語

    Returns:
        読めた本文。どれも無ければ空
    """
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
            # その言語の同意文を読めなければ次の言語を試す
            continue
    return ""


def plugin_consent_accepted() -> bool:
    """保存済みの同意が現在の版と一致するかを返す。

    Returns:
        現在の版があり、保存値と等しければ True
    """
    current = plugin_consent_version()
    stored = _consent_version(_load_user_payload().get(PLUGIN_CONSENT_KEY))
    return bool(current) and stored == current


def accept_plugin_consent() -> None:
    """現在の同意バージョンを user.json に記録する。"""
    payload = dict(_load_user_payload())
    if payload.get("data_location") not in LOCATION_MODES:
        payload["data_location"] = LOCATION_USER
    if "custom_path" not in payload:
        payload["custom_path"] = ""
    payload[PLUGIN_CONSENT_KEY] = plugin_consent_version()
    save_location_settings(payload)


def resolve_data_root(settings: Optional[dict] = None) -> Path:
    """設定からデータの置き場を決める。

    Args:
        settings: 場所の設定。無いときは user.json を読む

    Returns:
        データディレクトリ。設定が無ければユーザーフォルダ側
    """
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
    """現在のデータの置き場を返す。

    Returns:
        場所設定があるときは作ってキャッシュしたディレクトリ。無ければユーザーフォルダ側
    """
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
    """データの置き場をメモリ上で差し替える。

    Args:
        path: 新しいデータディレクトリ

    Returns:
        作成したディレクトリ
    """
    global _data_root
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    _data_root = root
    return root


def apply_data_location(settings: dict, *, copy_from_exe: bool = False) -> Path:
    """場所設定を保存し、データの置き場を切り替える。

    Args:
        settings: 書き込む場所の設定
        copy_from_exe: 真なら実行フォルダのユーザーデータをコピーする

    Returns:
        切り替えたデータディレクトリ
    """
    save_location_settings(settings)
    root = resolve_data_root(settings)
    root.mkdir(parents=True, exist_ok=True)
    if copy_from_exe:
        copy_user_data(get_project_root(), root)
    return set_data_root(root)


def copy_user_data(src: Path, dst: Path) -> None:
    """ユーザーデータを別の置き場へコピーする。

    Args:
        src: コピー元
        dst: コピー先
    """
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
    """ディレクトリへ試し書きできるかを返す。

    Args:
        path: 調べるディレクトリ

    Returns:
        作成と書き込みができれば True
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".ezco_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        # 書き込みに失敗したら偽を返す
        return False


def logs_dir() -> Path:
    """ログディレクトリを返す。

    Returns:
        データの置き場にある logs。無ければ作る
    """
    path = get_data_root() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path
