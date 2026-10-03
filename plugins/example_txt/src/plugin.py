"""EzCo 向けテキスト画像サンプル。

ホストは Class() のあと load(root, get_text, host) を渡す。

ホストが呼ぶ必須メソッド:
    get_file_count(path) -> int
    list_entries(path) -> [エントリ名, ...]
    read_entry(path, index) -> オブジェクト(name, data: bytes)

.txt / .log をアーカイブとして開き、折り返した本文を PNG ページにする。
サイドバーの字体・色・縦読み／横読み・文字コードは即時反映し、今のページの先頭文字から再分割する。
担当拡張子は manifest.formats と同じ並びの _SOURCE_SUFFIXES。
"""
import os
import threading

from layout import (
    HORIZONTAL,
    PageSettings,
    layout_fits,
    page_index_for_start,
    paginate,
    paginate_anchored,
    read_text,
    render_page,
    resolve_settings,
)

# テキスト画像の初期設定。
_DEFAULTS = {
    "font_family": "",
    "font_size": 0,
    "text_color": "#222222",
    "bg_color": "#f7f2e8",
    "page_width": 900,
    "page_height": 1200,
    "margin": 48,
    "writing": HORIZONTAL,
    "charset": "utf-8",
}
# 担当する拡張子。
_SOURCE_SUFFIXES = (".txt", ".log")


