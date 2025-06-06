# EzCo プラグイン

実行ファイル（開発時はプロジェクトルート）旁のこのフォルダに ZIP を置くと、独自の画像／アーカイブ形式を読み込めます。

開発者向けの契約・API リファレンスは [docs/plugins.md](../docs/plugins.md) にあります。

## ユーザー向け

1. `.zip` プラグインをこのフォルダ直下に置く（サブフォルダは読まれません）
2. EzCo を起動する（すでに起動中なら、ZIP を追加したあと再起動）
3. メニューのファイル設定で、拡張子ごとの読み込み方式（ビルドイン／プラグイン／読み込まない）を選ぶ。OK すると開いているファイルを再読み込みします
4. ビルドインと同じ拡張子は、既定ではビルドインが使われます
5. 一覧の列はドラッグで幅変更・並べ替えできます。幅と列順は保存されます
6. 読み込み済みプラグインの拡張子は、「ファイルを開く」ダイアログの「対応しているファイル」と「プラグイン形式」に入ります。フォルダを開いたときのスキャン対象にも含まれます

DLL プラグインはまだ未対応です。

## このフォルダのサンプル

| ファイル | 内容 |
| --- | --- |
| `example_png.zip` | `.png` をプラグイン経由で開く確認用。色とラベルを重ねます |
| `example_zip.zip` | `.zip` をプラグイン経由で開く確認用。パスワードダイアログの呼び出しも含みます |

`example_png/` と `example_zip/` はソースです。ホストが読むのは `.zip` の方なので、ソースを直したら ZIP を作り直してください。

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

`loader.py` には `supported_formats` / `get_file_count` / `list_entries` / `read_entry` を実装します。コンストラクタは `FileLoader(root, get_text, host)` です。`ez_co` は import できません。設定上の正体は `manifest.id(ver:version)` です。ダイアログの ID 列はバージョンなしの `id` だけです。同じ `id` の別バージョンは共存できます。詳細はマニュアルを見てください。
