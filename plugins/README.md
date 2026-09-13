# EzCo プラグイン

実行ファイル（開発時はプロジェクトルート）旁のこのフォルダに ZIP を置くと、独自の画像／アーカイブ形式やサイドバーを追加できます。

開発者向けの契約・API リファレンスは [docs/plugins.md](../docs/plugins.md) にあります。

## ユーザー向け

1. `.zip` プラグインをこのフォルダ直下に置く（サブフォルダは読まれません）
2. EzCo を起動する（すでに起動中なら、ZIP を追加したあと再起動）
3. メニューのプラグイン設定で、プラグインの ON/OFF と拡張子ごとの読み込み方式（ビルドイン／プラグイン／読み込まない）を選ぶ。OK すると開いているファイルを再読み込みし、無効にしたプラグインのサイドバーは消えます
4. ビルドインと同じ拡張子は、既定ではビルドインが使われます
5. 一覧の列はドラッグで幅変更・並べ替えできます。幅と列順は保存されます
6. 有効なプラグインの拡張子は、「ファイルを開く」ダイアログの「対応しているファイル」と「プラグイン形式」に入ります。フォルダを開いたときのスキャン対象にも含まれます

DLL プラグインはまだ未対応です。

## このフォルダのサンプル

| ファイル | 内容 |
| --- | --- |
| `example_png.zip` | `.png` をプラグイン経由で開く確認用。色とラベルを重ねます |
| `example_zip.zip` | `.zip` をプラグイン経由で開く確認用。パスワードダイアログの呼び出しも含みます |
| `product_info.zip` | 商品情報サイドバー。`info.json` と `folder.jpg` を表示します |

`example_png/`、`example_zip/`、`product_info/` はソースです。ホストが読むのは `.zip` の方なので、ソースを直したら ZIP を作り直してください。

```python
from pathlib import Path
import zipfile

src = Path("plugins/example_zip")
dst = Path("plugins/example_zip.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(src.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(src).as_posix())
```

サンプルの色重ねは確認用です。本番プラグインでは不要です。

## 最小構成

```
my_plugin.zip
├── manifest.json
├── src/
│   └── loader.py
└── langs/
    ├── ja.json
    └── en.json
```

ファイルローダーは `supported_formats`（または `host.register_format`）と `read_entry` などを実装します。サイドバーは `setup` で `host.load_ui` / `host.register_sidebar` します。コンストラクタは `Class(root, get_text, host)` です。`ez_co` は import できません。設定上の正体は `manifest.id(ver:version)` です。ダイアログの ID 列はバージョンなしの `id` だけです。同じ `id` の別バージョンは共存できます。詳細はマニュアルを見てください。
