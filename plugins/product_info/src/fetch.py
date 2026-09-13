"""DLsite / DMM からサイドバー用の項目だけ取る。標準ライブラリのみ。"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_DLSITE_ID = re.compile(r"[RVBA]J\d{6,8}", re.IGNORECASE)
_DMM_ID = re.compile(r"d_\d{6}", re.IGNORECASE)
_DLSOFT_ID = re.compile(r"(?:dlsoft_)?([a-zA-Z]{3,}_\d{4})")
_TIMEOUT = 12
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EzCo-ProductInfo/1.0"
_DLSITE_TYPES = ("maniax", "books", "home", "pro")


def match_product(text: str):
    if not text:
        return None
    found = _DLSITE_ID.search(text)
    if found:
        return ("dlsite", found.group().upper())
    found = _DMM_ID.search(text)
    if found:
        return ("dmm", found.group().lower())
    found = _DLSOFT_ID.search(text)
    if found:
        return ("dlsoft", found.group(1))
    return None


def fetch_product(kind: str, product_id: str) -> Optional[dict]:
    if kind == "dlsite":
        return _fetch_dlsite(product_id)
    if kind == "dmm":
        return _fetch_dmm(product_id)
    if kind == "dlsoft":
        return _fetch_dlsoft(product_id)
    return None


class _Node:
    __slots__ = ("tag", "attrs", "text", "children", "parent")

    def __init__(self, tag, attrs, parent=None):
        self.tag = tag
        self.attrs = dict(attrs)
        self.text = []
        self.children = []
        self.parent = parent


class _TreeParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {})
        self._cur = self.root

    def handle_starttag(self, tag, attrs):
        node = _Node(tag.lower(), attrs, self._cur)
        self._cur.children.append(node)
        if tag.lower() not in ("br", "img", "input", "meta", "link", "hr", "source"):
            self._cur = node

    def handle_endtag(self, tag):
        tag = tag.lower()
        cur = self._cur
        while cur is not None and cur.tag != "root":
            if cur.tag == tag:
                self._cur = cur.parent or self.root
                return
            cur = cur.parent

    def handle_data(self, data):
        if data:
            self._cur.text.append(data)


def _parse(html: str) -> _Node:
    parser = _TreeParser()
    parser.feed(html)
    parser.close()
    return parser.root


def _attr(node: _Node, name: str) -> str:
    return node.attrs.get(name) or node.attrs.get(name.lower()) or ""


def _id(node: _Node) -> str:
    return _attr(node, "id")


def _classes(node: _Node) -> set[str]:
    return {part for part in _attr(node, "class").split() if part}


def _own_text(node: _Node) -> str:
    return "".join(node.text).strip()


def _text(node: _Node) -> str:
    parts = ["".join(node.text)]
    for child in node.children:
        parts.append(_text(child))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _walk(node: _Node):
    yield node
    for child in node.children:
        yield from _walk(child)


def _by_id(root: _Node, value: str) -> Optional[_Node]:
    for node in _walk(root):
        if _id(node) == value:
            return node
    return None


def _by_class(root: _Node, name: str):
    return [node for node in _walk(root) if name in _classes(node)]


def _download(url: str, cookie: str = "") -> Optional[bytes]:
    headers = {"User-Agent": _USER_AGENT, "Accept": "text/html,image/*,*/*;q=0.8"}
    if cookie:
        headers["Cookie"] = cookie
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=_TIMEOUT) as response:
            if getattr(response, "status", 200) != 200:
                return None
            return response.read()
    except (HTTPError, URLError, TimeoutError, OSError):
        return None


def _abs_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    return url


def _cover_from_url(url: str, cookie: str = "") -> Optional[bytes]:
    if not url:
        return None
    return _download(_abs_url(url), cookie)


def _outline_value(root: _Node, label: str) -> str:
    outline = _by_id(root, "work_outline")
    if outline is None:
        return ""
    for row in _walk(outline):
        if row.tag != "tr":
            continue
        th = next((child for child in row.children if child.tag == "th"), None)
        if th is None or label not in _text(th):
            continue
        return _text(row).replace(_text(th), "", 1).strip()
    return ""


def _fetch_dlsite(product_id: str) -> Optional[dict]:
    html = None
    page_url = ""
    category = ""
    for kind in _DLSITE_TYPES:
        page_url = f"https://www.dlsite.com/{kind}/work/=/product_id/{product_id}.html"
        data = _download(page_url)
        if not data:
            continue
        html = data.decode("utf-8", "replace")
        if 'id="work_name"' in html or "work_name" in html:
            category = kind
            break
        html = None
    if not html:
        return None
    root = _parse(html)
    title_node = _by_id(root, "work_name")
    title = _text(title_node) if title_node else ""
    maker = _by_id(root, "work_maker")
    brand = ""
    if maker is not None:
        link = next((node for node in _walk(maker) if node.tag == "a"), None)
        brand = _text(link) if link is not None else _text(maker)
    category_type = _by_id(root, "category_type")
    work_formats = []
    if category_type is not None:
        work_formats = [_text(node) for node in _walk(category_type) if node.tag == "span" and _text(node)]
    genres = [_text(node) for node in _by_class(root, "main_genre") for node in _walk(node) if node.tag == "a"]
    if not genres:
        genres = [_text(node) for node in _walk(root) if node.tag == "a" and "main_genre" in _classes(node.parent or node)]
    overview_nodes = _by_class(root, "work_parts_container")
    overview = _text(overview_nodes[0]) if overview_nodes else ""
    cover_url = ""
    for node in _by_class(root, "product-slider-data"):
        for child in _walk(node):
            src = _attr(child, "data-src")
            if src:
                cover_url = src
                break
        if cover_url:
            break
    work_type = work_formats[0] if work_formats else ""
    result = {
        "タイトル": title,
        "URL": page_url,
        "PID": product_id,
        "カテゴリー": category,
        "ブランド名": brand,
        "年齢種別": _outline_value(root, "年齢指定"),
        "作品種別": work_type,
        "作品形式": work_formats,
        "ファイル形式": _outline_value(root, "ファイル形式"),
        "genre一覧": ", ".join(item for item in genres if item),
        "概要": overview,
        "_cover": _cover_from_url(cover_url),
    }
    if not result["タイトル"] and not result["PID"]:
        return None
    return result


def _fetch_dmm(product_id: str) -> Optional[dict]:
    page_url = f"https://www.dmm.co.jp/dc/doujin/-/detail/=/cid={product_id}/"
    data = _download(page_url, cookie="age_check_done=1")
    if not data:
        return None
    root = _parse(data.decode("utf-8", "replace"))
    titles = _by_class(root, "productTitle")
    title = ""
    if titles:
        h1 = next((node for node in _walk(titles[0]) if node.tag == "h1"), titles[0])
        title = _own_text(h1) or _text(h1)
    brands = _by_class(root, "circleName__txt")
    brand = _text(brands[0]) if brands else ""
    genres = [_text(node) for node in _by_class(root, "genreTag__txt") if _text(node)]
    summaries = _by_class(root, "summary__txt")
    overview = _text(summaries[0]) if summaries else ""
    cover_url = ""
    for node in _by_class(root, "productPreview__item"):
        img = next((child for child in _walk(node) if child.tag == "img"), None)
        if img is not None:
            cover_url = _attr(img, "src") or _attr(img, "data-src")
            if cover_url:
                break
    return {
        "タイトル": title,
        "URL": page_url,
        "PID": product_id,
        "カテゴリー": "",
        "ブランド名": brand,
        "年齢種別": "",
        "作品種別": "DMM",
        "作品形式": [],
        "ファイル形式": "",
        "genre一覧": ", ".join(genres),
        "概要": overview,
        "_cover": _cover_from_url(cover_url, cookie="age_check_done=1"),
    }


def _fetch_dlsoft(product_id: str) -> Optional[dict]:
    page_url = f"https://dlsoft.dmm.co.jp/detail/{product_id}/"
    data = _download(page_url, cookie="age_check_done=1")
    if not data:
        return None
    root = _parse(data.decode("utf-8", "replace"))
    titles = _by_class(root, "productTitle")
    title = _text(titles[0]) if titles else ""
    brand = ""
    genres = []
    for node in _walk(root):
        if node.tag in ("th", "dt") and _text(node) == "ブランド":
            nxt = _next_data_cell(node)
            if nxt is not None:
                brand = _text(nxt)
        if node.tag in ("th", "dt") and _text(node) == "ジャンル":
            nxt = _next_data_cell(node)
            if nxt is not None:
                genres = [_text(child) for child in _walk(nxt) if child.tag == "a" and _text(child)]
    overviews = _by_class(root, "area-detail-read")
    overview = _text(overviews[0]) if overviews else ""
    cover_url = ""
    for node in _by_class(root, "image-slider"):
        img = next((child for child in _walk(node) if child.tag == "img"), None)
        if img is not None:
            cover_url = _attr(img, "src") or _attr(img, "data-src")
            if cover_url:
                break
    return {
        "タイトル": title,
        "URL": page_url,
        "PID": product_id,
        "カテゴリー": "",
        "ブランド名": brand,
        "年齢種別": "",
        "作品種別": "DMM",
        "作品形式": [],
        "ファイル形式": "",
        "genre一覧": ", ".join(genres),
        "概要": overview,
        "_cover": _cover_from_url(cover_url, cookie="age_check_done=1"),
    }


def _next_data_cell(node: _Node) -> Optional[_Node]:
    parent = node.parent
    if parent is None:
        return None
    siblings = parent.children
    try:
        index = siblings.index(node)
    except ValueError:
        return None
    if index + 1 < len(siblings):
        return siblings[index + 1]
    uncle = parent.parent
    if uncle is None:
        return None
    row_kids = uncle.children
    try:
        row_index = row_kids.index(parent)
    except ValueError:
        return None
    if row_index + 1 < len(row_kids):
        return row_kids[row_index + 1]
    return None
