# EzCo プラグインマニュアル

ファイル読み込みプラグインの開発者向けリファレンスです。エンドユーザー向けの配置手順は [plugins/README.md](../plugins/README.md) を参照してください。ブラウザ向けの API 一覧はユーザーマニュアルの [プラグインリファレンス](../resources/UserManual/files/plugin-reference.html) です。同梱プラグインごとの説明は各フォルダの `README.md` にあります。

- **API バージョン**: `1`（`manifest.json` の `api_version` と一致必須）
- **配置場所**: データフォルダの `plugins/` のみ（設定の「データの置き場」。既定はこのユーザーのデータフォルダ）
- **配布形式**: ZIP（`.zip`）または同じ構成の展開フォルダ。DLL は口だけあり、現状はスキップされる
- **担当範囲**: ファイル読み込み、またはサイドバー UI。どちらも同じパッケージ + `__init__` 登録

---

## 目次

1. [概要と制約](#1-概要と制約)
2. [パッケージ構造](#2-パッケージ構造)
3. [読み込みと優先度](#3-読み込みと優先度)
4. [manifest.json](#4-manifestjson)
5. [ローダー契約 `FileLoader`](#5-ローダー契約-fileloader)
6. [ホスト API](#6-ホスト-api)
7. [多言語 `get_text`](#7-多言語-get_text)
8. [暗号化アーカイブ](#8-暗号化アーカイブ)
9. [設定キー](#9-設定キー)
10. [サンプル](#10-サンプル)
11. [トラブルシューティング](#11-トラブルシューティング)

---

## 1. 概要と制約

プラグインはホストからコールバックされるだけです。`if __name__ == "__main__"` の `main` は実行されません。

| できること | できないこと |
| --- | --- |
| 画像／アーカイブを独自に展開して画像バイトを返す | `import ez_co` / `import ez_co.*` |
| `__init__` / `setup` で拡張子とサイドバーを登録する | 他プラグインのモジュールを import する |
| `host.load_ui` で `.ui` を読む。PySide6 は import 可 | 他プラグインの設定を読む |
| ホストのパスワードダイアログを呼ぶ | ドックの貼り付け／フローティングを自分で制御する |
| プラグイン内の `langs/` `resources/` を読む | DLL プラグイン（未実装） |
| サードパーティ（`PIL`, `pyzipper` など本体依存）を import する | |

`src/` が import ルートです。同じパッケージ内の `from mark import mark_image` は許可されます。

ホストは起動時に `plugins/` を掃引し、`.zip` と `manifest.json` 付きフォルダを読み込みます。変更を反映するにはアプリの再起動が必要です。

---

## 2. パッケージ構造

ZIP または展開フォルダのルート直下に次を置きます。余分な親フォルダを挟まないでください。

```
my_plugin.zip  または  my_plugin/
├── manifest.json          # 必須
├── src/                   # 必須。import ルート
│   ├── loader.py          # entry で指定するモジュール
│   └── mark.py            # 任意のサブモジュール
├── langs/                 # 任意。ja.json / en.json
│   ├── ja.json
│   └── en.json
├── resources/             # 任意。root.read_bytes で読む
└── test/                  # 任意。ホストは読まない
```

開発中は `plugins/example_zip/` のように展開フォルダを `plugins/` 直下に置けば、そのまま読み込まれます。配布用 ZIP は [`dist-sample-plugins/`](../dist-sample-plugins/) です。同じ `id` が複数あるときは起動時にどれを読むか選びます。

```python
from pathlib import Path
import zipfile

src = Path("plugins/example_zip")
dst = Path("dist-sample-plugins/example_zip.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(src.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            zf.write(path, path.relative_to(src).as_posix())
```

---

## 3. 読み込みと優先度

### 3.1 掃引

1. `plugins/` 直下だけを見る（入れ子のサブフォルダは無視）
2. 拡張子 `.zip`、およびルートに `manifest.json` があるフォルダの `manifest.json` だけを先に読む
3. 拡張子 `.dll` は未対応のためスキップしてログを出す
4. 同じ `id` が1つなら、`api_version` がホストと一致するものだけを実体化する
5. 同じ `id` が2つ以上あるときは、未解決のときだけ起動時ダイアログで1つ（または読み込まない）を選ぶ。選択はプロファイルに保存し、その `id` は選んだファイルが残っている限り次回は聞かない。新しい重複 `id` が出たとき、または選んだファイルが消えたときだけ再表示する。選び直すときはプラグイン設定の「重複プラグインの選択」。反映は設定の OK / 適用と同じタイミング。選ばれなかったものは実体化せず、一覧に理由付きで残る

### 3.2 拡張子の担当

同じ拡張子をビルドインとプラグインの両方が宣言できます。既定は**ビルドイン優先**です。

メニューのプラグイン設定で、プラグインの ON/OFF と、拡張子ごとの「ビルドイン」「`id(ver:version)`」「読み込まない」を選べます。OFF にしたプラグインは無いものとして扱います。OK すると開いているファイルを一律再読み込みし、サイドバーも付け直します。新規 ZIP／フォルダの追加は再起動が必要です。

ビルドインに無い拡張子（例: `.ezpack`）は、プラグインが宣言すればそのプラグインが担当します。読み込み済みプラグインの拡張子は、「ファイルを開く」ダイアログの「対応しているファイル」と「プラグイン形式」に入り、フォルダを開いたときのスキャン対象にも含まれます。

### 3.3 解決順

`PluginManager.resolve_extension` の順です。

1. 設定 `plugins.extension_handlers[ext]` が `none`（読み込まない）
2. 設定が無く、旧アーカイブ設定でその種類が無効
3. 設定が `id(ver:version)`（または旧形式）で、一致するプラグインが当該拡張子を提供している
4. 設定が `builtin` で、ビルドインがその拡張子を知っている
5. ビルドインがその拡張子を知っている（設定なしの既定）
6. プラグインだけが知っている（先に掃引されたものが選ばれる）
7. どれも知らない

同じ `id` を同時にロードできるのは1つだけです。設定キーは `com.ezco.example.zip(ver:1.1.0)` です。完全一致が無いときは同じ `id` の新しいバージョンへ落ちます。

---

## 4. `manifest.json`

ホストが最初に読むメタデータです。JSON オブジェクトであること。

### フィールド

| 名前 | 型 | 必須 | 説明 |
| --- | --- | --- | --- |
| `id` | `string` | はい | プラグイン ID。同じ `id` は同時に1つだけロードする。設定キーと内部識別は `id(ver:version)`。一覧 UI の ID 列はバージョンなし。例: `com.ezco.example.zip` |
| `name` | `string` | はい | 設定ダイアログに出す表示名 |
| `version` | `string` | はい | パッケージ版。重複選択ダイアログの並びと、設定の `(ver:version)` に使う |
| `api_version` | `int` | はい | ホスト API バージョン。現在は `1` のみ |
| `entry` | `string` | はい | `モジュール:クラス`。モジュールは `src/` からのドットパス |
| `description` | `string` | いいえ | 説明。ホストは現状ログ以外では使わない |
| `author` | `string` | いいえ | 作者 |

### `entry` の解釈

```
loader:FileLoader     →  src/loader.py の FileLoader
pkg.mod:MyLoader      →  src/pkg/mod.py の MyLoader
```

`モジュール:クラス` が必須です。クラス名の省略や、ホスト側でのクラス探索はありません。

`.py` 接尾辞と `/` 区切りも受け付け、内部でドットパスに正規化します。

### 例

```json
{
  "id": "com.ezco.example.zip",
  "name": "Example ZIP Loader",
  "version": "1.1.0",
  "api_version": 1,
  "entry": "loader:FileLoader",
  "description": "Sample .zip loader.",
  "author": "EzCo"
}
```

### 検証エラー

| 条件 | 結果 |
| --- | --- |
| 必須フィールド欠落 | 読み込み失敗。`failed` に載る |
| `api_version != 1` | 読み込み失敗 |
| `entry` が `モジュール:クラス` でない | 読み込み失敗 |
| `src/` に entry モジュールが無い | 読み込み失敗 |
| 指定クラスがモジュールに無い | 読み込み失敗 |
| 対応形式もサイドバーも `setup` も無い | 読み込み失敗 |

---

## 5. ローダー契約 `FileLoader`

プラグインは `ez_co.plugins.api` を import しません。ホストが `manifest.entry` のクラスを `FileLoader(root, get_text, host)` で生成し、以降は名前の決まったメソッドを呼びます。

### 5.1 コンストラクタ

ホストは次の 1 通りだけを呼びます。

```
Class(root, get_text, host)
```

使わない引数も受け取って保持してください。ホストが渡すので、プラグイン側で探したりフォールバックしたりする必要はありません。

```python
class FileLoader:
    def __init__(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
```

| 引数 | 用途 |
| --- | --- |
| `root` | プラグイン ZIP 内のファイル。`read_bytes` / `exists` |
| `get_text` | 文言。`get_text("plugin.watermark")` |
| `host` | 登録・設定・状態参照。`host.register_format` / `register_sidebar` / `register_action` / `get_config` |

---

### `supported_formats()`

互換用です。新規は `__init__` で `host.register_format(extension, kind)` してください。ホストは掃引直後に `register_format` の結果を集め、無ければこのメソッドを呼びます。

**戻り値:** 次のいずれかのシーケンス

- `[(".zip", "archive"), (".png", "image")]`
- `[{"extension": ".zip", "kind": "archive"}]`
- `[{"ext": ".png", "type": "image"}]`

| 要素 | 説明 |
| --- | --- |
| 拡張子 | `.` 無しでもよい。内部で `.png` に正規化 |
| 種別 | `"image"` / `"img"` または `"archive"` / `"arch"` |

- `image`: ファイル自体を 1 枚の画像として開く
- `archive`: 中の画像一覧をページとして開く

**例外:** 空、または解釈不能な要素だけだと読み込み失敗。

---

### `get_file_count(file_path)`

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `file_path` | `str` | ユーザーが開いた実ファイルのパス |

**戻り値:** `int` — 画像エントリ数。ホストは `int(...)` する。

アーカイブなら `len(list_entries(file_path))` でよい。画像なら通常 `1`。

---

### `list_entries(file_path)`

ホストがアーカイブ展開時と、各ページ読み込み時に呼びます。

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `file_path` | `str` | 実ファイルのパス |

**戻り値:** エントリ名のシーケンス。各要素は `str` 化される。

- ディレクトリ名は返さない
- ホストが読める画像だけを返す（プラグイン側でフィルタしてよい）
- 暗号化アーカイブは、ここでパスワードを取らないと件数 0 になる

返した名前の順がページ順です。

---

### `read_entry(file_path, index)`

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `file_path` | `str` | 実ファイルのパス |
| `index` | `int` | `list_entries` の 0 始まりインデックス |

**戻り値:** `name` と `data` を持つオブジェクト。

| 属性 | 型 | 説明 |
| --- | --- | --- |
| `name` | `str` | エントリ名。仮想パスのファイル名になる |
| `data` | `bytes` | PNG / JPEG など、PIL が開ける画像バイト |

描画・ズーム・見開きはホストが行います。プラグインはバイトを返すだけです。

```python
class _Entry:
    def __init__(self, name, data):
        self.name = name
        self.data = data
```

**例外:** ホストは捕捉してログし、その画像を失敗扱いにする。パスワードキャンセルも例外でよい。

---

### 呼び出しタイミング

| 操作 | 呼ばれるメソッド |
| --- | --- |
| プラグイン読み込み | `register_format` または `supported_formats`。UI はあとで `setup` |
| 画像ファイルを開く | `read_entry(path, 0)` |
| アーカイブを開く | `list_entries` → 仮想パスを作る |
| ページ表示／プリフェッチ | `list_entries` のあと `read_entry(path, index)` |

`read_entry` はワーカースレッドから呼ばれることがあります。UI が必要な処理はホスト API（`ask_password` など）を使ってください。ホスト側で UI スレッドに渡します。

---

## 6. ホスト API

`ez_co` は import できません。入口はコンストラクタ引数です。

| 引数 | 例 |
| --- | --- |
| `get_text` | `self.get_text("plugin.watermark")` |
| `host` | `self.host.ask_password(...)` |
| `root` | `self.root.read_bytes("resources/icon.png")` |

同じ名前はモジュールの組み込みとしても渡します。モジュール先頭の関数から `get_text(...)` や `host.ask_password(...)` と書けます。`root` や組み込みから別経路を探さないでください。

登録（`__init__` または `setup`）:

- `host.register_format(extension, kind)` — `kind` は `"image"` / `"archive"`
- `host.register_sidebar(sidebar_id, title, widget_or_layout, aliases=None)` — `QWidget` または `QLayout`。ドック化は本体。開閉アクションも自動登録され、ショートカット／ジェスチャーに出せる。メニューは `{title}`、ショートカット／ジェスチャーの表示名は `{title}サイドバー表示/非表示`。`aliases` は旧アクション ID など
- `host.unregister_sidebar(sidebar_id)`
- `host.register_action(action_id, label, callback, aliases=None)` — 独自アクション。ショートカット／ジェスチャーから呼ばれる
- `host.unregister_action(action_id)`
- `host.load_ui(bytes_or_path)` — Designer の `.ui` を `QUiLoader` で読む
- `host.register_config(key, value_type, default=None, label=None, description=None)` — プラグイン設定ダイアログ用。`value_type` は `"bool"` / `"string"` / `"int"`。無効化してもスキーマは残るので `__init__` で登録してよい

状態:

- `host.get_current(key)` — `"path"` / `"folder"` / `"page"`
- `host.reload_current(page=None)` — 現在のファイルを開き直す（画像キャッシュも消える）。`page` は 1 始まり。省略時は今のページ
- `host.on(event, callback)` / `host.off(event, callback)` — `"current_changed"` / `"config_changed"`
- `host.get_app_config()` — `language` / `viewer` / `cache` / `ui_font` の読み取り専用

自プラグイン設定（DB の `plugin_id` はハッシュ化。他プラグインの行は読めない）:

- `host.get_config(key, default=None)` — 未保存ならスキーマの `default`
- `host.set_config(key, value)` — 型を正規化して保存し、そのプラグインへ `"config_changed"`（`{key, value}`）
- `host.delete_config(key)`

プラグイン設定の一覧にスキーマがある行は「設定」ボタンが出ます。そこでパネルを開き OK すると、本体ダイアログの OK を待たずに DB へ保存して通知します。

UI の再接続用に任意の `setup()` / `teardown()` を実装できます。無効化すると本体はサイドバーと登録アクションを外します。

---

### `get_text`

```text
get_text(key: str, **kwargs) -> str
```

プラグインまたは本体の文言を返す。

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `key` | `str` | ドット区切りキー。例: `plugin.watermark` |
| `**kwargs` | | `str.format(**kwargs)` に渡す |

**戻り値:** 見つかった文字列。無ければ本体の `get_text` に委譲。本体にも無ければキー自身など本体の既定。

**探索順**

1. プラグイン `langs/{現在言語}.json`
2. プラグイン `langs/ja.json` または `en.json`（フォールバック）
3. プラグイン `src/langs/{言語}.json`（互換）
4. 本体の言語ファイル

同じキーはプラグイン側が優先されます。言語は本体の現在言語です。

---

### `root`（`ZipPluginRoot`）

プラグイン ZIP 内リソースへの入口。

#### 属性

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `zip_path` | `Path` | 読み込んだプラグイン ZIP のパス |
| `get_text` | `callable` | コンストラクタの `get_text` と同じ |
| `host` | `PluginHost` | コンストラクタの `host` と同じ |

#### `root.read_bytes(relative_path)`

```text
read_bytes(relative_path: str) -> bytes
```

ZIP 内の相対パスを読む。`\\` は `/` に直し、先頭 `/` は除く。

**例外:** エントリが無ければ `KeyError`。

#### `root.exists(relative_path)`

```text
exists(relative_path: str) -> bool
```

ZIP 内にその相対パスがあるか。

`test/` はホストが自動では使いません。自分で `read_bytes("test/foo.bin")` すれば読めます。

---

### `ask_password`

```text
ask_password(file_path: str, mismatch: bool = False, verify=None) -> str | None
```

本体のアーカイブパスワードダイアログを出す。セッションキャッシュと履歴（Windows DPAPI）も見る。

**引数**

| 名前 | 型 | 既定 | 説明 |
| --- | --- | --- | --- |
| `file_path` | `str` | | 対象ファイル。キャッシュ／履歴のキー |
| `mismatch` | `bool` | `False` | 初回から「一致しません」を出すか。履歴不一致時はホストが True にする |
| `verify` | `callable` or `None` | `None` | `verify(password: str) -> bool`。False なら再入力 |

**戻り値**

| 値 | 意味 |
| --- | --- |
| `str` | 確定したパスワード。空文字もあり得る |
| `None` | キャンセル、または閉じる／X でアプリ終了 |

**処理順**

1. セッションにパスワードがあれば `verify`（無ければ成功）
2. 履歴の保存パスワードがあれば同様。失敗なら `mismatch=True` でダイアログ
3. ダイアログ。成功したらセッションに保存
4. 閉じる／X → アプリ終了、`None`

ワーカーから呼んでも UI スレッドで実行されます。`verify` も UI スレッドで走ります。重い処理は避けてください。

```python
password = ask_password(file_path, verify=lambda pwd: _can_open(file_path, pwd))
if password is None:
    raise RuntimeError("password cancelled")
```

---

### `show_dialog`

```text
show_dialog(name: str, **kwargs) -> Any
```

名前でホストのダイアログを選ぶ口。今ある実装はパスワードのみ。

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `name` | `str` | ダイアログ名。大小無視 |
| `file_path` / `path` | `str` | パスワード対象 |
| `mismatch` | `bool` | `ask_password` と同じ |
| `verify` | `callable` | `ask_password` と同じ |

**`name`**

| 値 | 動作 |
| --- | --- |
| `password` | `ask_password` |
| `archive_password` | 同上 |
| `ask_password` | 同上 |
| それ以外 | 警告ログ、`None` |

```python
password = show_dialog("password", file_path=file_path, verify=fn)
```

---

### `register_action`

```text
register_action(action_id: str, label: str, callback, aliases=None) -> None
```

プラグイン独自のアクションを登録する。ショートカット設定とジェスチャー設定の候補に出る。無効化すると登録は外れる。割り当て自体は設定に残る。

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `action_id` | `str` | プラグイン内で一意。`sidebar` と `:` は使えない |
| `label` | `str` | ダイアログに出す表示名 |
| `callback` | callable | UI スレッドで呼ばれる |
| `aliases` | 文字列または列 | 旧 ID など。本体はプラグイン固有の ID を持たない |

公開 ID は `plugin:{plugin_id}:{action_id}`。`register_sidebar` の開閉は `plugin:{plugin_id}:sidebar:{sidebar_id}`。既定ショートカットは付かない。既存のショートカット ID を残したいときはプラグイン側で `aliases` を渡す。

```python
self.host.register_sidebar("main", self.get_text("title"), self.widget, aliases=("old_toggle_id",))
self.host.register_action("refresh", self.get_text("refresh"), self.refresh)
```

---

### `run_action`

```text
run_action(action_id: str, **kwargs) -> bool
```

本体または登録済みプラグインのアクションを呼ぶ。

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `action_id` | `str` | 本体の `Actions` の値（例: `new_tab`）またはプラグインの公開 ID |
| `**kwargs` | | 未使用 |

**戻り値:** 実行できれば `True`。未対応の本体アクションは `False`。

---

### `host`（`PluginHost`）

`ask_password` / `show_dialog` / `run_action` を持つオブジェクト。コンストラクタの第 3 引数です。プラグインから `bind` を呼ぶ必要はありません。ホストがウィンドウ初期化時に親ウィジェットと DB を結びます。

```python
password = self.host.ask_password(file_path, verify=fn)
```

---

## 7. 多言語 `get_text`

`langs/ja.json` / `langs/en.json` は入れ子オブジェクトです。キーはドットで辿ります。

```json
{
  "plugin": {
    "watermark": "プラグイン読み込み表示"
  }
}
```

```python
label = get_text("plugin.watermark")
# プレースホルダ
# langs: { "plugin.count": "{n} 件" }
get_text("plugin.count", n=3)
```

`\\n` は改行に展開されます。本体と同じキーを置けば、プラグイン文言が本体より優先されます。

---

## 8. 暗号化アーカイブ

プラグイン担当の拡張子では、ホストの `_ensure_archive_unlocked` は走りません。パスワードが必要ならプラグインが `ask_password` してください。

推奨:

1. 暗号化されていなければダイアログを出さない
2. `verify` で実際に 1 エントリ読めるか試す
3. 成功パスワードをパス単位でキャッシュする
4. ZIP は `pyzipper.AESZipFile` を使う（ZipCrypto と WinZip AES の両方）

本体のビルドイン ZIP も `pyzipper.AESZipFile` です。標準 `zipfile` は AES（compress=99）を解けません。

閉じる／X はアプリ終了です。プラグインは `None` を受けて展開を打ち切ります。

---

## 9. 設定キー

プロファイル設定（`profile_settings`）に保存されます。

```yaml
plugins:
  enabled:
    com.ezco.example.zip: true
  source_choice:
    com.ezco.example.zip:
      source: example_zip
      seen: [example_zip, example_zip.zip]
  extension_handlers:
    .zip: com.ezco.example.zip(ver:1.1.0)
    .png: builtin
    .7z: none
  dialog:
    plugin_table:
      order: [enabled, name, id, version, kind, extensions, status, settings]
      widths: {enabled: 56, name: 160, id: 200, version: 72, kind: 90, extensions: 90, status: 110}
    ext_table:
      order: [extension, kind, handler]
      widths: {extension: 100, kind: 110, handler: 280}
```

| キー | 型 | 説明 |
| --- | --- | --- |
| `plugins.enabled` | `object` | `plugin_id` → 有効か。未記載は有効。ロード済みプラグインだけが対象 |
| `plugins.extension_handlers` | `object` | 拡張子 → `"builtin"`、`id(ver:version)`、または `"none"`（読み込まない）。旧形式も読む |
| `plugins.source_choice` | `object` | 重複 `id` → `{source, seen}`。`source` は `plugins/` 直下の名前、または `"none"`。選んだソースが残っている限り起動時は聞かない。切り替えるときはプラグイン設定の「重複プラグインの選択」 |
| `plugins.dialog` | `object` | プラグイン設定ダイアログの列順と幅。OK / キャンセルどちらでも保存する |

プラグイン固有の値は `plugin_settings` テーブルに、`plugin_id` のハッシュで保存します。プラグイン API に id 引数はありません。

UI は「プラグイン設定」ダイアログです。ON/OFF と読み込み方式を扱います。OFF にしたプラグインが担当していた拡張子は、ビルドイン → 他プラグイン → 行削除の順で付け替えます。ID に `(ver:)` は付けません。

---

## 10. サンプル

| パス | 内容 |
| --- | --- |
| `plugins/example_png/` | `.png` を `image` として読む。色重ねは確認用。ZIP は `dist-sample-plugins/` |
| `plugins/example_zip/` | `.zip` を `archive` として読む。パスワードダイアログの呼び方も含む |
| `plugins/example_txt/` | `.txt` を `archive` として読む。本文をページ画像にする。サイドバーで字体・色・縦読み／横読みを即時反映 |
| `plugins/product_info/` | 商品情報サイドバー。`resources/sidebar.ui` を `load_ui` で読む。`info.json` が無くフォルダ／ファイル名が DLsite / DMM 番号なら、標準ライブラリだけで非同期取得（ディスクには書かない。設定で OFF 可） |

ソースの `loader.py` 先頭にホスト契約のコメントがあります。確認するときはプラグイン設定で当該拡張子の読み込み方式をサンプル側にして OK してください。開いているファイルはすぐ再読み込みされます。新規に ZIP やフォルダを置いた直後だけ再起動してください。

色と「プラグイン読み込み表示」はサンプル固有です。本番では画像バイトをそのまま返してください。

---

## 11. トラブルシューティング

| 症状 | 確認 |
| --- | --- |
| 一覧に出ない | `plugins/` 直下の `.zip` か、`manifest.json` 付きフォルダか。ZIP／フォルダのルートが `manifest.json` か。`api_version` が `1` か。同じ `id` で「読み込まない」を選んでいないか |
| 起動時に重複ダイアログが出る | 未解決の重複 `id` がある。すでに選んだ `id` は、選んだファイルが残っていれば再表示しない。選び直すときはプラグイン設定 |
| ビルドインのまま開く | プラグイン設定の読み込み方式と ON/OFF。OK したか。新規 ZIP／フォルダなら再起動したか |
| `ImportError: ez_co` | プラグインから `ez_co` を import している |
| パスワードが一致しない | AES なのに標準 `zipfile` を使っていないか。`verify` の例外をログで見る |
| ダイアログが出ない | `list_entries` より前に暗号化判定して `self.host.ask_password` しているか |
| 件数 0 | 画像拡張子フィルタ、パスワード未解除、エントリがディレクトリだけ |
| 文言がキーのまま | `langs/ja.json` の入れ子と `get_text` のキーが一致しているか |

開発時は設定のデバッグモードを有効にすると、掃引・読み込み失敗・パスワード検証がログに出ます。
