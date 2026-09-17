# EzCo プラグインマニュアル

プラグインの開発者向けリファレンスです。エンドユーザー向けの配置手順は [plugins/README.md](../plugins/README.md) を参照してください。ブラウザ向けの API 一覧はユーザーマニュアルの [プラグインリファレンス](../resources/UserManual/files/plugin-reference.html) です。同梱プラグインごとの説明は各フォルダの `README.md` にあります。本体側の発見・有効化・拡張子解決は [ARCHITECTURE.md](ARCHITECTURE.md)、なぜその境界かは [DECISIONS.md](DECISIONS.md) です。

- **API バージョン**: `1`（`manifest.json` の `api_version` と一致必須）
- **配置場所**: データフォルダの `plugins/` のみ（設定の「データの置き場」。既定はこのユーザーのデータフォルダ）
- **配布形式**: ZIP（`.zip`）または同じ構成の展開フォルダ。DLL は未対応
- **担当範囲**: ファイル読み込み、サイドバー、表示フィルター。1つのプラグインがいくつでも持てる。入口は `Class()` と `load(root, get_text, host)`
- **信用**: 本体は中身を検査しない。責任は配布者と導入した使用者。詳細は [plugins/README.md](../plugins/README.md)

---

## 目次

1. [概要と制約](#1-概要と制約)
2. [パッケージ構造](#2-パッケージ構造)
3. [読み込みと優先度](#3-読み込みと優先度)
4. [manifest.json](#4-manifestjson)（[権限](#マニフェスト権限)）
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
| `load` で `register_config` / `register_config_json`、`setup` でサイドバーとフィルターを登録する | 他プラグインのモジュールを import する |
| `host.load_ui` で `.ui` を読む。PySide6 は import 可 | 他プラグインの設定を読む |
| ホストのパスワードダイアログを呼ぶ | ドックの貼り付け／フローティングを自分で制御する |
| プラグイン内の `resources/langs` と `resources/` を読む | DLL プラグイン（未対応） |
| サードパーティ（`PIL`, `pyzipper` など本体依存）を import する | |

役割はクラスを分けなくてよい。同じ入口が全部持てる。

| 役割 | マニフェスト | コード |
| --- | --- | --- |
| ファイル読み込み | `formats` | `get_file_count` / `list_entries` / `read_entry` |
| サイドバー | `sidebar: true` | `setup()` で `register_sidebar` |
| 表示フィルター | `permissions.filter: true` | `setup()` で `register_filter`。有効化はフィルターメニュー |
| 設定項目 | なし | `load()` で `register_config` / `register_config_json` |

`formats` も `sidebar` も無く `setup()` も無いと読み込み失敗。フィルターだけなら `permissions.filter` と `setup()` で足りる。

`src/` が import ルートです。同じパッケージ内の `from mark import mark_image` は許可されます。`import ez_co` の禁止は本体との結合事故を防ぐためであり、サンドボックスではありません。プラグインはアプリと同じ権限で動きます。中身は検査しません。悪意のあるコードや欠陥による損害について、EzCo の開発者は責任を負いません。責任は配布者と、それを導入した使用者にあります。利用者向けの注意は [plugins/README.md](../plugins/README.md) です。

ホストは起動時に `plugins/` を掃引し、`.zip` と `manifest.json` 付きフォルダを読み込みます。**新しい ZIP／フォルダを置いた（または消した）あとは再起動**が必要です。ON/OFF、拡張子の担当、重複の選び直しはプラグイン設定の OK / 適用で足り、再起動は不要です。

---

## 2. パッケージ構造

ZIP または展開フォルダのルート直下に次を置きます。余分な親フォルダを挟まないでください。

```
my_plugin.zip  または  my_plugin/
├── manifest.json          # 必須
├── src/                   # 必須。import ルート
│   ├── plugin.py          # entry。サンプルと新規はここ
│   └── mark.py            # 任意のサブモジュール
├── resources/
│   ├── langs/             # 新規の文言。ja.json / en.json
│   ├── ui/                # 任意。.ui。空フォルダは作らない
│   ├── assets/            # 任意。画像・音。空フォルダは作らない
│   └── config/            # 任意。設定 JSON。空フォルダは作らない
├── LICENSE.md             # 任意。設定の「ライセンス」。.md → .txt → 無印の順
└── test/                  # 任意。ホストは読まない
```

新規向けの最小ツリーは `resources/langs` だけです。旧 `langs/` と `src/langs/` はまだ読みますが、選択肢としては載せません。`host.load_ui` は bytes と OS パスのままです。`.ui` は `host.load_ui(self.root.read_ui("sidebar.ui"))` です。

ルート直下の `LICENSE.md`（Markdown）/ `LICENSE.txt` / `LICENSE`（テキスト）があると、プラグイン設定のライセンス列から読めます。複数あれば上だけ。表示は保証ではありません。起動時には出しません。

開発中は `plugins/example_zip/` のように展開フォルダを `plugins/` 直下に置けば、そのまま読み込まれます。配布用 ZIP は [`dist-sample-plugins/`](../dist-sample-plugins/) です。作り直しはタスク **「EzCo: プラグインZIP」** または `poetry run pack-plugins` です。出力名は `<フォルダ>-<manifest.version>.zip` です。`manifest.json` の構文・契約・バージョン形式・権限がおかしいものはログしてスキップし、最後に成功／失敗件数を出します。同じ `id` が複数あるときは起動時にどれを読むか選びます。

---

## 3. 読み込みと優先度

### 3.1 掃引

1. `plugins/` 直下だけを見る（入れ子のサブフォルダは無視）
2. 拡張子 `.zip`、およびルートに `manifest.json` があるフォルダの `manifest.json` だけを先に読む
3. 拡張子 `.dll` は未対応のためスキップしてログを出す
4. 候補があり、このユーザーの同意バージョンが `src/ez_co/resources/plugin_consent/version.txt` と一致しなければはい／いいえの確認を出す。本文は同フォルダの `ja.md` / `en.md`。いいえなら実体化せず、プラグイン設定メニューも出さない。次回起動でも聞く。はいなら `user.json` の `plugin_consent_version` にその値を書く。同意文を変えたら `version.txt` を上げると再表示する
5. 同意済みで同じ `id` が1つなら、`api_version` がホストと一致するものだけを実体化する
6. 同意済みで同じ `id` が2つ以上あるときは、未解決のときだけ起動時ダイアログで1つ（または読み込まない）を選ぶ。選択はプロファイルに保存し、その `id` は選んだファイルが残っている限り次回は聞かない。新しい重複 `id` が出たとき、または選んだファイルが消えたときだけ再表示する。選び直すときはプラグイン設定の「重複プラグインの選択」。反映は設定の OK / 適用と同じタイミング。選ばれなかったものは実体化せず、一覧に理由付きで残る

### 3.2 拡張子の担当

同じ拡張子をビルドインとプラグインの両方が宣言できます。既定は**ビルドイン優先**です。

メニューのプラグイン設定で、プラグインの ON/OFF と、拡張子ごとの「ビルドイン」「`id(ver:version)`」「読み込まない」を選べます。OFF にしたプラグインは無いものとして扱います。OK / 適用で開いているファイルを一律再読み込みし、サイドバーも付け直します（再起動は不要）。新規 ZIP／フォルダの追加・削除だけ再起動が必要です。

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
| `permissions` | `object` | いいえ | マニフェスト権限。本体だけが読む。詳細は下 |
| `formats` | `array` | いいえ | 担当形式。これが正。`[[".zip", "archive"]]` または `{ext, kind}`。`ext` は string または配列。`extension` / `type` は読まない |
| `sidebar` | `bool` | いいえ | サイドバーを使う宣言。widget や ID は書かない。実体は `register_sidebar` |

### マニフェスト権限

`permissions` は本体がロード前に読む力です。OS のサンドボックスではありません。未知キーは無視。値は JSON の `true` / `false` のみ（文字列 `"false"` や `1` は読み込み失敗）。`register_sidebar` / `register_filter` の引数では渡せません。

| キー | ないと | あると |
| --- | --- | --- |
| `filter` | `register_filter` は読み込み失敗 | 表示フィルターを台帳へ載せられる。登録しただけでは動かない。ユーザーがフィルターメニューで有効化した ID だけが pipe に入る |
| `inactive_callback` | サイドバーを登録したプラグインは、ドックが全部非表示のとき `current_changed` を受け取らない | 非表示でも届く。拡張子だけのプラグインは書かない |

### `entry` の解釈

```
plugin:FileLoader     →  src/plugin.py の FileLoader
pkg.mod:MyLoader      →  src/pkg/mod.py の MyLoader
```

`モジュール:クラス` が必須です。クラス名の省略や、ホスト側でのクラス探索はありません。リポジトリのサンプルと新規プラグインの入口は `src/plugin.py`（`entry` は `plugin:クラス名`）に揃えます。ホストは他のモジュール名も受け付けますが、同じ役割のファイル名をサンプル間で混ぜません。

`.py` 接尾辞と `/` 区切りも受け付け、内部でドットパスに正規化します。

### 例

```json
{
  "id": "com.ezco.example.zip",
  "name": "Example ZIP Loader",
  "version": "1.1.0",
  "api_version": 1,
  "entry": "plugin:FileLoader",
  "description": "Sample .zip loader.",
  "author": "EzCo",
  "formats": [[".zip", "archive"]]
}
```

```json
{
  "id": "com.ezco.example_txt",
  "name": "Example Text Pages",
  "version": "1.0.0",
  "api_version": 1,
  "entry": "plugin:TextImagePlugin",
  "formats": [[[".txt", ".log"], "archive"]],
  "sidebar": true
}
```

```json
{
  "id": "com.ezco.example.filter",
  "name": "Example Filter",
  "version": "1.0.0",
  "api_version": 1,
  "entry": "plugin:ExampleFilterPlugin",
  "permissions": {
    "filter": true
  }
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
| `permissions` の既知キーが JSON bool でない | 読み込み失敗 |

---

## 5. ローダー契約 `FileLoader`

プラグインは `ez_co.plugins.api` を import しません。ホストが `manifest.entry` のクラスを `Class()` で生成し、必須の `load(root, get_text, host)` のあと名前の決まったメソッドを呼びます。

### 5.1 生成と `load`

ホストは `Class()` のあと、必須の `load(root, get_text, host)` を呼びます。`__init__` はクラス内で完結するフィールドだけです。`root` / `get_text` / `host` は `load` の引数で受け取ります。`__init__` で `register_*` / `on` / `off` すると読み込み失敗です。

```python
class FileLoader:
    def __init__(self):
        self.root = None
        self.get_text = None
        self.host = None

    def load(self, root, get_text, host):
        self.root = root
        self.get_text = get_text
        self.host = host
```

| 引数 | 用途 |
| --- | --- |
| `root` | プラグイン ZIP 内のファイル。`read_bytes` / `exists` |
| `get_text` | 文言。`get_text("plugin.watermark")` |
| `host` | 登録・設定・状態参照。`register_config` / `register_config_json` は `load` 以降。`register_sidebar`（`sidebar: true` のときだけ） / `register_action` / `register_filter`（`permissions.filter` のときだけ）は `setup` |

担当形式は `manifest.json` の `formats` が正です。本体がロード時に読みます。

| 要素 | 説明 |
| --- | --- |
| 拡張子 | `.` 無しでもよい。内部で `.png` に正規化。オブジェクトは `ext`、配列は第1要素。どちらも string または配列 |
| 種別 | `"image"` / `"img"` または `"archive"` / `"arch"`。オブジェクトは `kind`、配列は第2要素 |

- `image`: ファイル自体を 1 枚の画像として開く
- `archive`: 中の画像一覧をページとして開く

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
| プラグイン読み込み | `manifest.formats`。UI はあとで `setup` |
| 画像ファイルを開く | `read_entry(path, 0)` |
| アーカイブを開く | `list_entries` → 仮想パスを作る |
| ページ表示／プリフェッチ | `list_entries` のあと `read_entry(path, index)` |

`read_entry` はワーカースレッドから呼ばれることがあります。UI が必要な処理はホスト API（`ask_password` など）を使ってください。ホスト側で UI スレッドに渡します。

---

## 6. ホスト API

`ez_co` は import できません。入口は `load(root, get_text, host)` の引数です。

| 引数 | 例 |
| --- | --- |
| `get_text` | `self.get_text("plugin.watermark")` |
| `host` | `self.host.ask_password(...)` |
| `root` | `self.root.read_ui("sidebar.ui")` / `self.root.read_asset("icon.png")` |

同じ名前はモジュールの組み込みとしても渡します。モジュール先頭の関数から `get_text(...)` や `host.ask_password(...)` と書けます。`root` や組み込みから別経路を探さないでください。`host` のメソッドは `self.host.ask_password` のように直接呼びます。`getattr` / `hasattr` / `setattr` で有無を見ません。足りない API は host に足します。

登録（`load` または `setup`）:

- `host.register_sidebar(sidebar_id, title, widget_or_layout, aliases=None)` — `QWidget` または `QLayout`。ドック化は本体。開閉アクションも自動登録され、ショートカット／ジェスチャーに出せる。メニューは `{title}`、ショートカット／ジェスチャーの表示名は `{title}サイドバー表示/非表示`。`aliases` は旧アクション ID など。権限はここへ渡さない。`manifest.sidebar` が `true` のときだけ。未宣言は `PluginRegistrationDenied`。プラグインは使わず、設定画面は「失敗: 権限がない登録がありました」
- `host.unregister_sidebar(sidebar_id)` — 有効中に1件外す。無効化は `clear_plugin`
- `host.register_action(action_id, label, callback, aliases=None)` — 独自アクション。ショートカット／ジェスチャーから呼ばれる
- `host.unregister_action(action_id)` — 有効中に1件外す。無効化は `clear_plugin`
- `host.register_filter(filter_id, title, process)` — 表示画像の加工。`permissions.filter` が `true` のときだけ。無ければ `PluginRegistrationDenied`。プラグインは使わず、設定画面は「失敗: 権限がない登録がありました」。公開 ID は `plugin:{plugin_id}:{filter_id}`。`setup()` で複数回呼んでよい（`filter_id` が違えば別レコード）。同じ `filter_id` の再登録は上書き。値は既存の `register_config`（フィルター専用の config API は無い）。v1 の `process(image, context)` は同期・短時間向け。`context` は path / page / size。Host は入らない。登録しただけでは呼ばない。本体の pipe に載り、かつ台帳にあるときだけ
- `host.unregister_filter(filter_id)` — 有効中に台帳からその1件を消す。pipe は触らない（ユーザーの ON 記憶を残す）。無効化は `clear_plugin`
- `host.load_ui(bytes_or_path)` — Designer の `.ui` を `QUiLoader` で読む。引数は bytes または OS パス。意味は変えない
- `host.register_config_json(name)` — `resources/config/` からの相対ファイル名。`load` で明示。自動では読まない。bytes / list は受け取らない。中身はフィールド配列。キーは `register_config` と同じ。未知キーはエラー。`choices` にクラス名、`enum` / `enum_type` はエラー（Enum はコードの `register_config` だけ）。表示文字列は `{key}` テンプレートのまま台帳へ載せる。途中失敗は `load` 例外 → `abort_load`（そのプラグインのスキーマごと消える）
- `host.register_config(key, value_type, default=None, label=None, description=None, choices=None, minimum=None, maximum=None, step=None, path_kind=None, path_filter=None, sync=False, reload=False, multiple=False, suffix=None, required=False)` — プラグイン設定ダイアログ用。`value_type` は `"bool"` / `"string"` / `"int"` / `"float"` / `"int_range"` / `"float_range"` / `"path"` / `"password"` / `"color"` / `"date"` / `"datetime"` / `"choice"` / `"font"` / `"charset"` / `"language"` / `"country"`。`choice` は `choices`（値の列、`(value, label)`、または `Enum` / member 列）。Enum を渡したときだけ `get_config` / `config_changed` は member。DB は canonical な `.name`（既存設定を残すなら member 名を変えない）。未知の name は default。複数で1件でも未知なら default 全体。`charset` / `language` / `country` は本体が一覧を持つ（表示は母語名。アプリ言語には合わせない）。`multiple=True` は JSON 配列。`[]` は補完しない（0件可）。`required=True` は empty を保存しない（`set_config` は False。プラグイン ACTIVE にはしない）。空を表現できない型では `required` は実質 no-op。`suffix` は数値の表示のみ。`description` があるときだけホバー。`int_range` / `float_range` は `minimum` / `maximum` / `step` が必須。`path` は `path_kind` が `"file"`（省略時）または `"directory"`。`password` は画面マスク、DB は DPAPI、`get_config` は平文。`sync=True` は数値のみ。`color` は `#RRGGBB`。`date` / `datetime` は UTC の Unix 秒。無効化してもスキーマは残るので `load` で登録してよい。`__init__` では例外。Host に渡す `label` / `description` / `suffix` / `path_filter` / choice の label、および `register_sidebar` の title、`register_filter` の title、`register_action` の label は、文字列全体が `{key}` のときだけ表示時に `get_text` する。台帳はテンプレートのまま。`"A{title}B"` や `"{title} ({hint})"` はリテラル。`{{` `}}` のエスケープは無い。混在が要る文言は langs 側で1キーにまとめる

状態:

- `host.get_current(key)` — `"path"` / `"folder"` / `"page"`
- `host.reload_current(page=None)` — 現在のファイルを開き直す（画像キャッシュも消える）。`page` は 1 始まり。省略時は今のページ
- `host.on(event, callback)` / `host.off(event, callback)` — `"current_changed"` / `"config_changed"`。`off` は有効中に外すとき。無効化は `clear_plugin`。サイドバーを登録したプラグインへの `"current_changed"` は、ドックが表示中か `permissions.inactive_callback` があるときに限る。`"config_changed"` は間引かない
- `host.get_app_config()` — `language` / `viewer` / `cache` / `ui_font` の読み取り専用

自プラグイン設定（DB の `plugin_id` はハッシュ化。他プラグインの行は読めない）:

- `host.get_config(key, default=None)` — 未保存ならスキーマの `default`。`date` / `datetime` は Unix 秒の int、`color` は `#RRGGBB`、`password` は平文、`path` は文字列。Enum choice は member。`multiple=True` は list
- `host.set_config(key, value)` — 型を正規化して保存し、そのプラグインへ `"config_changed"`（`{key, value}`）。required の empty は保存せず `False`
- `host.delete_config(key)`

プラグイン設定の一覧にスキーマがある行は「設定」ボタンが出ます。そこでパネルを開き OK / 適用すると、本体ダイアログの OK を待たずに DB へ保存して通知します。初期化はスキーマの default に戻します。`sync=True` の数値は 500ms のアイドル後に保存します。`reload=True` ならそのとき現在画像を開き直します。キャンセルはそのプレビューも戻します。ユーザーマニュアルの [プラグインリファレンス（コンフィグ）](../resources/UserManual/files/plugin-reference.html#plugin-config) に、スキーマ・保存場所・ダイアログの扱いをまとめています。

`load(root, get_text, host)` は必須です。UI の再接続用に任意の `setup()` / `teardown()` を実装できます。`setup()` は有効化のとき1回だけです。アプリ言語の変更では呼びません。`load` 失敗は UI 台帳と設定スキーマをそのプラグイン分だけ捨てます。`setup` 失敗は `teardown` を試してから `clear_plugin` します（スキーマは残す）。無効化すると本体の `clear_plugin` がサイドバー・登録アクション・`on` の listener・そのプラグインの FilterRecord を台帳から外します。**pipe の ID は残します**（次回 ON・次回起動で復元するため）。`off` / `unregister_*` は有効中に1件だけ外すとき用で、無効化の teardown には書かないでください。teardown に失敗理由は渡しません。所有物はフィールドの有無で止めてください。プラグイン設定の ON/OFF と、フィルターメニューの有効は別です。

任意の `language_changed()` はアプリの `set_language` 適用時だけ、ACTIVE なプラグインへ1回呼ばれます。引数なし。既存ウィジェットの表示文言更新専用です。未実装なら何もしません。ここでは `register_*` / `on` / `off` を禁止します。例外はそのプラグイン単位でログし、ACTIVE のまま他プラグインとメニュー更新は続けます。OS の表示言語変更は自動では見ません。ドックの visible / area / floating / widget は維持し、タイトルだけ差し替えます。

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

1. プラグイン `resources/langs/{現在言語}.json`
2. プラグイン `langs/{現在言語}.json`（互換）
3. プラグイン `src/langs/{言語}.json`（互換）
4. プラグイン ja.json または en.json（フォールバック。上記と同じ配置順）
5. 本体の言語ファイル

同じキーはプラグイン側が優先されます。言語は本体の現在言語です。Host に渡した名称が文字列全体 `{key}` なら、出す瞬間にこの `get_text` を使います。`"{config.fetch_web}"` のドットはキーの一部です。

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

#### `root.read_ui(relative_path)` / `root.read_asset(relative_path)` / `root.read_config(relative_path)`

```text
read_ui("sidebar.ui") -> resources/ui/sidebar.ui
read_asset("sounds/beep.wav") -> resources/assets/sounds/beep.wav
read_config("fields.json") -> resources/config/fields.json
```

サブフォルダ可。`..` / 絶対パス / 欠落は `KeyError`。`register_config_json` は `read_config` を呼びません。ウィジェット化は `host.load_ui(self.root.read_ui("sidebar.ui"))`。

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
self.host.register_sidebar("main", "{title}", self.widget, aliases=("old_toggle_id",))
self.host.register_action("refresh", "{refresh}", self.refresh)
```

---

### `register_filter`

```text
register_filter(filter_id: str, title: str, process) -> None
```

表示画像を加工するフィルターを台帳へ載せる。`manifest.permissions.filter` が `true` でない、または `process` が呼べないときは読み込み失敗。登録だけでは `process` は呼ばない。ユーザーがフィルターメニューで有効化した公開 ID だけが `config.filters.pipe` に入り、本体の `apply_pipe` がその順で呼ぶ。

**引数**

| 名前 | 型 | 説明 |
| --- | --- | --- |
| `filter_id` | `str` | プラグイン内で一意。`:` は使えない |
| `title` | `str` | フィルターメニューの枝名 |
| `process` | callable | `process(image, context) -> Image`。失敗は本体がログしてその段をスキップ。v1 は同期・短時間向け |

公開 ID は `plugin:{plugin_id}:{filter_id}`。設定は `register_config`。プラグインが複数フィルターを出しても設定ダイアログは1つ。原画キャッシュのオブジェクトは渡さない（working copy）。

```python
self.host.register_filter("sharp", "{sharp}", self._sharp)
```

---

### `unregister_filter`

```text
unregister_filter(filter_id: str) -> None
```

有効中に台帳からその1件を消す。pipe は触らない。無効化は `clear_plugin`。

```python
self.host.unregister_filter("sharp")
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

`resources/langs/ja.json` / `resources/langs/en.json` は入れ子オブジェクトです。キーはドットで辿ります。

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
      order: [enabled, name, id, version, kind, extensions, status, settings, license]
      widths: {enabled: 56, name: 160, id: 200, version: 72, kind: 90, extensions: 90, status: 110}
    ext_table:
      order: [extension, kind, handler]
      widths: {extension: 100, kind: 110, handler: 280}
```

| キー | 型 | 説明 |
| --- | --- | --- |
| `plugin_consent_version` | `string` | プロファイルではなく `user.json`。はいのとき `plugin_consent/version.txt`（例 `1.0.0`）を書く。無い・不正・不一致は未同意。本文を変えたら `version.txt` を上げる |
| `plugins.enabled` | `object` | `plugin_id` → 有効か。未記載は有効。ロード済みプラグインだけが対象 |
| `plugins.extension_handlers` | `object` | 拡張子 → `"builtin"`、`id(ver:version)`、または `"none"`（読み込まない）。旧形式も読む |
| `plugins.source_choice` | `object` | 重複 `id` → `{source, seen}`。`source` は `plugins/` 直下の名前、または `"none"`。選んだソースが残っている限り起動時は聞かない。切り替えるときはプラグイン設定の「重複プラグインの選択」 |
| `plugins.dialog` | `object` | プラグイン設定ダイアログの列順と幅。OK / キャンセルどちらでも保存する |

プラグイン固有の値は `plugin_settings` テーブルに、`plugin_id` のハッシュで保存します。プラグイン API に id 引数はありません。`manifest.json` の `version` を上げても `id` が同じなら同じ行です。本体設定の YAML エクスポートには出ません。詳細はユーザーマニュアルのプラグインリファレンス「プラグイン設定（コンフィグ）」です。

UI は「プラグイン設定」ダイアログです。ON/OFF と読み込み方式を扱います。OFF にしたプラグインが担当していた拡張子は、ビルドイン → 他プラグイン → 行削除の順で付け替えます。ID に `(ver:)` は付けません。

---

## 10. サンプル

| パス | 内容 |
| --- | --- |
| `plugins/example_png/` | `.png` を `image` として読む。色重ねは確認用。ZIP は `dist-sample-plugins/` |
| `plugins/example_zip/` | `.zip` を `archive` として読む。パスワードダイアログの呼び方も含む |
| `plugins/example_txt/` | `.txt` / `.log` を `archive` として読む。本文をページ画像にする。サイドバーで字体・色・縦読み／横読みを即時反映 |
| `plugins/product_info/` | 商品情報サイドバー。`resources/ui/sidebar.ui` を `load_ui` で読む。`info.json` が無くフォルダ／ファイル名が DLsite / DMM 番号なら、標準ライブラリだけで非同期取得（ディスクには書かない。設定で OFF 可） |
| `plugins/config_types/` | 確認用。設定種別を全部登録し、保存値をサイドバーに出す |
| `plugins/example_filter/` | 確認用。表示フィルター。色とラベルを重ね、文字サイズを `int_range`（`sync` と `reload`）で変える |

ソースの `plugin.py` 先頭にホスト契約のコメントがあります。確認するときはプラグイン設定で当該拡張子の読み込み方式をサンプル側にして OK / 適用してください。フィルターはプラグインを ON にしたあと、フィルターメニューで有効にしてください。開いているファイルはすぐ再読み込みされます。新しく ZIP やフォルダを置いた直後だけ再起動してください。

色と「プラグイン読み込み表示」「フィルター加工表示」はサンプル固有です。本番のローダーは画像バイトをそのまま返し、本番のフィルターは必要な加工だけにしてください。

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
| 文言がキーのまま | `resources/langs/ja.json` の入れ子と `get_text` のキーが一致しているか |

開発時は設定のデバッグモードを有効にすると、掃引・読み込み失敗・パスワード検証がログに出ます。