class TextImagePlugin:
    """テキストをページ画像にするプラグイン。"""

    def __init__(self):
        """root、get_text、host と、ページ分割のキャッシュを空で作る。"""
        self.root = None
        self.get_text = None
        self.host = None
        self._listening = False
        self._lock = threading.Lock()
        self._cache = {}
        self._last_txt = None

    def load(self, root, get_text, host):
        """root、get_text、host を保持し、設定 JSON を登録する。

        Args:
            root: プラグインルート。
            get_text: 文言取得関数。
            host: スコープ付きホスト。
        """
        self.root = root
        self.get_text = get_text
        self.host = host
        self.host.register_config_json("fields.json")

    def get_file_count(self, file_path):
        """ページ数を返す。

        Args:
            file_path: 対象テキスト。

        Returns:
            ページ数。
        """
        return len(self.list_entries(file_path))

    def list_entries(self, file_path):
        """ページ画像名を返し、最後に開いたパスを覚える。

        Args:
            file_path: 対象テキスト。

        Returns:
            page_NNN.png のリスト。ページが無ければ page_001.png の1件。
        """
        self._last_txt = str(file_path)
        pages = self._pages_for(file_path)
        if not pages:
            return ["page_001.png"]
        return [_page_name(index) for index in range(len(pages))]

    def read_entry(self, file_path, index):
        """指定ページの PNG を返す。

        Args:
            file_path: 対象テキスト。
            index: ページ番号。範囲外は端に寄せる。

        Returns:
            名前と PNG バイト列を持つエントリ。
        """
        text, pages, settings = self._layout_for(file_path)
        if not pages:
            pages = [(0, 0)]
            text = text or ""
        index = max(0, min(int(index), len(pages) - 1))
        start, end = pages[index]
        return _Entry(_page_name(index), render_page(text, start, end, settings))

    def setup(self):
        """設定変更を購読し、設定サイドバーを登録する。"""
        if not self._listening:
            self.host.on("config_changed", self._on_config)
            self._listening = True
        self.host.register_config_sidebar("text_image", "{title}")

    def teardown(self):
        """購読フラグを下ろす。"""
        self._listening = False

    def _on_config(self, payload=None):
        """文字コード変更で本文キャッシュを捨て、収まる設定なら現在位置から読み直す。

        Args:
            payload: config_changed の内容。charset のときだけキャッシュを捨てる。
        """
        if isinstance(payload, dict) and payload.get("key") == "charset":
            self._drop_text_cache()
        settings = self._resolved(self._raw_settings())
        if not layout_fits(settings):
            return
        self._reload_from_anchor()

    def _reload_from_anchor(self):
        """今のページ先頭文字を保ってページを組み直し、そのページを読み直す。"""
        path = self._current_txt_path()
        if not path:
            return
        try:
            text = read_text(path, self._charset())
        except OSError as exc:
            # 本文を読めなければ記録して再読み込みをやめる。
            self.host.report_error("read_text", exc)
            return
        page = self.host.get_current("page")
        try:
            page_index = max(0, int(page) - 1)
        except (TypeError, ValueError):
            # ページ番号にできなければ先頭ページにする。
            page_index = 0
        old_pages = None
        with self._lock:
            cached = self._cache.get(_norm(path))
            if cached is not None:
                old_pages = cached.get("pages")
        if old_pages and 0 <= page_index < len(old_pages):
            anchor = old_pages[page_index][0]
        else:
            anchor = 0
        settings = self._resolved(self._raw_settings())
        pages = paginate_anchored(text, settings, anchor)
        if not pages:
            return
        new_page = page_index_for_start(pages, anchor) + 1
        with self._lock:
            self._cache[_norm(path)] = {
                "mtime": _mtime(path),
                "settings": settings,
                "charset": self._charset(),
                "text": text,
                "pages": pages,
            }
        self.host.reload_current(new_page)

    def _current_txt_path(self):
        """今のパスから元テキストのパスを取り、無ければ最後に開いたパスを使う。

        Returns:
            テキストのパス。見つからなければ None。
        """
        parsed = _txt_path(self.host.get_current("path"))
        if parsed:
            self._last_txt = parsed
            return parsed
        last = self._last_txt
        if not last:
            return None
        current = str(self.host.get_current("path") or "").replace("\\", "/")
        name = os.path.basename(last)
        if name and name.replace("\\", "/") in current:
            return last
        return None

    def _charset(self) -> str:
        """設定の文字コードを返す。

        Returns:
            文字コード。空なら utf-8。
        """
        return str(self.host.get_config("charset", _DEFAULTS["charset"]) or "utf-8")

    def _drop_text_cache(self):
        """今のテキストのキャッシュを捨てる。"""
        path = self._current_txt_path()
        if not path:
            return
        with self._lock:
            self._cache.pop(_norm(path), None)

    def _raw_settings(self) -> PageSettings:
        """設定値から PageSettings を作る。

        Returns:
            プラグイン設定の PageSettings。
        """
        return PageSettings(
            font_family=str(self.host.get_config("font_family", _DEFAULTS["font_family"]) or ""),
            font_size=int(self.host.get_config("font_size", _DEFAULTS["font_size"]) or 0),
            text_color=str(self.host.get_config("text_color", _DEFAULTS["text_color"]) or _DEFAULTS["text_color"]),
            bg_color=str(self.host.get_config("bg_color", _DEFAULTS["bg_color"]) or _DEFAULTS["bg_color"]),
            page_width=int(self.host.get_config("page_width", _DEFAULTS["page_width"])),
            page_height=int(self.host.get_config("page_height", _DEFAULTS["page_height"])),
            margin=int(self.host.get_config("margin", _DEFAULTS["margin"])),
            writing=str(self.host.get_config("writing", _DEFAULTS["writing"]) or HORIZONTAL),
        )

    def _app_font(self):
        """アプリの ui_font から字体とサイズを読む。

        Returns:
            字体名とサイズ。読めなければ空と 0。
        """
        ui = {}
        try:
            ui = dict(self.host.get_app_config().get("ui_font") or {})
        except Exception:
            # アプリ字体を読めなければ空として続ける。
            ui = {}
        family = str(ui.get("font_family") or "")
        try:
            size = int(ui.get("font_size") or 0)
        except (TypeError, ValueError):
            # サイズを整数にできなければ 0 にする。
            size = 0
        return family, size

    def _resolved(self, raw: PageSettings) -> PageSettings:
        """アプリ字体で空欄を埋めた PageSettings を返す。

        Args:
            raw: プラグイン設定の値。

        Returns:
            補完後の PageSettings。
        """
        family, size = self._app_font()
        return resolve_settings(raw, family, size)

    def _pages_for(self, file_path):
        """ファイルのページ範囲だけ返す。

        Args:
            file_path: 対象テキスト。

        Returns:
            ページの開始と終了。
        """
        _text, pages, _settings = self._layout_for(file_path)
        return pages

    def _layout_for(self, file_path):
        """キャッシュか再分割で本文、ページ範囲、設定を返す。

        Args:
            file_path: 対象テキスト。

        Returns:
            本文、ページ範囲、設定。読めなければ空本文と1ページ。
        """
        path = str(file_path)
        key = _norm(path)
        mtime = _mtime(path)
        settings = self._resolved(self._raw_settings())
        charset = self._charset()
        with self._lock:
            cached = self._cache.get(key)
            if (
                cached
                and cached.get("mtime") == mtime
                and cached.get("settings") == settings
                and cached.get("charset") == charset
            ):
                return cached["text"], cached["pages"], cached["settings"]
        try:
            text = read_text(path, charset)
        except OSError as exc:
            # 本文を読めなければ記録して空のページを返す。
            self.host.report_error("read_text", exc)
            return "", [(0, 0)], settings
        pages = paginate(text, settings)
        if pages is None:
            pages = [(0, len(text))]
        with self._lock:
            self._cache[key] = {
                "mtime": mtime,
                "settings": settings,
                "charset": charset,
                "text": text,
                "pages": pages,
            }
        return text, pages, settings


