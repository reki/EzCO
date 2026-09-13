# EzCo プラグイン

データフォルダ（設定の「データの置き場」。既定はこのユーザーのデータフォルダ）の `plugins/` に ZIP、または `manifest.json` 付きの展開フォルダを置くと、独自の画像／アーカイブ形式やサイドバーを追加できます。開発時にリポジトリのこのフォルダを使うときは、置き場を実行ファイルと同じフォルダにしてください。

開発者向けの契約・API リファレンスは [docs/plugins.md](../docs/plugins.md) とユーザーマニュアルの [プラグインリファレンス](../resources/UserManual/files/plugin-reference.html) にあります。各プラグインの説明はフォルダ内の `README.md` です。配布用 ZIP は [dist-sample-plugins/](../dist-sample-plugins/) です。

## ユーザー向け

1. `.zip`、または `manifest.json` のあるフォルダをデータフォルダの `plugins/` 直下に置く（その下の入れ子は読まれません）。場所は設定の「データの置き場」です
2. EzCo を起動する（すでに起動中なら、追加したあと再起動）
3. メニューのプラグイン設定で、プラグインの ON/OFF と拡張子ごとの読み込み方式（ビルドイン／プラグイン／読み込まない）を選ぶ。スキーマがあるプラグインは「設定」から項目を変えられ、OK するとすぐ保存される。本体ダイアログの OK では開いているファイルを再読み込みし、無効にしたプラグインのサイドバーは消えます。有効なサイドバーの開閉や、プラグインが登録したアクションはショートカット／ジェスチャーに割り当てできます
4. ビルドインと同じ拡張子は、既定ではビルドインが使われます
5. 一覧の列はドラッグで幅変更・並べ替えできます。幅と列順は保存されます
6. 有効なプラグインの拡張子は、「ファイルを開く」ダイアログの「対応しているファイル」と「プラグイン形式」に入ります。フォルダを開いたときのスキャン対象にも含まれます

同じ `id` とバージョンのフォルダと ZIP が両方あるときは、フォルダを使います。DLL プラグインはまだ未対応です。

## このフォルダのサンプル

ここはソースです。データ置き場を実行フォルダにすると、これらのフォルダがそのまま読み込まれます。配布用 ZIP は [`dist-sample-plugins/`](../dist-sample-plugins/) です。

| フォルダ | 内容 |
| --- | --- |
| `example_png/` | `.png` をプラグイン経由で開く確認用。色とラベルを重ねます。[README](example_png/README.md) |
| `example_zip/` | `.zip` をプラグイン経由で開く確認用。パスワードダイアログの呼び出しも含みます。[README](example_zip/README.md) |
| `example_txt/` | `.txt` をページ画像として開く一般向けサンプル。サイドバーで字体・色・縦読み／横読みを即時反映します。[README](example_txt/README.md) |
| `product_info/` | 商品情報サイドバー。`info.json` と `folder.jpg` を表示。無いときはフォルダ／ファイル名の DLsite / DMM 番号から Web 取得（設定で OFF 可。フォルダには書かない）。[README](product_info/README.md) |
| `error_setup/` | 確認用。`setup()` で例外を出す。[README](error_setup/README.md) |
| `error_callback/` | 確認用。サイドバーの「エラー」ボタンでコールバック例外を出す。[README](error_callback/README.md) |

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

サンプルの色重ねは確認用です。本番プラグインでは不要です。

## 最小構成

```
my_plugin/   または my_plugin.zip
├── manifest.json
├── src/
│   └── loader.py
└── langs/
    ├── ja.json
    └── en.json
```

ファイルローダーは `supported_formats`（または `host.register_format`）と `read_entry` などを実装します。サイドバーは `setup` で `host.load_ui` / `host.register_sidebar` します。開閉は自動でアクション登録されます。旧ショートカット ID を残すときは `aliases` を渡します。独自処理は `host.register_action` です。コンストラクタは `Class(root, get_text, host)` です。`ez_co` は import できません。設定上の正体は `manifest.id(ver:version)` です。ダイアログの ID 列はバージョンなしの `id` だけです。同じ `id` の別バージョンは共存できます。詳細はマニュアルを見てください。
