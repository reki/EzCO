# 配布用サンプルプラグイン

ここにある `.zip` は完成したサンプルです。データフォルダ（設定の「データの置き場」）の `plugins/` にコピーして使います。

開発するときはリポジトリの `plugins/` にある展開フォルダを置きます。データ置き場を実行ファイルと同じフォルダにすると、そのフォルダがそのまま読み込まれます。ZIP の作り直しは配布するときだけで構いません。

| ファイル | 内容 |
| --- | --- |
| `example_png.zip` | `.png` をプラグイン経由で開く確認用 |
| `example_zip.zip` | `.zip` をプラグイン経由で開く確認用 |
| `example_txt.zip` | `.txt` をページ画像として開く |
| `product_info.zip` | 商品情報サイドバー |
| `error_setup.zip` | `setup()` で例外を出す確認用 |
| `error_callback.zip` | コールバック例外の確認用 |

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