class _Entry:
    """エントリ名とバイト列。"""

    def __init__(self, name, data):
        """名前とバイト列を保持する。

        Args:
            name: エントリ名。
            data: バイト列。
        """
        self.name = name
        self.data = data


def _page_name(index: int) -> str:
    """1始まり3桁のページ画像名を返す。

    Args:
        index: 0始まりのページ番号。

    Returns:
        page_NNN.png。
    """
    return f"page_{index + 1:03d}.png"


def _norm(path: str) -> str:
    """パスを比較用に正規化する。

    Args:
        path: 対象パス。

    Returns:
        大文字小文字を揃えた正規パス。
    """
    return os.path.normcase(os.path.normpath(str(path)))


def _mtime(path: str) -> float:
    """更新時刻を返し、読めなければ -1。

    Args:
        path: 対象パス。

    Returns:
        更新時刻。読めなければ -1。
    """
    try:
        return os.path.getmtime(path)
    except OSError:
        # 更新時刻を読めなければ -1 を返す。
        return -1


def _has_source_suffix(name: str, suffixes=_SOURCE_SUFFIXES) -> bool:
    """名前が担当拡張子で終わるなら True。

    Args:
        name: ファイル名。
        suffixes: 照合する拡張子。

    Returns:
        どれかで終われば True。
    """
    lowered = name.lower()
    return any(lowered.endswith(suffix) for suffix in suffixes)


def _txt_path(raw, suffixes=_SOURCE_SUFFIXES) -> str | None:
    """現在パスから元のテキストパスを取り出す。

    Args:
        raw: 現在のパス。archive: 形式も読む。
        suffixes: 担当拡張子。

    Returns:
        テキストのパス。担当拡張子でなければ None。
    """
    if not raw:
        return None
    value = str(raw)
    if "|" in value:
        left = value.split("|", 1)[0].replace("\\", "/")
        for prefix in ("archive://", "archive:/", "archive:"):
            if left.lower().startswith(prefix):
                left = left[len(prefix):]
                break
        if len(left) >= 3 and left[0] == "/" and left[2] == ":":
            left = left[1:]
        if _has_source_suffix(left, suffixes):
            return left.replace("/", os.sep)
    if _has_source_suffix(value, suffixes):
        return value
    return None
