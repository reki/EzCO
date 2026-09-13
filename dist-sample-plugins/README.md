# 配布用サンプルプラグイン

ここにある `.zip` は完成したサンプルです。データフォルダ（設定の「データの置き場」）の `plugins/` にコピーして使います。置いたあとは EzCo を再起動してください。ON/OFF や読み込み方式の変更はプラグイン設定の OK / 適用で足り、再起動は不要です。

本体は中身を検査しません。置いたコードはアプリと同じ権限で動きます。注意の全文は [plugins/README.md](../plugins/README.md) です。

開発するときはリポジトリの `plugins/` にある展開フォルダを置きます。データ置き場を実行ファイルと同じフォルダにすると、そのフォルダがそのまま読み込まれます。ZIP の作り直しは配布するときだけで構いません。

| ファイル | 内容 |
| --- | --- |
| `example_png.zip` | `.png` をプラグイン経由で開く確認用。ルートは `LICENSE`（拡張子なし） |
| `example_zip.zip` | `.zip` をプラグイン経由で開く確認用。ルートは `LICENSE.txt` |
| `example_txt.zip` | `.txt` をページ画像として開く。ルートは `LICENSE.md` |
| `product_info.zip` | 商品情報サイドバー。LICENSE なし |
| `error_setup.zip` | `setup()` で例外を出す確認用。LICENSE 3種あり、表示は md |
| `error_callback.zip` | コールバック例外の確認用。txt と無印あり、表示は txt |
| `config_types.zip` | 設定種別の確認用。bool / string / int / float / color / date / datetime / choice / font |

ソースから ZIP を作る例:

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
