# Example Text Pages

`.txt` / `.log` をページ画像として開く一般向けサンプルです。本文を折り返して PNG にし、本体の次／前ページで読み進めます。サイドバーで字体・色・余白・縦読み／横読み・文字コードを変えられ、変更はすぐに反映されます。

| 項目 | 値 |
| --- | --- |
| ID | `com.ezco.example_txt` |
| バージョン | `1.0.0` |
| 種別 | ファイル（アーカイブ） |
| ZIP | `dist-sample-plugins/example_txt-1.0.0.zip` |
| 入口 | `plugin:TextImagePlugin` |
| LICENSE | ルートの `LICENSE.md`（Markdown 表示の確認用） |

## 使い方

1. `example_txt.zip` をデータフォルダの `plugins/` 直下に置く
2. EzCo を起動（追加したあとは再起動）
3. プラグイン設定でこのプラグインを有効にする
4. `.txt` または `.log` を開く（ビルドインは担当しないので、有効ならこのローダーが使われます）

フォントをまだ保存していないときは、本体の UI フォントに合わせます。ページ数が変わる設定でも、今見ているページの先頭の文字から新しく表示します。1 行も入らない組み合わせは保存されますが、表示は開き直しません。初期値に戻すときはサイドバーの初期化です。

## 開発

ソースは `plugins/example_txt/` です。データフォルダの `plugins/` にこのフォルダを置けばそのまま読めます。配布 ZIP は `dist-sample-plugins/` です。

```python
from pathlib import Path
import zipfile

src = Path("plugins/example_txt")
dst = Path("dist-sample-plugins/example_txt.zip")
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(src.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            zf.write(path, path.relative_to(src).as_posix())
```

ホスト API の一覧はユーザーマニュアルの [プラグインリファレンス](../../resources/UserManual/files/plugin-reference.html) と [docs/plugins.md](../../docs/plugins.md) を見てください。
